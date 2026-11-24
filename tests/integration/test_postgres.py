"""Mandatory PostgreSQL tests; never substituted with SQLite or skipped in CI."""

import csv
import json
import os
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from openpyxl import Workbook
from sqlalchemy import create_engine, func, select, text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session
from app.api.main import app
from app.config import settings
from app.db import get_session
from app.etl.importer import import_file
from app.models.entities import Batch, Value
from scripts.seed import seed

pytestmark = pytest.mark.postgres
URL = "https://example.gov.ru/statistics/test-fixture"


@pytest.fixture(scope="module")
def pg_engine():
    url = os.environ.get("TEST_DATABASE_URL")
    if not url:
        pytest.fail(
            "TEST_DATABASE_URL is required: mandatory PostgreSQL test cannot run"
        )
    parsed = make_url(url)
    if (
        parsed.get_backend_name() != "postgresql"
        or parsed.database != "regional_ci_test"
    ):
        pytest.fail("Only dedicated disposable database regional_ci_test is accepted")
    engine = create_engine(url, pool_pre_ping=True)
    os.environ["DATABASE_URL"] = url
    settings.cache_clear()
    command.upgrade(Config("alembic.ini"), "head")
    with Session(engine) as session, session.begin():
        session.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        seed(session, external=False)
    yield engine
    engine.dispose()
    settings.cache_clear()


@pytest.fixture
def pg_session(pg_engine, tmp_path, monkeypatch):
    monkeypatch.setenv("RAW_DIR", str(tmp_path / "archive"))
    settings.cache_clear()
    with pg_engine.begin() as connection:
        connection.execute(
            text(
                "TRUNCATE regional.indicator_values, regional.data_quality_issues, regional.import_batches, core.sources CASCADE"
            )
        )
    with Session(pg_engine) as session:
        yield session


def fixture_file(path, fmt="csv", value="100", published="2024-07-12T03:00:00+03:00"):
    rows = [
        dict(
            indicator_code="births",
            region="RU-77",
            period_start="2023-01-01",
            period_end="2023-12-31",
            value=value,
            published_at=published,
        ),
        dict(
            indicator_code="births",
            region="RU-78",
            period_start="2023-01-01",
            period_end="2023-12-31",
            value=None,
            published_at=published,
        ),
    ]
    if fmt == "json":
        path.write_text(json.dumps(rows), encoding="utf-8")
    elif fmt == "xlsx":
        book = Workbook()
        book.active.append(list(rows[0]))
        for row in rows:
            book.active.append(list(row.values()))
        book.save(path)
    else:
        with path.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
            writer.writeheader()
            writer.writerows(rows)
    return path


def test_migrated_postgres_schema_and_indexes(pg_session):
    version = pg_session.scalar(text("SHOW server_version_num"))
    assert 160000 <= int(version) < 170000
    assert pg_session.scalar(
        text("SELECT extversion FROM pg_extension WHERE extname='vector'")
    )
    assert pg_session.scalar(text("SELECT version_num FROM alembic_version")) == "0005"
    schemas = set(
        pg_session.scalars(text("SELECT schema_name FROM information_schema.schemata"))
    )
    assert {"core", "regional"} <= schemas
    assert "media" not in schemas and "practices" not in schemas
    indexes = list(
        pg_session.scalars(
            text("SELECT indexdef FROM pg_indexes WHERE schemaname='regional'")
        )
    )
    assert any("uq_values_current" in i and "WHERE is_current" in i for i in indexes)
    assert any("revision_number" in i and "UNIQUE" in i for i in indexes)


def test_89_profile_reference_data(pg_session):
    rows = pg_session.execute(text(
        "SELECT region_id,name,federal_district,valid_from FROM core.regions "
        "WHERE region_id IN ('RU-80','RU-81','RU-84','RU-85') ORDER BY region_id"
    )).all()
    assert len(rows) == 4
    assert [r[0] for r in rows] == ['RU-80', 'RU-81', 'RU-84', 'RU-85']
    assert all(r[2] == '' and str(r[3]) == '2023-01-01' for r in rows)
    assert pg_session.scalar(text("SELECT count(*) FROM core.regions WHERE region_id LIKE 'RU-%'")) == 89


@pytest.mark.parametrize("fmt", ["csv", "xlsx", "json"])
def test_formats_dedup_null_utc_and_persistence(pg_session, pg_engine, tmp_path, fmt):
    path = fixture_file(tmp_path / ("fixture." + fmt), fmt)
    batch = import_file(pg_session, path, URL, "Synthetic CI fixture")
    assert batch.errors == 0
    original_id = batch.batch_id
    pg_session.commit()
    assert (
        import_file(pg_session, path, URL, "Synthetic CI fixture").batch_id
        == original_id
    )
    pg_session.commit()
    pg_engine.dispose()  # Close pool; reopen connections, never in-memory SQLite.
    with Session(pg_engine) as second:
        values = second.scalars(select(Value)).all()
        assert len(values) == 2
        assert sum(v.value is None for v in values) == 1
        for v in values:
            assert v.published_at.utcoffset() == timedelta(0)
            assert v.loaded_at.utcoffset() == timedelta(0)
        assert second.scalar(select(func.count()).select_from(Batch)) == 1


def test_revisions_and_api_real_postgres(pg_session, tmp_path):
    path = fixture_file(tmp_path / "fixture.csv")
    import_file(pg_session, path, URL, "Synthetic CI fixture")
    fixture_file(path, value="110", published="2024-08-12T00:00:00Z")
    import_file(pg_session, path, URL, "Synthetic CI fixture")
    pg_session.commit()
    rows = pg_session.scalars(
        select(Value).where(Value.region_id == "RU-77").order_by(Value.revision_number)
    ).all()
    assert [v.is_current for v in rows] == [False, True]
    assert [int(v.value) for v in rows] == [100, 110]
    app.dependency_overrides[get_session] = lambda: pg_session
    try:
        with TestClient(app) as client:
            assert client.get("/api/v1/health").status_code == 200
            response = client.get("/api/v1/regional/values?region_id=RU-77").json()
            assert response["total"] == 1
            assert float(response["items"][0]["value"]) == 110
            assert (
                client.get(
                    "/api/v1/regional/values?region_id=RU-77&history=true"
                ).json()["total"]
                == 2
            )
            assert client.get("/api/v1/regional/profiles/RU-77").status_code == 200
    finally:
        app.dependency_overrides.clear()


def test_parallel_import_and_advisory_lock(pg_session, pg_engine, tmp_path):
    path = fixture_file(tmp_path / "parallel.json", "json")

    def worker(_):
        with Session(pg_engine) as session, session.begin():
            return import_file(
                session, path, URL, "Synthetic concurrent fixture"
            ).batch_id

    with ThreadPoolExecutor(max_workers=4) as pool:
        ids = list(pool.map(worker, range(4)))
    assert len(set(ids)) == 1
    assert pg_session.scalar(select(func.count()).select_from(Value)) == 2
    # The importer lock is transaction-scoped and blocks another connection.
    with pg_engine.connect() as first, pg_engine.connect() as second:
        first.execute(text("SELECT pg_advisory_xact_lock(1701202601)"))
        assert (
            second.scalar(text("SELECT pg_try_advisory_xact_lock(1701202601)")) is False
        )
        first.rollback()
        assert (
            second.scalar(text("SELECT pg_try_advisory_xact_lock(1701202601)")) is True
        )
        second.rollback()


def test_inspected_official_subset_on_postgres(pg_session):
    from scripts.load_official_bundle import load_bundle

    first = load_bundle(pg_session)
    assert first.errors == 0
    assert load_bundle(pg_session).batch_id == first.batch_id
    assert pg_session.scalar(select(func.count()).select_from(Value)) == 20
    pg_session.commit()

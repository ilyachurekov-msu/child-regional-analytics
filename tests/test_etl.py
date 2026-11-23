import csv
from decimal import Decimal
from sqlalchemy import func, select
from app.etl.importer import import_file
from app.etl.normalize import number, source_identifier
from app.models.entities import Batch, QualityIssue, Value
import pytest

URL = "https://rosstat.gov.ru/compendium/document/13269"


def write(path, values):
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "indicator_code",
                "region",
                "period_start",
                "period_end",
                "value",
                "published_at",
            ],
        )
        writer.writeheader()
        for i, value in enumerate(values):
            writer.writerow(
                dict(
                    indicator_code="births",
                    region="Москва",
                    period_start=f"{2021 + i}-01-01",
                    period_end=f"{2021 + i}-12-31",
                    value=value,
                    published_at="2024-07-12T00:00:00Z",
                )
            )


def test_idempotence_revision_and_missing(session, tmp_path):
    path = tmp_path / "data.csv"
    write(path, ["100", ""])
    first = import_file(session, path, URL, "Test fixture, NOT official observations")
    again = import_file(session, path, URL, "Test fixture")
    assert first.batch_id == again.batch_id
    assert session.scalar(select(func.count()).select_from(Value)) == 2
    missing = session.scalar(select(Value).where(Value.value.is_(None)))
    assert missing.data_status == "missing"
    write(path, ["101", ""])
    import_file(session, path, URL, "Test fixture")
    rows = session.scalars(
        select(Value)
        .where(Value.period_start == missing.period_start.replace(year=2021))
        .order_by(Value.revision_number)
    ).all()
    assert [r.value for r in rows] == [Decimal(100), Decimal(101)]
    assert [r.is_current for r in rows] == [False, True]
    assert session.scalar(select(func.count()).select_from(Batch)) == 2


def test_invalid_values_and_unknown_region(session, tmp_path):
    path = tmp_path / "bad.csv"
    write(path, ["-1", "not a number", "Infinity"])
    batch = import_file(session, path, URL, "Test fixture")
    assert batch.errors == 3
    assert session.scalar(select(func.count()).select_from(Value)) == 0
    assert session.scalar(select(func.count()).select_from(QualityIssue)) == 3
    path.write_text(
        path.read_text(encoding="utf-8").replace("Москва", "Неизвестный регион"),
        encoding="utf-8",
    )
    batch = import_file(session, path, URL, "Test fixture")
    assert batch.errors == 3


@pytest.mark.parametrize(
    "raw,expected", [("1 234,5", Decimal("1234.5")), ("—", None), ("0", Decimal(0))]
)
def test_number(raw, expected):
    assert number(raw) == expected


def test_source_normalization():
    assert (
        source_identifier("HTTP://www.Rosstat.gov.ru/a/#test")
        == "https://rosstat.gov.ru/a"
    )

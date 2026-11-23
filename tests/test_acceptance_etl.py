import json
from sqlalchemy import func, select
from app.etl.importer import import_file
from app.models.entities import Value
from tests.test_etl import URL


def row(**kwargs):
    return dict(
        indicator_code="births",
        region="RU-77",
        period_start="2023-01-01",
        period_end="2023-12-31",
        value="10",
        published_at="2024-07-12T00:00:00Z",
        **kwargs,
    )


def test_units_dates_structure_and_missing_status_fail_closed(session, tmp_path):
    path = tmp_path / "rows.json"
    for change in (
        {"unit": "на 1000 жителей"},
        {"period_start": "2023-01-01garbage"},
        {"data_status": "missing"},
    ):
        data = row()
        data.update(change)
        path.write_text(json.dumps([data]), encoding="utf-8")
        assert import_file(session, path, URL, "Test fixture").errors == 1
    path.write_text(json.dumps([{"unknown_column": 1}]), encoding="utf-8")
    assert import_file(session, path, URL, "Test fixture").status == "failed"
    assert session.scalar(select(func.count()).select_from(Value)) == 0


def test_original_versions_unknown_date_and_stale_equal_value(session, tmp_path):
    path = tmp_path / "rows.json"
    original = tmp_path / "original.pdf"
    original.write_bytes(b"%PDF-synthetic-v1")
    data = row()
    data["published_at"] = None
    data["unit"] = "человек"
    path.write_text(json.dumps([data]), encoding="utf-8")
    first = import_file(session, path, URL, "Test fixture", original_path=original)
    assert first.original_checksum and first.original_path
    assert session.scalar(select(Value)).published_at is None
    original.write_bytes(b"%PDF-synthetic-v2")
    second = import_file(session, path, URL, "Test fixture", original_path=original)
    assert first.batch_id != second.batch_id
    data["published_at"] = "2024-09-12T00:00:00Z"
    data["value"] = "11"
    path.write_text(json.dumps([data]), encoding="utf-8")
    assert import_file(session, path, URL, "Test fixture").errors == 0
    data["published_at"] = "2024-07-12T00:00:00Z"
    path.write_text(json.dumps([data]), encoding="utf-8")
    assert import_file(session, path, URL, "Test fixture").errors == 1

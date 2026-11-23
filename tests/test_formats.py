import json
from openpyxl import Workbook
from sqlalchemy import select, func
from app.etl.importer import import_file
from app.models.entities import Value
from tests.test_etl import URL


def test_json_xlsx_and_invalid_publication(session, tmp_path):
    row = dict(
        indicator_code="births",
        region="RU-77",
        period_start="2023-01-01",
        period_end="2023-12-31",
        value="123",
        published_at="2024-07-12T00:00:00Z",
    )
    path = tmp_path / "values.json"
    path.write_text(json.dumps([row]), encoding="utf-8")
    assert import_file(session, path, URL, "Test fixture").errors == 0
    book = Workbook()
    book.active.append(list(row))
    book.active.append(list(row.values()))
    xlsx = tmp_path / "values.xlsx"
    book.save(xlsx)
    assert import_file(session, xlsx, URL, "Test fixture").errors == 0
    assert session.scalar(select(func.count()).select_from(Value)) == 1
    row["published_at"] = "2024-07-12T00:00:00"
    row["value"] = "124"
    path.write_text(json.dumps([row]), encoding="utf-8")
    assert import_file(session, path, URL, "Test fixture").errors == 1


def test_bad_format_is_recorded(session, tmp_path):
    path = tmp_path / "bad.json"
    path.write_text("{not json}", encoding="utf-8")
    batch = import_file(session, path, URL, "Test fixture")
    assert batch.status == "failed" and batch.errors == 1

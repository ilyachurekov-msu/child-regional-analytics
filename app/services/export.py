import csv
from io import BytesIO, StringIO
from openpyxl import Workbook


def safe_cell(value):
    if isinstance(value, str) and value.lstrip().startswith(("=", "+", "-", "@")):
        return "'" + value
    return value


def export_rows(rows, file_format):
    # Exact strings preserve decimal precision and ISO time zone information.
    header = (
        list(rows[0])
        if rows
        else ["region_id", "indicator_code", "period_start", "value", "source_url"]
    )
    values = [
        [safe_cell("" if r.get(k) is None else str(r[k])) for k in header] for r in rows
    ]
    if file_format == "csv":
        output = StringIO(newline="")
        writer = csv.writer(output)
        writer.writerow(header)
        writer.writerows(values)
        return output.getvalue().encode("utf-8-sig")
    book = Workbook()
    sheet = book.active
    sheet.title = "Региональная аналитика"
    sheet.append(header)
    for row in values:
        sheet.append(row)
    sheet.freeze_panes = "A2"
    sheet.auto_filter.ref = sheet.dimensions
    output = BytesIO()
    book.save(output)
    return output.getvalue()

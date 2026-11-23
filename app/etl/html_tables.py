from html.parser import HTMLParser
import re


class PublicationTables(HTMLParser):
    """Read actual HTML cells without guessing spreadsheet column positions."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.tables = []
        self.context = []
        self.table = None
        self.row = None
        self.cell = None
        self.hidden = 0

    def handle_starttag(self, tag, attrs):
        if tag in ("script", "style"):
            self.hidden += 1
        if self.hidden:
            return
        if tag == "table":
            if self.table is not None:
                raise ValueError("Nested publication tables are unsupported")
            self.table = {"context": " ".join(self.context)[-1800:], "rows": []}
        elif tag == "tr" and self.table is not None:
            self.row = []
        elif tag in ("td", "th") and self.row is not None:
            self.cell = []

    def handle_data(self, data):
        if self.hidden:
            return
        if self.cell is not None:
            self.cell.append(data)
        elif self.table is None:
            value = data.strip()
            if value:
                self.context.append(value)

    def handle_endtag(self, tag):
        if tag in ("script", "style"):
            self.hidden = max(0, self.hidden - 1)
            return
        if self.hidden:
            return
        if tag in ("td", "th") and self.cell is not None:
            self.row.append(re.sub(r"\s+", " ", " ".join(self.cell)).strip())
            self.cell = None
        elif tag == "tr" and self.row is not None:
            self.table["rows"].append(self.row)
            self.row = None
        elif tag == "table" and self.table is not None:
            self.tables.append(self.table)
            self.table = None


def publication_tables(payload):
    if b"charset=windows-1251" not in payload[:2000].lower():
        raise ValueError("Publication encoding changed; review adapter")
    parser = PublicationTables()
    parser.feed(payload.decode("cp1251"))
    return parser.tables

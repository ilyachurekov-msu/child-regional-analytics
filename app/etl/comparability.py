"""Fail closed on mixed definitions, periods and units; never impute values."""


def validate_series(rows, specification):
    seen = set()
    for row in rows:
        year = int(row["period_start"][:4])
        key = row["region"], row["indicator_code"], year
        if key in seen:
            raise ValueError("Duplicate observation in source")
        seen.add(key)
        if year not in specification["years"]:
            raise ValueError("Unexpected observation year")
        if (
            row["period_start"] != f"{year}-01-01"
            or row["period_end"] != f"{year}-12-31"
        ):
            raise ValueError("Only full calendar years are comparable")
        expected = (
            "единиц"
            if row["indicator_code"] in ("marriages", "divorces")
            else "человек"
        )
        if row.get("unit") != expected:
            raise ValueError("Unit mismatch; rates must not be mixed with counts")
    return rows

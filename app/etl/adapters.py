"""Strict publication-specific adapters. Unexpected layout is a hard error."""

import re

VERSION = "lipetsk-yearly-pdf/1.0.0"
LABELS = {
    "births": "Число родившихся",
    "deaths": "Число умерших",
    "natural_change": "Естественная убыль населения",
    "marriages": "Число браков",
    "divorces": "Число разводов",
}


def lipetsk_table(text, specification):
    years = specification["years"]
    if years != [2022, 2023] or specification["region_id"] != "RU-48":
        raise ValueError(
            "Адаптер применим только к проверяемой публикации Липецкстата 2022–2023"
        )
    normalized = text.replace("\u00a0", " ").replace("−", "-")
    if (
        not re.search(r"2022\s+2023", normalized)
        or "Липец" not in normalized
        or "Человек" not in normalized
    ):
        raise ValueError(
            "Изменилась структура публикации: регион, годы или единица не подтверждены"
        )
    if not re.search(r"январ[ьяе]\s*[–—-]\s*декабр", normalized, re.IGNORECASE):
        raise ValueError("Не подтверждён полный год наблюдения")
    result = {}
    for code, label in LABELS.items():
        label_pattern = r"\s+".join(map(re.escape, label.split()))
        matches = re.findall(
            r"(?m)^\s*" + label_pattern + r"\s+(-?\d+)\s+(-?\d+)\s*$", normalized
        )
        if len(matches) != 1:
            raise ValueError("Неоднозначная или изменённая строка таблицы: " + label)
        result[code] = list(map(int, matches[0]))
    rows = []
    for index, year in enumerate(years):
        if (
            result["births"][index] - result["deaths"][index]
            != result["natural_change"][index]
        ):
            raise ValueError("Контрольная сверка births - deaths != natural_change")
        for code in LABELS:
            value = result[code][index]
            if code != "natural_change" and value < 0:
                raise ValueError("Отрицательное число событий")
            rows.append(
                dict(
                    indicator_code=code,
                    region=specification["region_id"],
                    period_start=f"{year}-01-01",
                    period_end=f"{year}-12-31",
                    value=str(value),
                    published_at=specification.get("published_at"),
                    unit="единиц" if code in ("marriages", "divorces") else "человек",
                    data_status="provisional",
                )
            )
    return rows


def adapt_pdf(path, specification):
    from pypdf import PdfReader

    if specification["adapter"] != VERSION:
        raise ValueError("Неизвестный адаптер")
    text = "\n".join(
        page.extract_text(extraction_mode="layout") or ""
        for page in PdfReader(path).pages
    )
    return lipetsk_table(text, specification)


def kemerovo_html(payload, specification):
    from app.etl.html_tables import publication_tables

    supported = [
        2019,
        2020,
        2021,
        2022,
    ]
    if specification["region_id"] != "RU-42" or specification["years"] not in (supported, [2018] + supported):
        raise ValueError(
            "Unsupported region/year contract for Kemerovostat publication"
        )
    tables = publication_tables(payload)
    demo = [
        t
        for t in tables
        if re.search(
            r"4\.12\.\s*РОЖДАЕМОСТЬ,\s*СМЕРТНОСТЬ И ЕСТЕСТВЕННЫЙ ПРИРОСТ НАСЕЛЕНИЯ\s*$",
            t["context"],
        )
    ]
    marriage = [
        t for t in tables if re.search(r"4\.20\.\s*БРАКИ И\s*РАЗВОДЫ\s*$", t["context"])
    ]
    if len(demo) != 1 or len(marriage) != 1:
        raise ValueError("Changed table headings 4.12/4.20")
    demo = demo[0]["rows"]
    marriage = marriage[0]["rows"]
    if "Всего, человек" not in demo[0] or "Всё население" not in demo[3]:
        raise ValueError("Expected absolute counts for entire population")
    if [c.replace(" ", "") for c in marriage[0][1:]] != [
        "2018",
        "2019",
        "2020",
        "2021",
        "2022",
    ]:
        raise ValueError("Changed marriage years")
    if (
        marriage[2][0] != "Браков"
        or marriage[3][0] != "Разводов"
        or not marriage[4][0].startswith("На 1000")
    ):
        raise ValueError("Changed marriage absolute/rate boundary")
    result = []
    years = []
    # Exactly the first all-population block, never urban/rural or Russian rates.
    for item in demo[4:9]:
        year = int(item[0].replace(" ", ""))
        years.append(year)
        if len(item) != 11:
            raise ValueError("Changed demography column count")
        if year not in specification["years"]:
            continue
        values = {
            code: int(item[index].replace(" ", ""))
            for index, code in enumerate(
                ("births", "deaths", "natural_change"), start=1
            )
        }
        if values["births"] - values["deaths"] != values["natural_change"]:
            raise ValueError("Natural change reconciliation failed")
        column = year - 2018 + 1
        values.update(
            marriages=int(marriage[2][column]), divorces=int(marriage[3][column])
        )
        for code, value in values.items():
            if code != "natural_change" and value < 0:
                raise ValueError("Negative event count")
            result.append(
                dict(
                    indicator_code=code,
                    region="RU-42",
                    period_start=f"{year}-01-01",
                    period_end=f"{year}-12-31",
                    value=str(value),
                    published_at=None,
                    unit="единиц" if code in ("marriages", "divorces") else "человек",
                    data_status="official",
                )
            )
    if years != [2018, 2019, 2020, 2021, 2022] or len(result) != 5 * len(specification['years']):
        raise ValueError("Changed all-population year coverage")
    return result

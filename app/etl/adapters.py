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

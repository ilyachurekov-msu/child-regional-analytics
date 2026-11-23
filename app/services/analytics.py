from statistics import median
from sqlalchemy import select
from app.models.entities import Indicator, Region, Source, Value


def observations_query(region_ids=None, indicator_code=None, year=None, history=False):
    query = (
        select(Value, Indicator, Region, Source)
        .join(Indicator, Value.indicator_id == Indicator.indicator_id)
        .join(Region, Value.region_id == Region.region_id)
        .join(Source, Value.source_id == Source.source_id)
    )
    if not history:
        query = query.where(Value.is_current.is_(True))
    if region_ids:
        query = query.where(Value.region_id.in_(region_ids))
    if indicator_code:
        query = query.where(Indicator.code == indicator_code)
    if year:
        from datetime import date

        query = query.where(
            Value.period_start >= date(year, 1, 1),
            Value.period_end <= date(year, 12, 31),
        )
    return query.order_by(
        Value.period_start, Region.region_id, Indicator.code, Value.revision_number
    )


def observation(row):
    value, indicator, region, source = row
    return dict(
        value_id=value.value_id,
        indicator_code=indicator.code,
        indicator_name=indicator.name,
        region_id=region.region_id,
        region_name=region.name,
        federal_district=region.federal_district,
        period_start=value.period_start,
        period_end=value.period_end,
        value=value.value,
        unit=indicator.unit,
        source_id=source.source_id,
        source_name=source.name,
        source_url=source.url,
        published_at=value.published_at,
        loaded_at=value.loaded_at,
        data_status=value.data_status,
        revision_number=value.revision_number,
    )


def change(previous, current):
    if previous is None or current is None:
        return {"absolute_change": None, "relative_change_percent": None}
    return {
        "absolute_change": current - previous,
        "relative_change_percent": (current - previous) / abs(previous) * 100
        if previous != 0
        else None,
    }


def deviations(rows, direction):
    # Only subjects; aggregate rows must never enter the subject median.
    valid = [
        r for r in rows if r["region_id"].startswith("RU-") and r["value"] is not None
    ]
    if not valid:
        return []
    mid = median(r["value"] for r in valid)
    national = next((r["value"] for r in rows if r["region_id"] == "RU"), None)
    result = [
        dict(
            r,
            median=mid,
            deviation_from_median=r["value"] - mid,
            difference_from_russia=r["value"] - national
            if national is not None
            else None,
            unfavorable_direction=direction,
        )
        for r in valid
    ]
    return sorted(result, key=lambda r: r["value"], reverse=direction != "positive")


def construct_index(matrix, weights, directions):
    if (
        not weights
        or set(weights) != set(directions)
        or any(w <= 0 for w in weights.values())
    ):
        raise ValueError("Нужны положительные веса и направления для всех показателей")
    if any(d not in ("positive", "negative") for d in directions.values()):
        raise ValueError("Для индекса явно выберите направление нормирования")
    bounds = {}
    for code in weights:
        values = [r[code] for r in matrix.values() if r.get(code) is not None]
        if not values or min(values) == max(values):
            raise ValueError("Нормирование невозможно: отсутствует разброс " + code)
        bounds[code] = min(values), max(values)
    total = sum(weights.values())
    result = {}
    for region, row in matrix.items():
        if any(row.get(code) is None for code in weights):
            result[region] = None
            continue
        score = 0
        for code, weight in weights.items():
            low, high = bounds[code]
            normalized = (row[code] - low) / (high - low)
            if directions[code] == "negative":
                normalized = 1 - normalized
            score += normalized * weight / total
        result[region] = score * 100
    return result

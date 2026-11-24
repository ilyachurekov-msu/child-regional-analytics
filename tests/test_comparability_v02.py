from decimal import Decimal
from app.services.analytics import deviations


def test_published_district_and_country_only():
    rows = [
        dict(region_id="RU-42", federal_district="Сибирский", value=Decimal(10)),
        dict(region_id="RU-54", federal_district="Сибирский", value=Decimal(30)),
        dict(region_id="RU", federal_district="", value=Decimal(200)),
        dict(region_id="FD-07", federal_district="Сибирский", value=Decimal(50)),
    ]
    result = deviations(rows, "ambiguous")
    assert result[0]["difference_from_russia"] == -170
    assert result[0]["difference_from_federal_district"] == -20
    assert (
        deviations(rows[:2], "ambiguous")[0]["difference_from_federal_district"] is None
    )

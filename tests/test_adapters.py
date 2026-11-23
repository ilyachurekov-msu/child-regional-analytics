import pytest
from app.etl.adapters import lipetsk_table

# Synthetic layout fixture, deliberately not official statistical observations.
TEXT = """Липецкая область
Естественное движение населения за январь – декабрь
Человек
2022 2023
Число родившихся 10 12
Число умерших 15 16
Естественная убыль населения -5 -4
Число браков 8 9
Число разводов 3 4
"""
SPEC = {"region_id": "RU-48", "years": [2022, 2023], "published_at": None}


def test_adapter_checks_definition_and_natural_change():
    rows = lipetsk_table(TEXT, SPEC)
    assert len(rows) == 10
    assert rows[0]["unit"] == "человек"
    assert rows[3]["unit"] == "единиц"
    assert rows[0]["published_at"] is None
    for invalid in (
        TEXT.replace("2022 2023", "2021 2023"),
        TEXT.replace("-5 -4", "-6 -4"),
        TEXT.replace("Человек", "На 1000 жителей"),
        TEXT + "Число браков 8 9\n",
    ):
        with pytest.raises(ValueError):
            lipetsk_table(invalid, SPEC)

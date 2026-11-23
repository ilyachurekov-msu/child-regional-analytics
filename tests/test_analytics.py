from decimal import Decimal
import pytest
from app.services.analytics import change, construct_index, deviations


def test_changes_are_percent_not_percentage_points():
    assert change(Decimal("10"), Decimal("15")) == {
        "absolute_change": Decimal("5"),
        "relative_change_percent": Decimal("50"),
    }
    assert change(0, 2)["relative_change_percent"] is None
    assert change(None, 2)["absolute_change"] is None
    assert change(-10, -5)["relative_change_percent"] == 50


def test_aggregates_not_used_as_subjects_or_invented():
    rows = [
        {"region_id": "RU-77", "value": Decimal(10)},
        {"region_id": "RU-78", "value": Decimal(30)},
        {"region_id": "FD-01", "value": Decimal(999)},
        {"region_id": "RU-50", "value": None},
    ]
    result = deviations(rows, "negative")
    assert len(result) == 2
    assert all(r["median"] == 20 for r in result)
    assert all(r["difference_from_russia"] is None for r in result)
    rows.append({"region_id": "RU", "value": Decimal(500)})
    result = deviations(rows, "negative")
    assert result[0]["difference_from_russia"] == -470
    assert result[0]["median"] == 20


def test_index_requires_complete_valid_comparable_input():
    with pytest.raises(ValueError):
        construct_index({"a": {"x": 1}, "b": {"x": 1}}, {"x": 1}, {"x": "positive"})
    with pytest.raises(ValueError):
        construct_index({"a": {"x": 1}, "b": {"x": 2}}, {"x": 0}, {"x": "positive"})
    result = construct_index(
        {"a": {"x": 1, "y": 4}, "b": {"x": 3, "y": 2}, "c": {"x": None, "y": 3}},
        {"x": 1, "y": 1},
        {"x": "positive", "y": "negative"},
    )
    assert result == {"a": 0, "b": 100, "c": None}

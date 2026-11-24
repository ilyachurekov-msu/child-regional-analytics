from sqlalchemy import select, func
from app.models.entities import Value
from scripts.load_press_release import load_press_release


def test_official_country_fact_is_idempotent_and_keeps_missing_timestamp(session):
    batch = load_press_release(session)
    assert not batch.errors and batch.original_checksum is None
    value = session.scalar(select(Value).where(Value.region_id == 'RU'))
    assert str(value.period_start) == '2024-01-01' and value.value == 1222408
    assert value.published_at is None and value.data_status == 'provisional'
    assert load_press_release(session).batch_id == batch.batch_id
    assert session.scalar(select(func.count()).select_from(Value)) == 1

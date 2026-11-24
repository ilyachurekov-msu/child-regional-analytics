"""Correct standalone dictionary coverage for the inspected 2018 annual series."""
import os
from alembic import op

revision = '0004'
down_revision = '0003'


def upgrade():
    if os.getenv('CORE_MANAGED_EXTERNALLY', 'false').lower() != 'true':
        op.execute("UPDATE core.regions SET valid_from=DATE '2018-01-01' WHERE region_id='RU-42' AND valid_from=DATE '2018-11-03'")


def downgrade():
    if os.getenv('CORE_MANAGED_EXTERNALLY', 'false').lower() != 'true':
        from sqlalchemy import text
        count = op.get_bind().scalar(text("SELECT count(*) FROM regional.indicator_values WHERE region_id='RU-42' AND period_start < DATE '2018-11-03'"))
        if count:
            raise RuntimeError('Coverage rollback would invalidate existing observations; reconcile them first')
        op.execute("UPDATE core.regions SET valid_from=DATE '2018-11-03' WHERE region_id='RU-42' AND valid_from=DATE '2018-01-01'")

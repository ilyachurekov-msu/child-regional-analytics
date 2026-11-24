"""Add four application profile identifiers without changing existing keys."""
import os
from alembic import op
from sqlalchemy import text

revision = "0005"
down_revision = "0004"

REGIONS = (
    ("RU-80", "Донецкая Народная Республика"),
    ("RU-81", "Луганская Народная Республика"),
    ("RU-84", "Херсонская область"),
    ("RU-85", "Запорожская область"),
)


def upgrade():
    if os.getenv("CORE_MANAGED_EXTERNALLY", "false").lower() == "true":
        return
    for region_id, name in REGIONS:
        existing = op.get_bind().scalar(text("SELECT name FROM core.regions WHERE region_id=:id"), {"id": region_id})
        if existing is not None and existing != name:
            raise RuntimeError("Profile region ID collision: " + region_id)
        op.get_bind().execute(text(
            "INSERT INTO core.regions (region_id,name,federal_district,valid_from) "
            "VALUES (:id,:name,'',DATE '2023-01-01') ON CONFLICT (region_id) DO NOTHING"
        ), {"id": region_id, "name": name})


def downgrade():
    # Additive reference data remains: deleting stable keys could break consumers
    # or preexisting operator-owned records. Explicit reconciliation is required.
    pass

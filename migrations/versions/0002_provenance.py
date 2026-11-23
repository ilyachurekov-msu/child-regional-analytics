"""Record original-source provenance and unknown publication dates honestly."""

from alembic import op
import sqlalchemy as sa

revision = "0002"
down_revision = "0001"


def upgrade():
    op.add_column(
        "import_batches",
        sa.Column("original_checksum", sa.String(64), nullable=True),
        schema="regional",
    )
    op.add_column(
        "import_batches",
        sa.Column("original_path", sa.Text(), nullable=True),
        schema="regional",
    )
    op.alter_column(
        "indicator_values",
        "published_at",
        existing_type=sa.DateTime(timezone=True),
        nullable=True,
        schema="regional",
    )


def downgrade():
    # Refuse unsafe downgrade where unknown publication dates cannot be represented.
    op.alter_column(
        "indicator_values",
        "published_at",
        existing_type=sa.DateTime(timezone=True),
        nullable=False,
        schema="regional",
    )
    op.drop_column("import_batches", "original_path", schema="regional")
    op.drop_column("import_batches", "original_checksum", schema="regional")

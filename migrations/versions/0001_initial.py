"""Initial immutable schema snapshot, contract 1.0.0."""

from alembic import context, op

revision = "0001"
down_revision = None


def upgrade():
    from app.config import settings
    from migrations.schema_v1 import metadata

    bind = op.get_bind()
    if not settings().core_managed_externally:
        op.execute("CREATE SCHEMA IF NOT EXISTS core")
        metadata.create_all(
            bind,
            tables=[t for t in metadata.sorted_tables if t.schema == "core"],
            checkfirst=not context.is_offline_mode(),
        )
    op.execute("CREATE SCHEMA IF NOT EXISTS regional")
    metadata.create_all(
        bind,
        tables=[t for t in metadata.sorted_tables if t.schema == "regional"],
        checkfirst=not context.is_offline_mode(),
    )


def downgrade():
    from migrations.schema_v1 import metadata

    for table in reversed(metadata.sorted_tables):
        if table.schema == "regional":
            op.drop_table(table.name, schema="regional")
    # Shared core is deliberately retained to protect other platform modules.

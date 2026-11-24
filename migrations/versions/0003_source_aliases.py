"""Non-destructive canonical source crosswalk; no source PK is rewritten."""

from alembic import op
import sqlalchemy as sa

revision = "0003"
down_revision = "0002"


def upgrade():
    op.create_table(
        "source_aliases",
        sa.Column("canonical_source_id", sa.Uuid(), primary_key=True),
        sa.Column(
            "legacy_source_id",
            sa.Uuid(),
            sa.ForeignKey("core.sources.source_id"),
            nullable=False,
        ),
        sa.Column("method_version", sa.Text(), nullable=False),
        schema="regional",
    )
    # The app's canonical algorithm is frozen by a test vector; existing PKs remain unchanged.
    from urllib.parse import urlsplit, urlunsplit, parse_qsl, urlencode
    from uuid import UUID, uuid5

    connection = op.get_bind()
    for row in connection.execute(
        sa.text(
            "SELECT source_id, source_type, url FROM core.sources WHERE url IS NOT NULL"
        )
    ).mappings():
        parts = urlsplit(row["url"].strip())
        host = parts.hostname.encode("idna").decode().lower()
        port = parts.port
        if port and not (
            (parts.scheme == "https" and port == 443)
            or (parts.scheme == "http" and port == 80)
        ):
            host += f":{port}"
        query = sorted(
            (k, v)
            for k, v in parse_qsl(parts.query, keep_blank_values=True)
            if not k.lower().startswith("utm_") and k.lower() not in ("yclid", "fbclid")
        )
        url = urlunsplit(
            (parts.scheme.lower(), host, parts.path or "/", urlencode(query), "")
        )
        canonical = uuid5(
            UUID("72c4db98-6752-5fe0-a56d-af600628f13b"),
            f"source:{row['source_type'].strip().lower()}:{url}",
        )
        connection.execute(
            sa.text(
                "INSERT INTO regional.source_aliases (canonical_source_id,legacy_source_id,method_version) VALUES (:canonical,:legacy,:version)"
            ),
            {
                "canonical": canonical,
                "legacy": row["source_id"],
                "version": "media-compatible-1.0.0",
            },
        )


def downgrade():
    op.drop_table("source_aliases", schema="regional")

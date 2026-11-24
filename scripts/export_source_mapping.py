import json
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.db import engine
from app.models.entities import Source
from app.services.source_identity import canonical_source_uuid


def main():
    with Session(engine()) as session:
        rows = [
            {
                "legacy_source_id": str(s.source_id),
                "canonical_source_id": str(canonical_source_uuid(s.source_type, s.url)),
                "url": s.url,
            }
            for s in session.scalars(select(Source))
            if s.url
        ]
    ids = [r["canonical_source_id"] for r in rows]
    if len(ids) != len(set(ids)):
        raise ValueError(
            "Canonical collision: manual reconciliation required; no database mutation performed"
        )
    print(json.dumps(rows, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

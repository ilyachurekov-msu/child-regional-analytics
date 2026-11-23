"""Load the inspected official numerical subset, offline and idempotently."""

import hashlib
import json
from pathlib import Path
from sqlalchemy.orm import Session
from app.db import engine
from app.etl.importer import import_file


def load_bundle(session):
    root = Path("data/official")
    meta = json.loads((root / "provenance.json").read_text(encoding="utf-8"))
    path = root / "kemerovo-2022.json"
    if hashlib.sha256(path.read_bytes()).hexdigest() != meta["normalized_sha256"]:
        raise ValueError("Official subset checksum mismatch")
    rows = json.loads(path.read_text(encoding="utf-8"))
    if len(rows) != meta["observations"] or {r["region"] for r in rows} != {
        meta["region_id"]
    }:
        raise ValueError("Official subset coverage mismatch")
    batch = import_file(
        session,
        path,
        meta["source_url"],
        meta["source_name"],
        meta["publisher"],
        parser_version=meta["adapter"],
    )
    # The original was archived by the source-verification step; it is not in Git.
    # Do not invent a local raw path when importing the portable numerical subset.
    batch.original_checksum = meta["source_sha256"]
    if batch.errors or batch.status == "failed":
        raise ValueError("Official subset import failed quality checks")
    return batch


if __name__ == "__main__":
    with Session(engine()) as session, session.begin():
        batch = load_bundle(session)
        print(
            f"Official subset: batch={batch.batch_id}; rows={batch.rows_processed}; status={batch.status}"
        )

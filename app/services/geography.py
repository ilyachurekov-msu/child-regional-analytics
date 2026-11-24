import gzip
import hashlib
import json
from functools import lru_cache
from pathlib import Path


@lru_cache
def geography():
    metadata = json.loads(
        Path("data/geography-provenance.json").read_text(encoding="utf-8")
    )
    payload = gzip.decompress(Path("data/regions.geojson.gz").read_bytes())
    if hashlib.sha256(payload).hexdigest() != metadata["derived_sha256"]:
        raise ValueError("Geography checksum mismatch")
    return json.loads(payload), metadata

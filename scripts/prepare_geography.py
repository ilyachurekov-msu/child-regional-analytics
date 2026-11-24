"""Build attributed ODbL geography; never invent missing regional matches."""

import csv
import gzip
import hashlib
import json
from pathlib import Path


def main():
    raw = Path("data/raw/rus-adm1.geojson").read_bytes()
    metadata = json.loads(Path("data/raw/geo-metadata.json").read_text())
    mapping_path = Path("child-media-monitor/shared-contracts/region-mapping.csv")
    mapping = {
        r["old_region_id"]: r["region_id"]
        for r in csv.DictReader(mapping_path.open(encoding="utf-8"))
    }
    geo = json.loads(raw)
    canonical = {
        r["region_id"]
        for r in csv.DictReader(Path("contracts/regions.csv").open(encoding="utf-8"))
    }
    for feature in geo["features"]:
        code = mapping[feature["properties"]["shapeISO"]]
        if code not in canonical:
            raise ValueError("Unknown region: " + code)
        feature["properties"]["region_id"] = code
    ids = [f["properties"]["region_id"] for f in geo["features"]]
    if len(ids) != len(set(ids)):
        raise ValueError("Duplicate geographic region")
    payload = json.dumps(geo, ensure_ascii=False, separators=(",", ":")).encode()
    with gzip.GzipFile("data/regions.geojson.gz", "wb", mtime=0) as handle:
        handle.write(payload)
    metadata.update(
        original_sha256=hashlib.sha256(raw).hexdigest(),
        derived_sha256=hashlib.sha256(payload).hexdigest(),
        mapped_regions=ids,
        missing_regions=sorted(
            canonical - set(ids) - {"RU"} - {f"FD-{i:02}" for i in range(1, 9)}
        ),
        derivative="Only properties.region_id added; geometry unchanged; gzip transport",
    )
    Path("data/geography-provenance.json").write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    with Path("contracts/geography-crosswalk.csv").open(
        "w", encoding="utf-8", newline=""
    ) as handle:
        writer = csv.writer(handle)
        writer.writerow(["shapeISO", "region_id", "shapeName"])
        writer.writerows(
            (
                f["properties"]["shapeISO"],
                f["properties"]["region_id"],
                f["properties"]["shapeName"],
            )
            for f in geo["features"]
        )


if __name__ == "__main__":
    main()

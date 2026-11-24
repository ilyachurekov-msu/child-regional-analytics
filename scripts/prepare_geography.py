"""Build attributed ODbL geography; never invent missing regional matches."""

import csv
import gzip
import hashlib
import json
from pathlib import Path


def main():
    raw = Path("data/raw/rus-adm1.geojson").read_bytes()
    metadata = json.loads(Path("data/raw/geo-metadata.json").read_text())
    mapping_path = Path("contracts/geography-crosswalk.csv")
    mapping = {
        r["shapeISO"]: r["region_id"]
        for r in csv.DictReader(mapping_path.open(encoding="utf-8"))
    }
    geo = json.loads(raw)
    supplemental_raw = Path("data/raw/ukr-adm1.geojson").read_bytes()
    supplemental_metadata = json.loads(Path("data/raw/ukr-geo-metadata.json").read_text())
    supplemental_mapping = {
        "UA-43": "RU-91", "UA-40": "RU-92", "UA-14": "RU-80",
        "UA-09": "RU-81", "UA-65": "RU-84", "UA-23": "RU-85",
    }
    for feature in json.loads(supplemental_raw)["features"]:
        code = feature["properties"]["shapeISO"]
        if code in supplemental_mapping:
            mapping[code] = supplemental_mapping[code]
            geo["features"].append(feature)
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
    expected = canonical - {"RU"} - {f"FD-{i:02}" for i in range(1, 9)}
    if len(ids) != 89 or set(ids) != expected:
        raise ValueError("Geography must match all 89 dictionary subjects exactly")
    payload = json.dumps(geo, ensure_ascii=False, separators=(",", ":")).encode()
    base_payload = json.dumps({**geo, "features": geo["features"][:83]}, ensure_ascii=False, separators=(",", ":")).encode()
    supplement_payload = json.dumps({"type": "FeatureCollection", "features": geo["features"][83:]}, ensure_ascii=False, separators=(",", ":")).encode()
    with gzip.GzipFile("data/regions.geojson.gz", "wb", mtime=0) as handle:
        handle.write(base_payload)
    with gzip.GzipFile("data/profile89-supplement.geojson.gz", "wb", mtime=0) as handle:
        handle.write(supplement_payload)
    metadata.update(
        original_sha256=hashlib.sha256(raw).hexdigest(),
        derived_sha256=hashlib.sha256(payload).hexdigest(),
        base_derived_sha256=hashlib.sha256(base_payload).hexdigest(),
        supplement_derived_sha256=hashlib.sha256(supplement_payload).hexdigest(),
        mapped_regions=ids,
        missing_regions=sorted(
            canonical - set(ids) - {"RU"} - {f"FD-{i:02}" for i in range(1, 9)}
        ),
        derivative="Only properties.region_id added; geometry unchanged; gzip transport",
        profile="89-region application profile, names checked against owner DataLens",
        datalens_audit={
            "dataset_id": "066oulh5srlmj", "workbook_id": "ioo46sefq9521",
            "url": "https://datalens.ru/datasets/066oulh5srlmj-rossiya-geometriya-regionov-i-uchrezhdeniya",
            "checked_on": "2026-11-24", "distinct_region_names": 89,
            "mode": "Read-only queries through an unsaved temporary table; no objects saved or updated",
            "original_file": "native_map.csv", "original_geometry_license": "unknown to owner",
            "reuse": "Names/profile only; original DataLens coordinates are not redistributed",
        },
        sources=[
            {**metadata, "shapeGroup": "RUS", "features_selected": 83,
             "url": metadata["simplifiedGeometryGeoJSON"], "sha256": hashlib.sha256(raw).hexdigest()},
            {**supplemental_metadata, "shapeGroup": "UKR", "features_selected": 6,
             "url": supplemental_metadata["simplifiedGeometryGeoJSON"],
             "sha256": hashlib.sha256(supplemental_raw).hexdigest(),
             "license": supplemental_metadata["boundaryLicense"],
             "source_codes": list(supplemental_mapping)},
        ],
        classification_note="Source shapeISO/shapeGroup and geometries are retained unchanged. Application region_id is a crosswalk, not an ISO reclassification. Boundary epoch is 2017; matching 89 profile entries does not establish current boundary accuracy or statistical coverage.",
    )
    metadata.update(boundaryID="application-profile-89-2026-11-24", boundaryISO=None,
                    boundaryName="89-element application profile", admUnitCount="89",
                    original_sha256_scope="RUS source; all source checksums are listed under sources")
    for key in list(metadata):
        if key.startswith(("mean", "min", "max")):
            del metadata[key]
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

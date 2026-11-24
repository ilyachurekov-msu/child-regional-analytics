import csv
import json
import hashlib
from pathlib import Path
from decimal import Decimal
import pytest
from app.services.geography import geography
from app.etl.comparability import validate_series
from app.services.source_identity import canonical_source_uuid


def test_geography_is_attributed_mapped_and_incomplete_honestly():
    geo, meta = geography()
    ids = [f["properties"]["region_id"] for f in geo["features"]]
    assert len(set(ids)) == len(ids) == 83
    assert meta["boundaryYearRepresented"] == "2017"
    assert meta["boundaryLicense"] == "Open Data Commons Open Database License 1.0"
    assert set(meta["missing_regions"]) == {"RU-91", "RU-92"}
    known = {
        r["region_id"]
        for r in csv.DictReader(Path("contracts/regions.csv").open(encoding="utf-8"))
    }
    assert set(ids) <= known
    assert all(
        f["geometry"]["type"] in ("Polygon", "MultiPolygon") for f in geo["features"]
    )


def test_official_extension_has_no_imputation():
    meta = json.loads(Path('data/official/provenance-v02.json').read_text(encoding='utf-8'))
    payload = Path('data/official/kemerovo-2018-2022.json').read_bytes().replace(b'\r\n', b'\n')
    assert hashlib.sha256(payload).hexdigest() == meta['normalized_sha256']
    rows = json.loads(
        Path("data/official/kemerovo-2018-2022.json").read_text(encoding="utf-8")
    )
    assert len(rows) == 25
    validate_series(rows, {"years": list(range(2018, 2023))})
    for year in range(2018, 2023):
        values = {
            r["indicator_code"]: Decimal(r["value"])
            for r in rows
            if r["period_start"] == f"{year}-01-01"
        }
        assert values["births"] - values["deaths"] == values["natural_change"]
    altered = [dict(rows[0], unit="на 1000 населения")]
    with pytest.raises(ValueError):
        validate_series(altered, {"years": [2018]})


def test_canonical_source_identity_matches_media_procedure():
    from uuid import UUID, uuid5

    expected = uuid5(
        UUID("72c4db98-6752-5fe0-a56d-af600628f13b"),
        "source:rss:https://example.org/feed",
    )
    assert (
        canonical_source_uuid("rss", "https://Example.org:443/feed?utm_source=x#y")
        == expected
    )

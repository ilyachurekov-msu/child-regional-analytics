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
    if hashlib.sha256(payload).hexdigest() != metadata["base_derived_sha256"]:
        raise ValueError("Geography checksum mismatch")
    geo = json.loads(payload)
    supplement = gzip.decompress(Path("data/profile89-supplement.geojson.gz").read_bytes())
    if hashlib.sha256(supplement).hexdigest() != metadata["supplement_derived_sha256"]:
        raise ValueError("Geography supplement checksum mismatch")
    geo["features"].extend(json.loads(supplement)["features"])
    combined = json.dumps(geo, ensure_ascii=False, separators=(",", ":")).encode()
    if hashlib.sha256(combined).hexdigest() != metadata["derived_sha256"]:
        raise ValueError("Combined geography checksum mismatch")
    return geo, metadata


@lru_cache
def plotly_geography():
    """D3 spherical polygons need clockwise exteriors, opposite RFC7946 winding."""
    import copy
    geo, metadata = geography()
    display = copy.deepcopy(geo)
    for feature in display['features']:
        geometry = feature['geometry']
        polygons = [geometry['coordinates']] if geometry['type'] == 'Polygon' else geometry['coordinates']
        for polygon in polygons:
            for index, ring in enumerate(polygon):
                clockwise = sum((b[0] - a[0]) * (b[1] + a[1]) for a, b in zip(ring, ring[1:])) > 0
                if clockwise != (index == 0):
                    polygon[index] = list(reversed(ring))
    return display, metadata

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

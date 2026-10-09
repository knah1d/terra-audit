"""
District lookup for field boundaries.

data/bgd_districts.geojson holds the 64 Bangladesh districts (ADM2) from
geoBoundaries gbOpen BGD ADM2, simplified release — source: Bangladesh
Bureau of Statistics (BBS) / OCHA ROAP, licensed CC BY 3.0 IGO. Only the
district name and geometry are kept, coordinates rounded to 5 decimals.
"""

import json
from functools import lru_cache
from pathlib import Path

from shapely.geometry import shape
from shapely.ops import unary_union

_DISTRICTS_PATH = Path(__file__).parent / "data" / "bgd_districts.geojson"


@lru_cache(maxsize=1)
def _districts():
    """Loaded on first use, not at import time, so importing the API never
    touches the filesystem (see tests/backend/test_import_hygiene.py)."""
    with open(_DISTRICTS_PATH, encoding="utf-8") as f:
        data = json.load(f)
    return [(feat["properties"]["name"], shape(feat["geometry"])) for feat in data["features"]]


def _to_shape(geojson: dict):
    """Accepts a FeatureCollection, Feature, or bare geometry — new fields
    arrive as a Feature, stored fields are a FeatureCollection."""
    t = geojson.get("type")
    if t == "FeatureCollection":
        return unary_union([shape(f["geometry"]) for f in geojson.get("features", [])])
    if t == "Feature":
        return shape(geojson["geometry"])
    return shape(geojson)


def detect_district(geojson: dict) -> str | None:
    """
    Name of the district the field boundary falls in, or None if it lies
    outside Bangladesh. A boundary that straddles districts is assigned to
    the one it overlaps most.
    """
    field = _to_shape(geojson)
    if field.is_empty:
        return None
    if not field.is_valid:
        field = field.buffer(0)
    best_name, best_overlap = None, 0.0
    for name, district in _districts():
        if not district.intersects(field):
            continue
        overlap = district.intersection(field).area
        if overlap > best_overlap:
            best_name, best_overlap = name, overlap
    return best_name

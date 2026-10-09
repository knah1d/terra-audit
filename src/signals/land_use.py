"""
Observed land use of a field boundary — shown as "Field Type" in the UI and
kept separate from `field_type`, which is the methodology (VM0051 rice AWD
vs VM0042 cropland ALM) the field is enrolled under. Land use is a fact
about the land; methodology is a project decision, so this only ever
*suggests* a methodology and never sets one.

Rule-based, no ML model:
  1. ESA WorldCover 2021: if under half the polygon is cropland (or
     herbaceous wetland, where seasonally flooded paddies can land), the
     field is `non_cropland`.
  2. Sentinel-1 VH over the last 12 months (the same descending-pass,
     polygon-median series signal runs use): a rice season shows as open
     water at flooding/transplanting (very low VH) followed by a strong VH
     rise as the canopy grows. Any such season -> `rice_paddy`, otherwise
     `upland_cropland`.

The thresholds below are an uncalibrated heuristic — they have not been
validated against independently labelled fields, which is why the result
is overridable and stored with its evidence and source.
"""

from datetime import date, datetime, timedelta
from functools import lru_cache
import json

import pandas as pd

LAND_USE_VALUES = ("rice_paddy", "rice_rotation", "upland_cropland", "non_cropland")

METHOD = "worldcover_s1_vh_flood_growth_v1"
WINDOW_DAYS = 365
MIN_OBSERVATIONS = 10
CROPLAND_CLASSES = (40, 90)        # WorldCover cropland, herbaceous wetland
CROPLAND_MIN_FRACTION = 0.5
FLOOD_VH_DB = -20.0                # open water at flooding/transplanting
GROWTH_RISE_DB = 5.0               # VH rise from flood to canopy
GROWTH_MIN_DAYS = 20
GROWTH_MAX_DAYS = 100
EPISODE_GAP_DAYS = 60              # floods closer than this are one season

WORLDCOVER_NAMES = {
    10: "tree cover", 20: "shrubland", 30: "grassland", 40: "cropland",
    50: "built-up", 60: "bare / sparse vegetation", 70: "snow and ice",
    80: "permanent water", 90: "herbaceous wetland", 95: "mangroves",
    100: "moss and lichen",
}


def _rice_seasons(df: pd.DataFrame) -> list[dict]:
    """Flood-then-growth episodes in a (date, vh) series."""
    obs = [
        (datetime.strptime(d, "%Y-%m-%d").date(), float(vh))
        for d, vh in zip(df["date"], df["vh"])
    ]
    seasons = []
    for flood_date, flood_vh in obs:
        if flood_vh >= FLOOD_VH_DB:
            continue
        if seasons and (flood_date - seasons[-1]["_flood_date"]).days <= EPISODE_GAP_DAYS:
            continue
        later = [
            (d, vh) for d, vh in obs
            if GROWTH_MIN_DAYS <= (d - flood_date).days <= GROWTH_MAX_DAYS
        ]
        if not later:
            continue
        peak_date, peak_vh = max(later, key=lambda o: o[1])
        if peak_vh - flood_vh >= GROWTH_RISE_DB:
            seasons.append({
                "_flood_date": flood_date,
                "flood_date": flood_date.isoformat(), "flood_vh_db": round(flood_vh, 2),
                "peak_date": peak_date.isoformat(), "peak_vh_db": round(peak_vh, 2),
            })
    for s in seasons:
        del s["_flood_date"]
    return seasons


def classify_land_use(
    fractions: dict, df: pd.DataFrame, window_start: str, window_end: str,
) -> tuple[str | None, dict]:
    """
    Pure classification step (no Earth Engine). Returns (land_use, evidence);
    land_use is None when there isn't enough data to decide, with the reason
    in evidence["summary"].
    """
    evidence = {"method": METHOD, "window_start": window_start, "window_end": window_end}
    if not fractions:
        evidence["summary"] = "No land-cover data inside the boundary."
        return None, evidence

    cropland = sum(fractions.get(c, 0.0) for c in CROPLAND_CLASSES)
    dominant = max(fractions, key=fractions.get)
    evidence["cropland_fraction"] = round(cropland, 3)
    evidence["dominant_land_cover"] = WORLDCOVER_NAMES.get(dominant, str(dominant))
    if cropland < CROPLAND_MIN_FRACTION:
        evidence["summary"] = (
            f"Mostly {evidence['dominant_land_cover']} — only {cropland:.0%} cropland "
            f"detected."
        )
        return "non_cropland", evidence

    n_obs = 0 if df.empty else len(df)
    evidence["observations"] = n_obs
    if n_obs < MIN_OBSERVATIONS:
        evidence["summary"] = (
            f"Only {n_obs} Sentinel-1 observations in the last 12 months — "
            "too few to tell rice from other crops."
        )
        return None, evidence

    seasons = _rice_seasons(df)
    evidence["rice_seasons"] = seasons
    if seasons:
        dates = ", ".join(s["flood_date"] for s in seasons)
        evidence["summary"] = (
            f"Rice flooding-then-growth pattern in Sentinel-1 VH "
            f"({len(seasons)} season{'s' if len(seasons) > 1 else ''}, flooded {dates})."
        )
        return "rice_paddy", evidence
    evidence["summary"] = (
        f"Cropland ({cropland:.0%}, detected) with no rice flooding pattern "
        f"in {n_obs} Sentinel-1 observations over the last 12 months."
    )
    return "upland_cropland", evidence


@lru_cache(maxsize=256)
def _detect_cached(engine, geometry_json: str, today: date) -> tuple[str | None, str]:
    """Cached per geometry per day, so the registration request re-checking
    what the form just detected doesn't hit Earth Engine twice. Exceptions
    are not cached."""
    geometry = json.loads(geometry_json)
    window_end = today.isoformat()
    window_start = (today - timedelta(days=WINDOW_DAYS)).isoformat()
    fractions = engine.land_cover_fractions(geometry)
    cropland = sum(fractions.get(c, 0.0) for c in CROPLAND_CLASSES)
    # Skip the slower Sentinel-1 query when WorldCover already decides it.
    if fractions and cropland >= CROPLAND_MIN_FRACTION:
        df = engine.extract_clean_timeseries(geometry, window_start, window_end)
    else:
        df = pd.DataFrame()
    land_use, evidence = classify_land_use(fractions, df, window_start, window_end)
    return land_use, json.dumps(evidence)


def detect_land_use(engine, geojson: dict) -> tuple[str | None, dict]:
    """Detects land use for a Feature/FeatureCollection/geometry via Earth
    Engine. Raises if Earth Engine fails — callers decide the fallback."""
    land_use, evidence_json = _detect_cached(
        engine, json.dumps(geojson, sort_keys=True), date.today(),
    )
    return land_use, json.loads(evidence_json)

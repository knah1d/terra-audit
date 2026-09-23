"""Shared retrospective Sentinel observations; no crop or practice inference.

Scene-level values and identifiers are retained. Optical indices use a
20 m grid because SWIR and SCL are native 20 m bands. Quality cutoffs are
engineering screens, not scientifically validated accuracy thresholds.
"""
from datetime import date, datetime, timedelta, timezone

import ee

from src.processing import MULTICROP_VERSION

S1_COLLECTION = "COPERNICUS/S1_GRD"
S2_COLLECTION = "COPERNICUS/S2_SR_HARMONIZED"


def geometry_of(value):
    if "features" in value:
        return value["features"][0]["geometry"]
    return value.get("geometry", value)


def quality_summary(observations, start, end):
    start, end = date.fromisoformat(start), date.fromisoformat(end)
    by_sensor = {}
    for sensor in ("sentinel1", "sentinel2"):
        usable = [r for r in observations if r["sensor"] == sensor and r["valid_fraction"] >= 0.5]
        days = sorted({date.fromisoformat(r["date"]) for r in usable})
        bounds = [start, *days, end]
        gap = max((b - a).days for a, b in zip(bounds, bounds[1:]))
        by_sensor[sensor] = {"usable_dates": len(days), "max_gap_days": gap}
    warnings = []
    if any(v["usable_dates"] < 5 for v in by_sensor.values()):
        warnings.append("Fewer than five usable dates for one or more sensors")
    if any(v["max_gap_days"] > 30 for v in by_sensor.values()):
        warnings.append("An observation gap exceeds 30 days")
    return {"sensors": by_sensor, "warnings": warnings,
            "status": "insufficient_evidence" if warnings else "ready_for_exploration",
            "note": "Coverage screens only; neither status establishes crop or practice accuracy."}


def extract_observations(geometry, start, end):
    geom = ee.Geometry(geometry_of(geometry))
    # User-facing periods include the end date; Earth Engine excludes it.
    stop = (date.fromisoformat(end) + timedelta(days=1)).isoformat()

    def summarize(img, bands, scale, sensor):
        stats = img.select(bands).reduceRegion(ee.Reducer.median(), geom, scale, maxPixels=1e7)
        valid = img.select(bands[0]).mask().unmask(0, sameFootprint=False).reduceRegion(
            ee.Reducer.mean(), geom, scale, maxPixels=1e7).get(bands[0])
        return ee.Feature(None, stats).set({"time": img.get("system:time_start"),
            "scene_id": img.get("system:index"), "sensor": sensor, "valid_fraction": valid,
            "relative_orbit": img.get("relativeOrbitNumber_start") if sensor == "sentinel1" else None})

    s1 = (ee.ImageCollection(S1_COLLECTION).filterBounds(geom).filterDate(start, stop)
          .filter(ee.Filter.eq("instrumentMode", "IW"))
          .filter(ee.Filter.eq("orbitProperties_pass", "DESCENDING"))
          .filter(ee.Filter.listContains("transmitterReceiverPolarisation", "VV"))
          .filter(ee.Filter.listContains("transmitterReceiverPolarisation", "VH")))

    def radar(img):
        vv, vh = img.select("VV"), img.select("VH")
        vp, hp = ee.Image.constant(10).pow(vv.divide(10)), ee.Image.constant(10).pow(vh.divide(10))
        bands = vv.rename("vv").addBands(vh.rename("vh")).addBands(
            hp.multiply(4).divide(vp.add(hp)).rename("rvi"))
        return bands.copyProperties(img, ["system:time_start", "system:index", "relativeOrbitNumber_start"])

    s2 = ee.ImageCollection(S2_COLLECTION).filterBounds(geom).filterDate(start, stop)

    def optical(img):
        scl = img.select("SCL")
        clear = scl.eq(4).Or(scl.eq(5)).Or(scl.eq(6))
        reflectance = img.select(["B2", "B3", "B4", "B8", "B11", "B12"]).multiply(0.0001).updateMask(clear)
        ndvi = reflectance.normalizedDifference(["B8", "B4"]).rename("ndvi")
        ndmi = reflectance.normalizedDifference(["B8", "B11"]).rename("ndmi")
        ndti = reflectance.normalizedDifference(["B11", "B12"]).rename("ndti")
        return reflectance.addBands([ndvi, ndmi, ndti]).copyProperties(img, ["system:time_start", "system:index"])

    collections = [s1.map(radar).map(lambda img: summarize(img, ["vv", "vh", "rvi"], 10, "sentinel1")),
                   s2.map(optical).map(lambda img: summarize(img, ["B2", "B3", "B4", "B8", "B11", "B12", "ndvi", "ndmi", "ndti"], 20, "sentinel2"))]
    observations = []
    for collection in collections:
        for feature in collection.getInfo()["features"]:
            row = feature["properties"]
            row["date"] = datetime.fromtimestamp(row.pop("time") / 1000, timezone.utc).date().isoformat()
            row["valid_fraction"] = float(row.get("valid_fraction") or 0)
            observations.append(row)
    observations.sort(key=lambda r: (r["date"], r["sensor"], r["scene_id"]))
    return {"processing_version": MULTICROP_VERSION, "sources": [S1_COLLECTION, S2_COLLECTION],
            "window_start": start, "window_end": end, "observations": observations,
            "quality": quality_summary(observations, start, end),
            "limitations": ["Retrospective seasonal observations, not a validated crop classifier",
                            "No weather inputs in this processing version",
                            "Small fields and mixed pixels require local validation"]}

import ee
import pandas as pd
from datetime import datetime, timezone
from scipy.signal import savgol_filter


class SpatialDataEngine:
    def __init__(self):
        try:
            ee.Initialize()
        except Exception as e:
            raise RuntimeError(f"Earth Engine Initialization Failed: {e}")

    def extract_clean_timeseries(
        self, geojson_geometry: dict, start_date: str, end_date: str
    ) -> pd.DataFrame:
        """
        Fetches Sentinel-1 GRD time-series for a polygon and returns a clean
        DataFrame with VV, VH, CROSS_RATIO, RVI, and Savitzky-Golay smoothed
        columns.  All timestamps are resolved in UTC to avoid local-timezone
        date-shift artefacts.
        """
        # -- Geometry normalisation -------------------------------------------
        if "features" in geojson_geometry:
            geom_dict = geojson_geometry["features"][0]["geometry"]
        elif "geometry" in geojson_geometry:
            geom_dict = geojson_geometry["geometry"]
        else:
            geom_dict = geojson_geometry

        ee_geometry = ee.Geometry(geom_dict)

        # -- Image Collection -----------------------------------------------
        # DESCENDING pass only → avoids sawtooth artefacts from mixed orbits
        s1_stack = (
            ee.ImageCollection("COPERNICUS/S1_GRD")
            .filterBounds(ee_geometry)
            .filterDate(start_date, end_date)
            .filter(ee.Filter.eq("instrumentMode", "IW"))
            .filter(ee.Filter.eq("orbitProperties_pass", "DESCENDING"))
            .filter(ee.Filter.listContains("transmitterReceiverPolarisation", "VV"))
            .filter(ee.Filter.listContains("transmitterReceiverPolarisation", "VH"))
        )

        # -- Band computation ------------------------------------------------
        def calculate_indices(img):
            vv = img.select("VV")
            vh = img.select("VH")
            cross_ratio = vh.subtract(vv).rename("CROSS_RATIO")
            # Radar Vegetation Index (RVI) — sensitive to crop biomass
            rvi = vh.multiply(4).divide(vh.add(vv)).rename("RVI")
            return img.addBands([cross_ratio, rvi]).select(
                ["VV", "VH", "CROSS_RATIO", "RVI"]
            )

        processed_stack = s1_stack.map(calculate_indices)

        # -- Spatial reduction -----------------------------------------------
        def reduce_region(img):
            stats = img.reduceRegion(
                reducer=ee.Reducer.median(),   # robust to speckle outliers
                geometry=ee_geometry,
                scale=10,
                maxPixels=1e9,                 # safe for large polygons
            )
            return ee.Feature(None, stats).set(
                "system:time_start", img.get("system:time_start")
            )

        reduced = processed_stack.map(reduce_region).getInfo()

        # -- Parse results ---------------------------------------------------
        records = []
        for feat in reduced["features"]:
            props = feat["properties"]
            # Guard: skip any image where any band returned null
            if not all(props.get(k) is not None for k in ["VV", "VH", "CROSS_RATIO", "RVI"]):
                continue
            # Use UTC to avoid local-timezone date-shift at midnight boundaries
            ts_ms = props["system:time_start"]
            date_str = datetime.fromtimestamp(
                ts_ms / 1000.0, tz=timezone.utc
            ).strftime("%Y-%m-%d")
            records.append(
                {
                    "date": date_str,
                    "vv": props["VV"],
                    "vh": props["VH"],
                    "cross_ratio": props["CROSS_RATIO"],
                    "rvi": props["RVI"],
                }
            )

        df = pd.DataFrame(records)
        if df.empty:
            return df

        df = (
            df.sort_values("date")
            .drop_duplicates(subset=["date"])
            .reset_index(drop=True)
        )

        # -- Savitzky-Golay smoothing ----------------------------------------
        # Requires ≥ window_length (5) observations; fallback to raw otherwise
        if len(df) >= 5:
            df["vv_smoothed"] = savgol_filter(df["vv"], window_length=5, polyorder=2)
            df["vh_smoothed"] = savgol_filter(df["vh"], window_length=5, polyorder=2)
        else:
            df["vv_smoothed"] = df["vv"]
            df["vh_smoothed"] = df["vh"]

        return df

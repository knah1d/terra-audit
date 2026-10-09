"""Ricemapper handcrafted (HC) Sentinel-1 features for the external AWD model.

The feature functions below are ported from microsoft/rice-irrigation-mapping-s1s2
(ricemapper/utils/utils.py: generate_s1_spline, find_troughs_and_crests,
count_inflection_points, find_min_max_mean_stdev, _normalize_ratios, and
scripts/train/train.py: _generate_handcrafted_features_batch) with the exact
parameters used for the published AWD-task features
(data/features/06-01_09-05_f4d/train_HC.parquet), so that inference computes
the same 61 features the model was trained on.

    Copyright (c) Microsoft Corporation. Licensed under the MIT License.

Behaviour is kept as published, including quirks (e.g. db_to_linear applied to
an already-linear VV/VH ratio before the gaussian fit) — changing them would
change the features the model expects.

Known input differences vs the published training data (documented, not
silently assumed away): training used ESA SNAP gamma0 with a multi-temporal
Refined Lee speckle filter over Punjab (2024); extract_ascending_gamma0()
uses Earth Engine COPERNICUS/S1_GRD_FLOAT sigma0 converted to gamma0 via the
ellipsoid incidence angle, without a speckle filter (the polygon mean
averages speckle but is not identical).
"""
from datetime import date, datetime

import numpy as np
import pandas as pd
from scipy.interpolate import CubicSpline
from scipy.ndimage import gaussian_filter1d
from scipy.optimize import curve_fit
from scipy.signal import find_peaks

FEATURE_VERSION = "ricemapper-hc-ascending-v1"
ORBIT = "ASCENDING"
# One of the two published research windows. With handcrafted features only,
# Jun 1 – Sep 5 scored higher in repeated nested cross-validation than the
# May 1 – Dec 15 window the paper prefers for its HC+Presto AWD model.
WINDOW_MONTH_DAY = ((6, 1), (9, 5))
K = 3
SPLINE_SIGMA = 0.5
RATIO_SMOOTHING_SIGMA = 10
MIN_OBSERVATIONS = 4
VARIABLES = [f"VV_{ORBIT}_mean_spline", f"VH_{ORBIT}_mean_spline", f"{ORBIT}_spline_ratio"]
_EPOCH = pd.Timestamp("1970-01-01")  # matplotlib>=3.3 date2num epoch (research pinned 3.8)


def research_window(today: date) -> tuple[str, str]:
    """Most recent complete research window (Jun 1 – Sep 5) on or before `today`."""
    (sm, sd), (em, ed) = WINDOW_MONTH_DAY
    year = today.year if today >= date(today.year, em, ed) else today.year - 1
    return date(year, sm, sd).isoformat(), date(year, em, ed).isoformat()


def _db_to_linear(ts):
    return 10 ** (np.asarray(ts) / 10)


def _normalize_ratios(ts_ratio, ignore_sections=(1, 1)):
    middle = ts_ratio[ignore_sections[0]:-ignore_sections[1]]
    min_val, max_val = np.min(middle), np.max(middle)
    normalized = [(y - min_val) / (max_val - min_val + 1e-6) for y in middle]
    return np.concatenate((
        [normalized[0]] * ignore_sections[0], normalized, [normalized[-1]] * ignore_sections[1],
    ))


def _gaussian(x, a, b, c):
    return a * np.exp(-((x - b) ** 2) / (2 * c**2))


def _r_squared(y, y_pred):
    ss_res = np.sum((y - y_pred) ** 2)
    ss_tot = np.sum((y - np.mean(y)) ** 2)
    return 1 - (ss_res / (ss_tot + 1e-6))


def _count_inflection_points(ts):
    if len(ts) < 3:
        return 0
    return int(np.sum(np.diff(np.sign(np.diff(np.diff(ts)))) != 0))


def _splines(dates, vv, vh, start, end):
    """generate_s1_spline(mode="temporal_smoothing", sigma=0.5, convert_to_db=False)."""
    start, end = pd.to_datetime(start), pd.to_datetime(end)
    date_range = pd.date_range(start=start, end=end, freq="D")
    x_smooth = (date_range - start).days.values
    x = (pd.to_datetime(list(dates)) - start).days.values
    vv_s = CubicSpline(x, gaussian_filter1d(np.asarray(vv, float), SPLINE_SIGMA))(x_smooth)
    vh_s = CubicSpline(x, gaussian_filter1d(np.asarray(vh, float), SPLINE_SIGMA))(x_smooth)
    ratio = np.array([a / (b + 1e-9) for a, b in zip(vv_s, vh_s)])
    out = {VARIABLES[0]: vv_s, VARIABLES[1]: vh_s, VARIABLES[2]: ratio}

    gaussian = {f"{ORBIT}_ratio_gaussian_{k}": np.nan for k in "abc"}
    gaussian[f"{ORBIT}_ratio_gaussian_r2"] = np.nan
    normed = _normalize_ratios(_db_to_linear(ratio))
    if not (np.isnan(normed).any() or np.isinf(normed).any()):
        smooth = gaussian_filter1d(normed, RATIO_SMOOTHING_SIGMA)
        date_nums = ((date_range - _EPOCH) / pd.Timedelta(days=1)).values.astype(float)
        try:
            popt, _ = curve_fit(_gaussian, date_nums, smooth,
                                p0=[1, np.mean(date_nums), np.std(date_nums)])
            r2 = _r_squared(smooth, _gaussian(date_nums, *popt))
            a, b, c = popt[0], popt[1] - date_nums[0], popt[2]
        except RuntimeError:
            a, b, c, r2 = 0, 0, 0, 0
        gaussian = {f"{ORBIT}_ratio_gaussian_a": a, f"{ORBIT}_ratio_gaussian_b": b,
                    f"{ORBIT}_ratio_gaussian_c": c, f"{ORBIT}_ratio_gaussian_r2": r2}
    return out, list(date_range), gaussian


def _troughs_and_crests(series, dates, start):
    """find_troughs_and_crests(k=3) — values relative to the season mean,
    days since window start, missing slots padded with 0 / max_days."""
    start = pd.to_datetime(start)
    max_days = (pd.to_datetime(dates[-1]) - start).days
    results = {}
    for var in VARIABLES:
        ts = np.asarray(series[var])
        season_avg = np.mean(ts)
        crests, _ = find_peaks(ts)
        troughs, _ = find_peaks(-ts)
        num_crests, num_troughs = len(crests), len(troughs)
        crests, troughs = crests[:K], troughs[:K]
        crest_days = [(pd.to_datetime(dates[i]) - start).days for i in crests]
        trough_days = [(pd.to_datetime(dates[i]) - start).days for i in troughs]
        crest_vals = [ts[i] - season_avg for i in crests]
        trough_vals = [ts[i] - season_avg for i in troughs]
        crest_vals += [0] * (K - len(crest_vals))
        trough_vals += [0] * (K - len(trough_vals))
        crest_days += [max_days] * (K - len(crest_days))
        trough_days += [max_days] * (K - len(trough_days))
        for i in range(K):
            results[f"{var}_troughs_values_{i+1}"] = trough_vals[i]
            results[f"{var}_crests_values_{i+1}"] = crest_vals[i]
            results[f"{var}_trough_days_{i+1}"] = trough_days[i]
            results[f"{var}_crest_days_{i+1}"] = crest_days[i]
        results[f"{var}_num_troughs"] = num_troughs
        results[f"{var}_num_crests"] = num_crests
    return results


def feature_names() -> list[str]:
    """The 61 HC feature names, as they appear in the published parquet."""
    names = [f"{ORBIT}_ratio_gaussian_{k}" for k in ("a", "b", "c", "r2")]
    for var in VARIABLES:
        for base in ("troughs_values", "crests_values", "trough_days", "crest_days"):
            names += [f"{var}_{base}_{i + 1}" for i in range(K)]
        names += [f"{var}_num_troughs", f"{var}_num_crests"]
    for var in VARIABLES:
        names += [f"{stat}_{var}" for stat in ("inflection_points", "min", "max", "mean", "std")]
    return names


def handcrafted_features(obs: pd.DataFrame, start: str, end: str) -> dict:
    """61 HC features from an ascending-orbit series with columns
    date (YYYY-MM-DD), vv, vh — linear-power gamma0, polygon mean."""
    obs = obs.dropna(subset=["vv", "vh"]).groupby("date", as_index=False)[["vv", "vh"]].mean()
    obs = obs[(obs["date"] >= start) & (obs["date"] <= end)].sort_values("date")
    if len(obs) < MIN_OBSERVATIONS:
        raise ValueError(f"Only {len(obs)} ascending Sentinel-1 observations in {start}..{end}")
    series, dates, features = _splines(obs["date"], obs["vv"], obs["vh"], start, end)
    for var in VARIABLES:
        if np.isnan(series[var]).any() or np.isinf(series[var]).any():
            raise ValueError("Spline produced invalid values")
    features.update(_troughs_and_crests(series, dates, start))
    for var in VARIABLES:
        ts = series[var]
        features[f"inflection_points_{var}"] = _count_inflection_points(ts)
        features[f"min_{var}"], features[f"max_{var}"] = float(np.min(ts)), float(np.max(ts))
        features[f"mean_{var}"], features[f"std_{var}"] = float(np.mean(ts)), float(np.std(ts))
    return features


def extract_ascending_gamma0(geometry: dict, start: str, end: str) -> tuple[pd.DataFrame, int | None]:
    """Polygon-mean linear gamma0 (sigma0 / cos(incidence)) from the dominant
    ascending relative orbit — mixing relative orbits would mix viewing
    geometries within one series. Returns (series, relative_orbit)."""
    import ee

    if "features" in geometry:
        geometry = geometry["features"][0]["geometry"]
    elif "geometry" in geometry:
        geometry = geometry["geometry"]
    geom = ee.Geometry(geometry)
    stop = (pd.to_datetime(end) + pd.Timedelta(days=1)).strftime("%Y-%m-%d")
    collection = (
        ee.ImageCollection("COPERNICUS/S1_GRD_FLOAT").filterBounds(geom).filterDate(start, stop)
        .filter(ee.Filter.eq("instrumentMode", "IW"))
        .filter(ee.Filter.eq("orbitProperties_pass", ORBIT))
        .filter(ee.Filter.listContains("transmitterReceiverPolarisation", "VV"))
        .filter(ee.Filter.listContains("transmitterReceiverPolarisation", "VH"))
    )
    orbits = collection.aggregate_array("relativeOrbitNumber_start").getInfo()
    if not orbits:
        return pd.DataFrame(columns=["date", "vv", "vh"]), None
    relative_orbit = max(set(orbits), key=orbits.count)
    collection = collection.filter(ee.Filter.eq("relativeOrbitNumber_start", relative_orbit))

    def reduce(img):
        cos_theta = img.select("angle").multiply(np.pi / 180).cos()
        gamma0 = img.select(["VV", "VH"]).divide(cos_theta)
        stats = gamma0.reduceRegion(ee.Reducer.mean(), geom, 10, maxPixels=1e9)
        return ee.Feature(None, stats).set("time", img.get("system:time_start"))

    rows = []
    for feature in collection.map(reduce).getInfo()["features"]:
        p = feature["properties"]
        if p.get("VV") is None or p.get("VH") is None:
            continue
        rows.append({"date": datetime.utcfromtimestamp(p["time"] / 1000).strftime("%Y-%m-%d"),
                     "vv": p["VV"], "vh": p["VH"]})
    return pd.DataFrame(rows, columns=["date", "vv", "vh"]), relative_orbit

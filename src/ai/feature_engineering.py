"""
Turns the dataset builder's combined frame into an (X, y) matrix for
sklearn/xgboost.

Deliberately excludes vv_zscore, is_flooded, and drydown_event — these are
the columns the `label` is derived from, so including them would let a model
trivially memorize the threshold rule rather than learn a distinct
representation from the underlying signal.
"""

import numpy as np
import pandas as pd

LABEL_CLASSES = ["dry", "flooded", "drydown"]

_BASE_FEATURES = [
    "vv", "vh", "cross_ratio", "rvi", "vv_smoothed", "vh_smoothed", "vv_diff",
]


def _days_since_window_start(df: pd.DataFrame) -> pd.Series:
    date = pd.to_datetime(df["date"])
    window_start = pd.to_datetime(df["window_start"])
    return (date - window_start).dt.days.astype(float)


def _days_since_sowing(df: pd.DataFrame) -> pd.Series:
    """Sowing date is resolved per (field_id, window) group from the
    is_sowing marker. extract_phenology's idxmin() guarantees exactly one
    sowing row per non-empty group, so this is always defined."""
    date = pd.to_datetime(df["date"])
    out = pd.Series(np.nan, index=df.index, dtype=float)
    group_cols = ["field_id", "window_start", "window_end"]
    for _, group in df.groupby(group_cols, sort=False):
        sowing_rows = group.index[group["is_sowing"] == 1]
        if len(sowing_rows) == 0:
            continue
        sowing_date = date.loc[sowing_rows[0]]
        out.loc[group.index] = (date.loc[group.index] - sowing_date).dt.days.astype(float)
    return out


def build_features(df: pd.DataFrame, include_area_ha: bool = False) -> tuple[pd.DataFrame, pd.Series]:
    """
    df: combined frame from dataset_builder.build_dataset()/load_dataset().
    Returns (X, y): X is a numeric feature matrix, y is string labels
    (call encode_labels(y) before handing to sklearn/xgboost).
    """
    X = df[_BASE_FEATURES].copy()
    X["days_since_window_start"] = _days_since_window_start(df)
    X["days_since_sowing"] = _days_since_sowing(df)

    if include_area_ha:
        X["area_ha"] = df["area_ha"]

    # Only meaningful once a second district is cached — get_dummies with
    # drop_first naturally yields zero columns while just one exists today.
    district_dummies = pd.get_dummies(df["district"], prefix="district", drop_first=True)
    X = pd.concat([X, district_dummies], axis=1)

    y = df["label"]
    return X, y


def encode_labels(y: pd.Series) -> np.ndarray:
    """Maps to LABEL_CLASSES' fixed order — never LabelEncoder.fit(y), since
    a fold that happens to miss a class would otherwise shift integer codes."""
    return y.map(LABEL_CLASSES.index).to_numpy()

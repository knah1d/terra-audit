"""External research AWD-practice benchmark; never used for carbon accounting.

This is intentionally separate from src.ai.ml.models, whose labels come from
the AdaptiveAWDGate itself. The published Ricemapper AWD task maps AWD to 1
and PTR/DSR to 0; the latter must NOT be described as measured CF labels.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.impute import SimpleImputer
from sklearn.metrics import (
    accuracy_score, balanced_accuracy_score, confusion_matrix,
    precision_recall_fscore_support,
)
from sklearn.model_selection import GroupShuffleSplit, train_test_split
from sklearn.pipeline import Pipeline

BENCHMARK_VERSION = "external-ricemapper-practice-v1"
SOURCE_URL = "https://github.com/microsoft/rice-irrigation-mapping-s1s2"
LABEL_MAP = {"AWD": 1, "PTR": 0, "DSR": 0}
EXCLUDE = {
    "label", "class", "sn", "geometry", "latitude", "longitude",
    "lat", "lon", "lng", "district", "stratify_key", "planting_date",
    "field_id", "plot_id", "parcel_id", "farm_id", "id", "index",
    "awd", "irrigation", "target", "is_awd", "is_flooded", "drydown_event",
}
GROUP_COLUMNS = ("plot_id", "field_id", "parcel_id", "farm_id")


def checksum(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def prepare_data(frame: pd.DataFrame, *, group_column: str | None = None):
    """Use published categorical labels, never threshold pseudo-labels.

    Numeric features are accepted only after removal of identifiers and
    candidate target/leakage columns. A named group identifier is required
    for a VERIFIED group-disjoint split. Without one, evaluation is described
    as a row holdout and carries an explicit plot-independence limitation.
    """
    if "label" not in frame:
        raise ValueError("Missing published 'label' column")
    labels = frame["label"].astype("string").str.strip().str.upper()
    unknown = set(labels.dropna().unique()) - set(LABEL_MAP)
    if unknown:
        raise ValueError(f"Unexpected research labels: {sorted(unknown)}")
    valid = labels.isin(LABEL_MAP)
    if valid.sum() < 20:
        raise ValueError("Need at least 20 usable independently labeled research rows")
    y = labels.loc[valid].map(LABEL_MAP).astype(int).reset_index(drop=True)
    if y.nunique() != 2 or y.value_counts().min() < 4:
        raise ValueError("Both AWD and non-AWD research labels need at least four rows")

    df = frame.loc[valid].reset_index(drop=True)
    if group_column is None:
        group_column = next((c for c in GROUP_COLUMNS if c in df.columns), None)
    if group_column is not None and group_column not in df:
        raise ValueError(f"Group column {group_column!r} not present")
    groups = None
    if group_column:
        if df[group_column].isna().any():
            raise ValueError("Group column contains missing values")
        groups = df[group_column].astype(str).to_numpy()

    features = []
    for col in df.columns:
        low = col.lower().strip()
        if low in EXCLUDE or col == group_column:
            continue
        if any(token in low for token in ("latitude", "longitude", "target", "label", "ground_truth")):
            continue
        if pd.api.types.is_numeric_dtype(df[col]):
            features.append(col)
    if not features:
        raise ValueError("No flat numeric research features found; use a published handcrafted-feature parquet")
    X = df[features].replace([np.inf, -np.inf], np.nan)
    if X.isna().all(axis=None):
        raise ValueError("Every numeric research feature is missing")
    return X, y, groups, group_column


def _split(X, y, groups, *, seed: int, test_fraction: float):
    indices = np.arange(len(X))
    if groups is None:
        train, test = train_test_split(
            indices, test_size=test_fraction, stratify=y, random_state=seed
        )
        strategy = "stratified_row_holdout_plot_independence_unverified"
    else:
        if len(np.unique(groups)) < 5:
            raise ValueError("At least five distinct plot groups required")
        splitter = GroupShuffleSplit(n_splits=40, test_size=test_fraction, random_state=seed)
        chosen = None
        for train, test in splitter.split(X, y, groups):
            if len(set(y.iloc[train])) == len(set(y.iloc[test])) == 2:
                chosen = train, test
                break
        if chosen is None:
            raise ValueError("Cannot build group-disjoint split with both labels")
        train, test = chosen
        if not set(groups[train]).isdisjoint(set(groups[test])):
            raise AssertionError("Group leakage")
        strategy = "group_disjoint_plot_holdout"
    return train, test, strategy


def train_benchmark(
    frame: pd.DataFrame, *, source_sha256: str, group_column: str | None = None,
    seed: int = 42, test_fraction: float = 0.2,
):
    if not 0.1 <= test_fraction <= 0.4:
        raise ValueError("test_fraction must be between 0.1 and 0.4")
    X, y, groups, group_column = prepare_data(frame, group_column=group_column)
    train, test, split_strategy = _split(
        X, y, groups, seed=seed, test_fraction=test_fraction
    )
    model = Pipeline([
        ("imputer", SimpleImputer(strategy="median", keep_empty_features=True)),
        ("classifier", RandomForestClassifier(
            n_estimators=250, min_samples_leaf=2, class_weight="balanced",
            random_state=seed, n_jobs=-1,
        )),
    ])
    model.fit(X.iloc[train], y.iloc[train])
    prediction = model.predict(X.iloc[test])
    precision, recall, f1, support = precision_recall_fscore_support(
        y.iloc[test], prediction, labels=[0, 1], zero_division=0
    )
    report = {
        "benchmark_version": BENCHMARK_VERSION,
        "source_url": SOURCE_URL,
        "source_sha256": source_sha256,
        "target": "AWD vs published PTR/DSR categories (NOT verified CF or drydown counts)",
        "model": "random_forest",
        "seed": seed,
        "split_strategy": split_strategy,
        "group_column": group_column,
        "train_rows": int(len(train)),
        "test_rows": int(len(test)),
        "train_groups": int(len(set(groups[train]))) if groups is not None else None,
        "test_groups": int(len(set(groups[test]))) if groups is not None else None,
        "feature_names": list(X.columns),
        "accuracy": float(accuracy_score(y.iloc[test], prediction)),
        "balanced_accuracy": float(balanced_accuracy_score(y.iloc[test], prediction)),
        "confusion_matrix_labels": ["not_AWD_research_class", "AWD"],
        "confusion_matrix": confusion_matrix(
            y.iloc[test], prediction, labels=[0, 1]
        ).tolist(),
        "precision": {"not_awd": float(precision[0]), "awd": float(precision[1])},
        "recall": {"not_awd": float(recall[0]), "awd": float(recall[1])},
        "f1": {"not_awd": float(f1[0]), "awd": float(f1[1])},
        "support": {"not_awd": int(support[0]), "awd": int(support[1])},
        "limitations": [
            "Data from Punjab, India, in 2024; not Bangladesh accuracy.",
            "Published AWD labels compared with PTR/DSR, not direct CF measurements.",
            "Practice classification does not establish the count of AWD drydown events.",
            "Terra Audit currently extracts S1_GRD sigma0 median; published features use different preprocessing.",
            "No use in carbon calculation, readiness, or credit issuance.",
            *([] if groups is not None else [
                "No verified plot identifier in input; row holdout may contain correlated plots."
            ]),
        ],
    }
    bundle = {
        "model": model, "feature_names": list(X.columns),
        "version": BENCHMARK_VERSION, "source_sha256": source_sha256,
        "target": report["target"],
    }
    return bundle, report


def save_benchmark(bundle: dict, report: dict, directory: Path):
    """Local operator deployment only: neither the API nor users upload pickle files."""
    import joblib
    directory.mkdir(parents=True, exist_ok=True)
    (directory / "metrics.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    joblib.dump(bundle, directory / "model.joblib")


def read_metrics(directory: Path) -> dict | None:
    path = directory / "metrics.json"
    if not path.is_file():
        return None
    data = json.loads(path.read_text(encoding="utf-8"))
    if data.get("benchmark_version") != BENCHMARK_VERSION:
        raise ValueError("Unrecognized external benchmark version")
    return data

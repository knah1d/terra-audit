"""External research AWD-practice benchmark; never used for carbon accounting.

This is intentionally separate from src.ai.ml.models, whose labels come from
the AdaptiveAWDGate itself. The published Ricemapper AWD task
(scripts/train/train.py, task "AWD_vs_PTR") trains AWD = 1 against PTR
(puddled transplanted rice) = 0 and excludes DSR. The released data has no
continuous-flooding (CF) label: PTR is the research comparison class for
conventional flooding, not a measured CF label.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd
import sklearn
from sklearn.ensemble import RandomForestClassifier
from sklearn.impute import SimpleImputer
from sklearn.metrics import (
    accuracy_score, balanced_accuracy_score, brier_score_loss, confusion_matrix,
    precision_recall_fscore_support, roc_auc_score,
)
from sklearn.base import clone
from sklearn.model_selection import (
    GroupShuffleSplit, RepeatedStratifiedKFold, cross_validate, train_test_split,
)
from sklearn.pipeline import Pipeline

from src.ai.ml.ricemapper_features import FEATURE_VERSION

BENCHMARK_VERSION = "external-ricemapper-practice-v2"
SOURCE_URL = "https://github.com/microsoft/rice-irrigation-mapping-s1s2"
# Shipped with the code (src/ is in the API image; data/ is not).
ARTIFACT_DIR = Path(__file__).parent / "artifacts" / "ricemapper_awd"
LABEL_MAP = {"AWD": 1, "PTR": 0}
RESEARCH_CLASSES = {"AWD", "PTR", "DSR"}  # DSR is excluded from the AWD task
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
    unknown = set(labels.dropna().unique()) - RESEARCH_CLASSES
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
    if groups is None:
        # Without plot IDs, identical feature rows are almost certainly the
        # same plot listed twice; keeping both could put one copy in train
        # and the other in test.
        keep = ~X.duplicated()
        X, y = X.loc[keep].reset_index(drop=True), y.loc[keep].reset_index(drop=True)
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
    rows_in = int(frame["label"].astype("string").str.strip().str.upper().isin(LABEL_MAP).sum())
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
    # A single holdout of a few hundred rows is noisy; repeated CV over all
    # rows shows the spread. Only valid as a stability check when rows are
    # independent plots (see split_strategy).
    cv = cross_validate(
        clone(model), X, y, scoring=["accuracy", "roc_auc"],
        cv=RepeatedStratifiedKFold(n_splits=5, n_repeats=5, random_state=seed),
    )
    model.fit(X.iloc[train], y.iloc[train])
    prediction = model.predict(X.iloc[test])
    score = model.predict_proba(X.iloc[test])[:, 1]
    precision, recall, f1, support = precision_recall_fscore_support(
        y.iloc[test], prediction, labels=[0, 1], zero_division=0
    )
    report = {
        "benchmark_version": BENCHMARK_VERSION,
        "source_url": SOURCE_URL,
        "source_sha256": source_sha256,
        "target": "AWD vs PTR (puddled transplanted rice) research practice labels — not measured CF, not drydown counts",
        "sklearn_version": sklearn.__version__,
        "rows_awd_ptr": rows_in,
        "duplicate_rows_removed": rows_in - int(len(X)),
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
        "confusion_matrix_labels": ["PTR", "AWD"],
        "confusion_matrix": confusion_matrix(
            y.iloc[test], prediction, labels=[0, 1]
        ).tolist(),
        "precision": {"not_awd": float(precision[0]), "awd": float(precision[1])},
        "recall": {"not_awd": float(recall[0]), "awd": float(recall[1])},
        "f1": {"not_awd": float(f1[0]), "awd": float(f1[1])},
        "support": {"not_awd": int(support[0]), "awd": int(support[1])},
        "roc_auc": float(roc_auc_score(y.iloc[test], score)),
        "brier_score": float(brier_score_loss(y.iloc[test], score)),
        "repeated_cv_5x5": {
            "accuracy_mean": float(cv["test_accuracy"].mean()),
            "accuracy_std": float(cv["test_accuracy"].std()),
            "roc_auc_mean": float(cv["test_roc_auc"].mean()),
            "roc_auc_std": float(cv["test_roc_auc"].std()),
        },
        "limitations": [
            "Data from Punjab, India, in 2024; not Bangladesh accuracy.",
            "Labels are AWD vs PTR (a sowing method used as the conventional-flooding comparison); no measured CF labels.",
            "Model score is an uncalibrated random-forest vote share, not a calibrated probability.",
            "Practice classification does not establish the count of AWD drydown events.",
            "Inference uses Earth Engine S1_GRD_FLOAT gamma0 (sigma0/cos θ) without SNAP's multi-temporal speckle filter; training used SNAP gamma0.",
            "Research window Jun 1 – Sep 5 follows the Punjab Kharif calendar; Bangladesh Boro (Jan–May) is outside it.",
            "No use in carbon calculation, readiness, or credit issuance.",
            *([] if groups is not None else [
                "No verified plot identifier in input; row holdout may contain correlated plots."
            ]),
        ],
    }
    bundle = {
        "model": model, "feature_names": list(X.columns),
        "version": BENCHMARK_VERSION, "source_sha256": source_sha256,
        "feature_version": FEATURE_VERSION,
        "target": report["target"],
    }
    return bundle, report


def save_benchmark(bundle: dict, report: dict, directory: Path):
    """Local operator deployment only: neither the API nor users upload pickle files."""
    import joblib
    directory.mkdir(parents=True, exist_ok=True)
    (directory / "metrics.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    joblib.dump(bundle, directory / "model.joblib")


_bundle_cache: dict = {}


def load_bundle(directory: Path = ARTIFACT_DIR) -> dict | None:
    """Loads the operator-trained bundle shipped in the repo; never a user upload."""
    import joblib
    path = directory / "model.joblib"
    if not path.is_file():
        return None
    if path not in _bundle_cache:
        bundle = joblib.load(path)
        if bundle.get("version") != BENCHMARK_VERSION:
            raise ValueError("Unrecognized external model version")
        _bundle_cache[path] = bundle
    return _bundle_cache[path]


def predict(bundle: dict, features: dict) -> float:
    """AWD-practice score for one field, from features in the training order."""
    missing = [name for name in bundle["feature_names"] if name not in features]
    if missing:
        raise ValueError(f"Missing model features: {missing[:3]}")
    row = pd.DataFrame([[features[n] for n in bundle["feature_names"]]],
                       columns=bundle["feature_names"]).replace([np.inf, -np.inf], np.nan)
    return float(bundle["model"].predict_proba(row)[0, 1])


def read_metrics(directory: Path = ARTIFACT_DIR) -> dict | None:
    path = directory / "metrics.json"
    if not path.is_file():
        return None
    data = json.loads(path.read_text(encoding="utf-8"))
    if data.get("benchmark_version") != BENCHMARK_VERSION:
        raise ValueError("Unrecognized external benchmark version")
    return data

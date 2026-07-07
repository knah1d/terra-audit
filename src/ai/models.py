"""
Shared training/cross-validation harness for the AI baseline classifiers.
Random Forest and XGBoost share identical CV/metrics/persistence logic, so
it lives here once instead of being duplicated per model.
"""

import warnings
from pathlib import Path

import joblib
import numpy as np
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import KFold, StratifiedKFold, cross_val_predict

from src.ai.feature_engineering import LABEL_CLASSES, encode_labels

MODEL_DIR = Path(__file__).parent.parent.parent / "data" / "ai_models"


def _make_xgb_classifier():
    # Imported lazily so models.py itself doesn't hard-fail if xgboost isn't installed.
    import xgboost as xgb

    return xgb.XGBClassifier(
        n_estimators=200, max_depth=4, random_state=42, eval_metric="mlogloss"
    )


MODEL_REGISTRY = {
    "random_forest": lambda: RandomForestClassifier(
        n_estimators=200, class_weight="balanced", random_state=42
    ),
    "xgboost": _make_xgb_classifier,
}


def _make_cv_splitter(y_encoded: np.ndarray, requested_k: int = 3):
    """
    Tries StratifiedKFold(k=min(requested_k, smallest_class_count)). When the
    smallest class can't support k>=2 under stratification (true today: the
    'drydown' class has 1 sample), falls back to plain unstratified KFold
    with a warning — so minority-class metrics are visibly provisional
    rather than a hard crash or a silently dropped class. Automatically
    upgrades to full stratified k-fold once more labeled data accumulates;
    fold count is never hardcoded.

    Returns (splitter, k_used, stratified).
    """
    n_samples = len(y_encoded)
    if n_samples < 2:
        raise ValueError("Need at least 2 samples to cross-validate.")

    _, counts = np.unique(y_encoded, return_counts=True)
    min_class_count = counts.min()

    if min_class_count >= 2:
        k = min(requested_k, int(min_class_count))
        return StratifiedKFold(n_splits=k, shuffle=True, random_state=42), k, True

    k = min(requested_k, n_samples)
    warnings.warn(
        f"Smallest class has {min_class_count} sample(s) — cannot stratify. "
        f"Falling back to unstratified KFold(k={k}); minority-class metrics "
        "are provisional until more labeled data accumulates.",
        stacklevel=2,
    )
    return KFold(n_splits=k, shuffle=True, random_state=42), k, False


def train_and_evaluate(model_name: str, X, y, k: int = 3) -> dict:
    """
    Runs pooled out-of-fold cross-validation via cross_val_predict, then fits
    one final model on all available data for persistence/inference.
    """
    model_factory = MODEL_REGISTRY[model_name]
    y_encoded = encode_labels(y)
    splitter, k_used, stratified = _make_cv_splitter(y_encoded, k)

    y_pred = cross_val_predict(model_factory(), X, y_encoded, cv=splitter)

    final_model = model_factory()
    final_model.fit(X, y_encoded)

    return {
        "model_name": model_name,
        "k_used": k_used,
        "stratified": stratified,
        "y_true": y_encoded,
        "y_pred": y_pred,
        "classes": LABEL_CLASSES,
        "model": final_model,
        "feature_names": list(X.columns),
    }


def save_model(result: dict) -> Path:
    MODEL_DIR.mkdir(parents=True, exist_ok=True)
    path = MODEL_DIR / f"{result['model_name']}.joblib"
    joblib.dump(
        {
            "model": result["model"],
            "classes": result["classes"],
            "feature_names": result["feature_names"],
        },
        path,
    )
    return path


def load_model(model_name: str) -> dict:
    path = MODEL_DIR / f"{model_name}.joblib"
    return joblib.load(path)

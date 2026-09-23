"""
Shared training/cross-validation harness for the AI baseline classifiers.
Random Forest and XGBoost share identical CV/metrics/persistence logic, so
it lives here once instead of being duplicated per model.
"""

from pathlib import Path

import joblib
import numpy as np
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import GroupKFold, cross_val_predict
from src.processing import PROCESSING_VERSION

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


def _make_cv_splitter(y_encoded, groups, requested_k=3):
    if groups is None or len(groups) != len(y_encoded):
        raise ValueError("Field identifiers are required for leakage-safe evaluation. Rebuild the dataset.")
    n_groups = len(set(groups))
    if n_groups < 2 or requested_k < 2:
        raise ValueError("Need at least two independent fields and two folds for evaluation")
    k = min(requested_k, n_groups)
    splits = list(GroupKFold(n_splits=k).split(np.zeros(len(y_encoded)), y_encoded, groups))
    for train, test in splits:
        if set(y_encoded[train]) != set(range(len(LABEL_CLASSES))):
            raise ValueError("Each training fold must contain dry, flooded and drydown labels. Collect more independently grouped fields.")
    return splits, k, False


def train_and_evaluate(model_name: str, X, y, k: int = 3, groups=None) -> dict:
    """
    Runs pooled out-of-fold cross-validation via cross_val_predict, then fits
    one final model on all available data for persistence/inference.
    """
    model_factory = MODEL_REGISTRY[model_name]
    y_encoded = encode_labels(y)
    groups = groups if groups is not None else X.attrs.get("field_groups")
    splitter, k_used, stratified = _make_cv_splitter(y_encoded, groups, k)

    y_pred = cross_val_predict(model_factory(), X, y_encoded, cv=splitter)
    y_proba = cross_val_predict(
        model_factory(), X, y_encoded, cv=splitter, method="predict_proba"
    )

    final_model = model_factory()
    final_model.fit(X, y_encoded)

    return {
        "model_name": model_name,
        "split_strategy": "field_grouped",
        "processing_version": PROCESSING_VERSION,
        "k_used": k_used,
        "stratified": stratified,
        "y_true": y_encoded,
        "y_pred": y_pred,
        "y_proba": y_proba,
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
            "processing_version": PROCESSING_VERSION,
            "split_strategy": "field_grouped",
        },
        path,
    )
    return path


def load_model(model_name: str) -> dict:
    path = MODEL_DIR / f"{model_name}.joblib"
    bundle = joblib.load(path)
    if bundle.get("processing_version") != PROCESSING_VERSION:
        raise FileNotFoundError("Model uses old satellite features; rebuild the dataset and retrain")
    return bundle

"""
Applies a trained AI baseline model to a single field/window's processed
time-series, producing the same is_flooded/drydown_event columns the
threshold gate would — so the rest of the pipeline (carbon calc, charts,
export) is agnostic to which detector ran.
"""

import pandas as pd

from src.ai.feature_engineering import build_features
from src.ai.models import load_model


def predict_awd_states(
    df: pd.DataFrame,
    model_name: str,
    field_id: str,
    district: str,
    area_ha: float,
    window_start: str,
    window_end: str,
) -> pd.DataFrame:
    """
    df: gate.extract_phenology(gate.analyze_irrigation_behavior(...)) output —
    already carries vv_smoothed/vh_smoothed/vv_zscore/vv_diff/is_sowing/
    is_harvest, none of which this function touches.

    Returns a copy with is_flooded/drydown_event overwritten by the model's
    predictions, plus new predicted_label/confidence columns.

    Raises FileNotFoundError if `model_name` hasn't been trained yet
    (propagates from src.ai.models.load_model) — callers should catch this
    and fall back to the threshold gate's own labels.
    """
    bundle = load_model(model_name)
    model, classes, feature_names = bundle["model"], bundle["classes"], bundle["feature_names"]

    tagged = df.copy()
    tagged["field_id"] = field_id
    tagged["district"] = district
    tagged["area_ha"] = area_ha
    tagged["window_start"] = window_start
    tagged["window_end"] = window_end

    X, _ = build_features(tagged)
    # Aligns to the training-time feature schema — district one-hot columns
    # can differ in count/order between training data and a single
    # inference field (e.g. a district never seen in training).
    X = X.reindex(columns=feature_names, fill_value=0)

    pred_ids = model.predict(X)
    proba = model.predict_proba(X)

    out = df.copy()
    out["predicted_label"] = [classes[i] for i in pred_ids]
    out["confidence"] = proba.max(axis=1)
    out["is_flooded"] = (out["predicted_label"] == "flooded").astype(int)
    out["drydown_event"] = (out["predicted_label"] == "drydown").astype(int)
    return out

"""Reproducible crop model training and evidence-only inference."""
import hashlib
import io
from importlib.metadata import version

import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.impute import SimpleImputer
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import LabelEncoder

from src.ai import workspace as ws
from src.ai.crop_benchmark import FEATURE_VERSION, benchmark, seasonal_features
from src.monitoring import digest
from src.processing import MULTICROP_VERSION
from src.storage import get_storage


def train(org_id, project_id, job_id, payload, checkpoint):
    # One immutable publication per queue job, including after crash/reclaim.
    existing = [r for r in ws.entries(org_id, project_id, "model") if r["id"] == job_id]
    if existing:
        return {"record_id": job_id}
    corpus = payload["corpus"]
    if not {e["field_id"] for e in corpus["examples"]} <= ws.active_fields(org_id, project_id):
        raise ValueError("Training field membership changed; submit a new training request")
    name = payload["model"]
    evaluation = benchmark(corpus, payload["split"], [name])
    checkpoint()
    X = pd.DataFrame([e["features"] for e in corpus["examples"]], dtype=float)
    encoder = LabelEncoder().fit([e["crop"] for e in corpus["examples"]])
    if name == "random_forest":
        estimator = RandomForestClassifier(n_estimators=200, class_weight="balanced", random_state=42, n_jobs=1)
    elif name == "xgboost":
        from xgboost import XGBClassifier
        estimator = XGBClassifier(n_estimators=200, max_depth=4, random_state=42, n_jobs=1)
    else:
        raise ValueError("Unsupported model")
    pipeline = make_pipeline(SimpleImputer(strategy="median", add_indicator=True, keep_empty_features=True), estimator)
    pipeline.fit(X, encoder.transform([e["crop"] for e in corpus["examples"]]))
    checkpoint()
    if ws.frozen_corpus(org_id, project_id)["sha256"] != corpus["sha256"]:
        raise ValueError("Reviewed training evidence changed while training; submit a new request")
    artifact = io.BytesIO()
    joblib.dump(pipeline, artifact)
    contents = artifact.getvalue()
    sha = hashlib.sha256(contents).hexdigest()
    # Content-addressed names avoid partial overwrites by a reclaimed worker.
    key = f"{org_id}/ai-models/{job_id}/{sha}.joblib"
    get_storage().save(key, io.BytesIO(contents))
    checkpoint()
    record = {"name": payload["name"], "model": name, "requested_by": payload["requested_by"],
              "artifact_key": key, "artifact_sha256": sha, "feature_names": list(X.columns),
              "feature_version": FEATURE_VERSION, "processing_version": MULTICROP_VERSION,
              "classes": encoder.classes_.tolist(), "districts": sorted({e["district"] for e in corpus["examples"] if e["district"]}),
              "training_years": sorted({e["year"] for e in corpus["examples"]}),
              "evaluation": evaluation, "corpus_sha256": corpus["sha256"],
              "calibration": "uncalibrated", "purpose": "retrospective_crop_monitoring_only"}
    ws.append(org_id, project_id, "model", record, job_id)
    return {"record_id": job_id}


def predict(org_id, project_id, payload):
    model = ws.get_entry(org_id, project_id, payload["model_id"], "model")["payload"]
    run, season = payload["run"], payload["season"]
    data, declared = run["payload"], season["payload"]["crops"]
    reasons = []
    if len(declared) != 1:
        reasons.append("Mixed-crop seasons require a separately validated multi-label model")
    elif declared[0] not in model["classes"]:
        reasons.append("Declared crop is outside this model's training scope")
    if data.get("quality", {}).get("status") != "ready_for_exploration":
        reasons.append("Insufficient satellite coverage")
    if model["feature_version"] != FEATURE_VERSION or model["processing_version"] != MULTICROP_VERSION or data.get("processing_version") != MULTICROP_VERSION:
        reasons.append("Incompatible processing or feature version")
    if data.get("field", {}).get("district") not in model["districts"]:
        reasons.append("District is outside this model's training scope")
    if data.get("window_start") != season["payload"]["start_date"] or data.get("window_end") != season["payload"]["end_date"]:
        reasons.append("Satellite snapshot dates do not match the current season")
    from datetime import date
    if season["payload"]["end_date"] >= date.today().isoformat():
        reasons.append("This model requires a completed season")
    software = model["evaluation"]["software"]
    for library in ("scikit-learn", "numpy", "xgboost"):
        if software.get(library) and software[library] != version(library):
            reasons.append(f"Retrain for the installed {library} version")
    result = {"field_id": run["field_id"], "season_id": run["season_id"], "season_version_id": season["id"],
              "run_id": run["id"], "run_sha256": digest(data), "model_id": payload["model_id"],
              "deployment_revision": payload["deployment_revision"], "threshold": payload["threshold"],
              "status": "insufficient_evidence", "reasons": reasons, "predicted_crop": None,
              "probabilities": {}, "confidence": None, "calibration": "uncalibrated",
              "declared_crops": declared, "requested_by": payload["requested_by"],
              "in_training_data": any(e["field_id"] == run["field_id"] for e in model["evaluation"]["dataset"]["examples"]),
              "scope": "Monitoring suggestion only; not crop verification, practice compliance or carbon issuance"}
    if reasons:
        return result
    with get_storage().open(model["artifact_key"]) as f:
        contents = f.read()
    if hashlib.sha256(contents).hexdigest() != model["artifact_sha256"]:
        raise ValueError("Model artifact integrity check failed; retrain the model")
    # Only server-created, digest-checked artifacts are deserialized. No upload API.
    pipeline = joblib.load(io.BytesIO(contents))
    features = seasonal_features(data)
    X = pd.DataFrame([{k: features.get(k) for k in model["feature_names"]}], dtype=float)
    probs = pipeline.predict_proba(X)[0]
    best = int(np.argmax(probs))
    result.update(probabilities=dict(zip(model["classes"], probs.tolist())), confidence=float(probs[best]))
    if float(probs[best]) < payload["threshold"]:
        reasons.append("Model score is below the configured review threshold")
    else:
        result.update(status="review_required", predicted_crop=model["classes"][best])
    return result

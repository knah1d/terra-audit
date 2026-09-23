"""Retrospective crop-type benchmark from reviewed field evidence.

Does not promote models into production or infer management practices.
Each example is one single-crop field-season; mixed crops remain recordable
but are excluded from this single-label experiment.
"""
import numpy as np
import pandas as pd
import platform
from importlib.metadata import version
from sklearn.ensemble import RandomForestClassifier
from sklearn.impute import SimpleImputer
from sklearn.metrics import classification_report, confusion_matrix, log_loss
from sklearn.model_selection import GroupKFold, LeaveOneGroupOut
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import LabelEncoder

from src.monitoring import digest, records
from src.processing import MULTICROP_VERSION

BANDS = ["vv", "vh", "rvi", "B2", "B3", "B4", "B8", "B11", "B12", "ndvi", "ndmi", "ndti"]
FEATURE_VERSION = "season-quartile-stats-v1"


def seasonal_features(run):
    rows = [r for r in run["observations"] if r.get("valid_fraction", 0) >= 0.5]
    start, end = pd.Timestamp(run["window_start"]), pd.Timestamp(run["window_end"])
    duration = max(1, (end - start).days + 1)
    # Keep one dominant S1 relative orbit to avoid treating viewing geometry
    # differences as crop changes. The original scenes remain in the snapshot.
    radar = [r for r in rows if r["sensor"] == "sentinel1"]
    if radar:
        orbit = pd.Series([r.get("relative_orbit") for r in radar]).mode()
        if len(orbit):
            rows = [r for r in rows if r["sensor"] != "sentinel1" or r.get("relative_orbit") == orbit.iloc[0]]
    features = {}
    for band in BANDS:
        # Multiple granules from one acquisition date must not overweight it.
        values = [(r["date"], r[band]) for r in rows if r.get(band) is not None]
        series = pd.DataFrame(values, columns=["date", "value"])
        series = series.groupby("date")["value"].median() if len(series) else pd.Series(dtype=float)
        features[f"{band}_median"] = float(series.median()) if len(series) else None
        features[f"{band}_range"] = float(series.max() - series.min()) if len(series) else None
        for quarter in range(4):
            selected = [v for d, v in series.items()
                        if min(3, int((pd.Timestamp(d) - start).days * 4 / duration)) == quarter]
            features[f"{band}_q{quarter + 1}"] = float(np.median(selected)) if selected else None
    return features


def build_corpus(org_id):
    observations = records("field_observations", org_id)
    reviews = records("observation_reviews", org_id)
    runs = records("monitoring_runs", org_id)
    decisions = {r["payload"]["observation_id"]: r["payload"] for r in reviews}
    examples, excluded = [], []
    for season in records("crop_seasons", org_id):
        sid, data = season["id"], season["payload"]
        labels = [r for r in observations if r["season_id"] == sid
                  and r["payload"]["kind"] == "crop_identity"
                  and r["payload"]["source"] in {"field_measurement", "expert_observation"}
                  and decisions.get(r["id"], {}).get("decision") == "accepted"]
        candidates = [r for r in runs if r["season_id"] == sid
                      and r["payload"].get("processing_version") == MULTICROP_VERSION]
        reason = None
        if len(data["crops"]) != 1:
            reason = "Mixed crops require a separate multi-label benchmark"
        elif data["crops"][0] in {"unknown", "other", "mixed"}:
            reason = "An identified crop is required for supervised evaluation"
        elif not labels:
            reason = "No accepted independent crop observation"
        elif {r["payload"]["value"] for r in labels} != set(data["crops"]):
            reason = "Crop evidence conflicts with the declaration or other accepted evidence"
        elif not candidates:
            reason = "No current-version satellite snapshot"
        elif candidates[-1]["payload"]["quality"]["status"] == "insufficient_evidence":
            reason = "Latest snapshot has insufficient observation coverage"
        if reason:
            excluded.append({"season_id": sid, "reason": reason})
            continue
        run = candidates[-1]
        examples.append({"season_id": sid, "field_id": season["field_id"],
            "year": data["start_date"][:4], "district": run["payload"]["field"]["district"],
            "crop": data["crops"][0], "run_id": run["id"], "run_sha256": digest(run["payload"]),
            "label_observation_ids": [r["id"] for r in labels],
            "label_review_ids": [r["id"] for r in reviews if r["payload"]["observation_id"] in {x["id"] for x in labels}],
            "features": seasonal_features(run["payload"])})
    corpus = {"schema_version": "crop-benchmark-v1", "feature_version": FEATURE_VERSION,
              "processing_version": MULTICROP_VERSION, "label_source": "independently_reviewed_field_evidence",
              "examples": examples, "excluded": excluded,
              "scope": "Retrospective single-crop classification; no carbon or practice verification"}
    return {**corpus, "sha256": digest(corpus)}


def make_splits(examples, mode):
    if mode not in {"field", "year", "district"}:
        raise ValueError("Unknown evaluation split")
    groups = np.array([r[f"{mode}_id" if mode == "field" else mode] for r in examples])
    if len(set(groups)) < 2:
        raise ValueError(f"Need at least two distinct {mode} groups")
    splitter = GroupKFold(n_splits=min(5, len(set(groups)))) if mode == "field" else LeaveOneGroupOut()
    fields = np.array([r["field_id"] for r in examples])
    splits = []
    for train, test in splitter.split(np.zeros(len(examples)), groups=groups):
        # A year-held-out test must not see another season of the same field.
        train = train[~np.isin(fields[train], fields[test])]
        if not len(train):
            raise ValueError("No training fields remain after field-isolation checks; collect more independent fields")
        if not {examples[i]["crop"] for i in test} <= {examples[i]["crop"] for i in train}:
            raise ValueError("A held-out crop is absent from training; collect that crop in more independent groups")
        splits.append((train, test))
    return splits


def benchmark(corpus, mode="field", models=("random_forest", "xgboost")):
    examples = corpus["examples"]
    if len(examples) < 4 or len({r["crop"] for r in examples}) < 2:
        raise ValueError("Need at least four eligible field-seasons across two crops, with each crop in independent fields")
    splits = make_splits(examples, mode)
    X = pd.DataFrame([r["features"] for r in examples], dtype=float)
    encoder = LabelEncoder().fit([r["crop"] for r in examples])
    y = encoder.transform([r["crop"] for r in examples])
    results = {}
    for model_name in dict.fromkeys(models):
        predictions = np.zeros(len(y), dtype=int)
        probabilities = np.zeros((len(y), len(encoder.classes_)))
        folds = []
        for train, test in splits:
            if model_name == "random_forest":
                model = RandomForestClassifier(n_estimators=200, class_weight="balanced", random_state=42, n_jobs=1)
            elif model_name == "xgboost":
                from xgboost import XGBClassifier
                model = XGBClassifier(n_estimators=200, max_depth=4, random_state=42, n_jobs=1)
            else:
                raise ValueError("Unknown benchmark model")
            # Imputation is fitted on training rows only; never the full corpus.
            pipeline = make_pipeline(SimpleImputer(strategy="median", add_indicator=True, keep_empty_features=True), model)
            pipeline.fit(X.iloc[train], y[train])
            predictions[test] = pipeline.predict(X.iloc[test])
            probabilities[np.ix_(test, model.classes_.astype(int))] = pipeline.predict_proba(X.iloc[test])
            folds.append({"train_seasons": [examples[i]["season_id"] for i in train],
                          "test_seasons": [examples[i]["season_id"] for i in test]})
        results[model_name] = {"report": classification_report(y, predictions, labels=np.arange(len(encoder.classes_)),
            target_names=encoder.classes_.tolist(), output_dict=True, zero_division=0),
            "confusion_matrix": confusion_matrix(y, predictions).tolist(),
            "log_loss": float(log_loss(y, probabilities, labels=np.arange(len(encoder.classes_)))),
            "brier_score": float(np.mean(np.sum((probabilities - np.eye(len(encoder.classes_))[y]) ** 2, axis=1))),
            "predictions": [{"season_id": r["season_id"], "actual": r["crop"],
                "predicted": str(encoder.classes_[predictions[i]]),
                "probabilities": probabilities[i].tolist()} for i, r in enumerate(examples)], "folds": folds}
    return {"dataset": corpus, "split": mode, "classes": encoder.classes_.tolist(), "models": results,
            "software": {"python": platform.python_version(), "scikit-learn": version("scikit-learn"),
                         "numpy": version("numpy"), "xgboost": version("xgboost") if "xgboost" in models else None},
            "deployment_status": "research_only", "seed": 42,
            "limitations": ["Small samples do not establish regional validity", "Probabilities are not calibrated",
                            "Full-season features cannot be used for early-season claims",
                            "WorldCereal/Presto comparison requires a separately prepared compatible feature dataset"]}

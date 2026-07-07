"""
Metrics for the AI baseline classifiers, computed from pooled out-of-fold
cross-validation predictions (see src.ai.models.train_and_evaluate).

Naming avoids "accuracy" in a ground-truth sense: labels come from the
threshold gate itself (see dataset_builder.py docstring), so what's measured
here is model-vs-threshold-gate agreement, not accuracy against verified
real-world irrigation truth.
"""

import numpy as np
from sklearn.metrics import (
    auc,
    confusion_matrix,
    precision_recall_fscore_support,
    roc_curve,
)


def summarize_fold_predictions(result: dict) -> dict:
    """Returns a JSON-serializable dict, reusable as-is by a Streamlit
    Validation tab (e.g. pd.DataFrame(d['per_class']).T for a table, or a
    heatmap over d['confusion_matrix'])."""
    classes = result["classes"]
    y_true = result["y_true"]
    y_pred = result["y_pred"]
    label_ids = list(range(len(classes)))

    agreement = (y_true == y_pred).mean()
    precision, recall, f1, support = precision_recall_fscore_support(
        y_true, y_pred, labels=label_ids, zero_division=0
    )
    per_class = {
        cls: {
            "precision": float(precision[i]),
            "recall": float(recall[i]),
            "f1": float(f1[i]),
            "support": int(support[i]),
        }
        for i, cls in enumerate(classes)
    }
    cm = confusion_matrix(y_true, y_pred, labels=label_ids)

    macro_p, macro_r, macro_f1, _ = precision_recall_fscore_support(
        y_true, y_pred, labels=label_ids, average="macro", zero_division=0
    )

    return {
        "model_name": result["model_name"],
        "k_used": result["k_used"],
        "stratified": result["stratified"],
        "threshold_agreement_score": float(agreement),
        "macro_avg": {
            "precision": float(macro_p),
            "recall": float(macro_r),
            "f1": float(macro_f1),
        },
        "per_class": per_class,
        "confusion_matrix": {"labels": list(classes), "matrix": cm.tolist()},
    }


def feature_importance(result: dict) -> dict:
    """Maps feature name -> importance, sorted descending. Both
    RandomForestClassifier and XGBClassifier expose `.feature_importances_`
    in the same shape, so no model-specific branching is needed."""
    importances = result["model"].feature_importances_
    pairs = sorted(
        zip(result["feature_names"], importances), key=lambda p: p[1], reverse=True
    )
    return {name: float(value) for name, value in pairs}


def roc_curve_data(result: dict) -> dict:
    """One-vs-rest ROC curve per class from pooled out-of-fold probabilities
    (result['y_proba'], added by models.train_and_evaluate).

    Caveat: with a class this thin on samples, its curve is numerically
    valid but not statistically meaningful — callers should caption this
    rather than present it as a confident result."""
    classes = result["classes"]
    y_true = result["y_true"]
    y_proba = result["y_proba"]

    curves = {}
    for i, cls in enumerate(classes):
        y_true_binary = (y_true == i).astype(int)
        fpr, tpr, _ = roc_curve(y_true_binary, y_proba[:, i])
        curves[cls] = {
            "fpr": fpr.tolist(),
            "tpr": tpr.tolist(),
            "auc": float(auc(fpr, tpr)) if len(np.unique(y_true_binary)) > 1 else None,
        }
    return curves


def summarize(result: dict) -> str:
    """Human-readable text summary for CLI output."""
    d = summarize_fold_predictions(result)
    lines = [
        f"Model: {d['model_name']} (cv folds={d['k_used']}, stratified={d['stratified']})",
        f"Threshold-gate agreement: {d['threshold_agreement_score']:.3f}",
        "Per-class:",
    ]
    for cls, m in d["per_class"].items():
        lines.append(
            f"  {cls:10s} precision={m['precision']:.2f} recall={m['recall']:.2f} "
            f"f1={m['f1']:.2f} support={m['support']}"
        )
    lines.append(f"Confusion matrix (labels={d['confusion_matrix']['labels']}):")
    for row in d["confusion_matrix"]["matrix"]:
        lines.append(f"  {row}")
    return "\n".join(lines)

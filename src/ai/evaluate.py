"""
Metrics for the AI baseline classifiers, computed from pooled out-of-fold
cross-validation predictions (see src.ai.models.train_and_evaluate).

Naming avoids "accuracy" in a ground-truth sense: labels come from the
threshold gate itself (see dataset_builder.py docstring), so what's measured
here is model-vs-threshold-gate agreement, not accuracy against verified
real-world irrigation truth.
"""

from sklearn.metrics import confusion_matrix, precision_recall_fscore_support


def summarize_fold_predictions(result: dict) -> dict:
    """Returns a JSON-serializable dict, reusable as-is by a future
    Streamlit Validation tab (e.g. pd.DataFrame(d['per_class']).T for a
    table, or a heatmap over d['confusion_matrix'])."""
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

    return {
        "model_name": result["model_name"],
        "k_used": result["k_used"],
        "stratified": result["stratified"],
        "threshold_agreement_score": float(agreement),
        "per_class": per_class,
        "confusion_matrix": {"labels": list(classes), "matrix": cm.tolist()},
    }


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

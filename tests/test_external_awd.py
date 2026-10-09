"""The external benchmark must never be confused with detector-label agreement."""
import hashlib

import numpy as np
import pandas as pd
import pytest

from src.ai.ml.external_awd import prepare_data, train_benchmark


def research_rows(n=80, with_group=True):
    rng = np.random.default_rng(1234)
    labels = np.array(["AWD", "PTR", "DSR", "AWD"] * (n // 4))
    out = pd.DataFrame({
        "label": labels,
        "VV_DESCENDING_mean_spline_0": rng.normal(-14, 2, n),
        "VH_DESCENDING_mean_spline_0": rng.normal(-21, 2, n),
        "numeric_feature": rng.normal(size=n),
        "Latitude": np.linspace(30, 32, n),
        "drydown_event": (labels == "AWD").astype(int),
    })
    if with_group:
        out["plot_id"] = [f"plot_{i//2}" for i in range(n)]
    return out


def test_research_training_is_disjoint_and_excludes_leakage():
    data = research_rows()
    X, y, groups, group_col = prepare_data(data)
    assert group_col == "plot_id"
    assert len(X) == len(y) == 60  # DSR rows are excluded from the AWD-vs-PTR task
    assert "Latitude" not in X.columns
    assert "drydown_event" not in X.columns
    assert "plot_id" not in X.columns
    bundle, report = train_benchmark(data, source_sha256="abc")
    assert report["split_strategy"] == "group_disjoint_plot_holdout"
    assert report["train_groups"] + report["test_groups"] == len(set(groups))
    assert bundle["feature_names"] == report["feature_names"]
    assert len(report["confusion_matrix"]) == 2
    assert 0 <= report["accuracy"] <= 1


def test_no_group_id_is_explicitly_unverified():
    _, report = train_benchmark(research_rows(with_group=False), source_sha256="def")
    assert "plot_independence_unverified" in report["split_strategy"]
    assert any("row holdout" in item for item in report["limitations"])


def test_unknown_research_label_rejected():
    data = research_rows()
    data.loc[0, "label"] = "flooded"
    with pytest.raises(ValueError, match="Unexpected research labels"):
        prepare_data(data)


def test_no_plot_accuracy_from_synthetic_detector_labels():
    data = research_rows()
    data["label"] = "drydown"
    with pytest.raises(ValueError, match="Unexpected research labels"):
        prepare_data(data)

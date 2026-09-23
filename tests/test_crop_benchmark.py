import numpy as np
import pandas as pd
import pytest

from src.ai.crop_benchmark import benchmark, make_splits, seasonal_features
from src.ai.models import train_and_evaluate
from src.multicrop_data import quality_summary
from src.processing import rvi_from_db


def examples():
    # Every field has both crops in separate seasons, so grouped evaluation
    # has a learnable task and no crop disappears from its training folds.
    return [{"field_id": f"f{i}", "season_id": f"s{i}-{crop}", "crop": crop,
             "year": str(2020 + i), "district": f"d{i % 2}",
             "features": {"ndvi_median": float(c), "ndmi_median": None}}
            for i in range(4) for c, crop in enumerate(["wheat", "maize"])]


@pytest.mark.parametrize("mode", ["field", "year", "district"])
def test_splits_never_share_fields(mode):
    rows = examples()
    for train, test in make_splits(rows, mode):
        assert {rows[i]["field_id"] for i in train}.isdisjoint({rows[i]["field_id"] for i in test})
        key = "field_id" if mode == "field" else mode
        assert {rows[i][key] for i in train}.isdisjoint({rows[i][key] for i in test})


def test_unrepresented_crop_fails_instead_of_misleading_score():
    rows = examples()
    rows[0]["crop"] = "unique"
    with pytest.raises(ValueError, match="absent from training"):
        make_splits(rows, "field")


def test_benchmark_reproducible_and_contains_fold_manifest():
    corpus = {"examples": examples(), "sha256": "test"}
    a = benchmark(corpus, models=["random_forest", "xgboost"])
    b = benchmark(corpus, models=["random_forest"])
    assert a["models"]["random_forest"] == b["models"]["random_forest"]
    assert a["deployment_status"] == "research_only"
    assert len(a["models"]["random_forest"]["predictions"]) == 8
    assert a["models"]["xgboost"]["log_loss"] >= 0


def test_features_exclude_clouds_and_duplicate_granule_weighting():
    run = {"window_start": "2025-01-01", "window_end": "2025-04-30", "observations": [
        {"date": "2025-01-05", "sensor": "sentinel2", "valid_fraction": 1, "ndvi": .2},
        {"date": "2025-01-05", "sensor": "sentinel2", "valid_fraction": 1, "ndvi": .4},
        {"date": "2025-01-15", "sensor": "sentinel2", "valid_fraction": .1, "ndvi": .9}]}
    features = seasonal_features(run)
    assert features["ndvi_q1"] == pytest.approx(.3)
    assert features["ndvi_q2"] is None
    assert not any("crop" in key or "field" in key for key in features)


def test_rvi_power_units_and_quality_abstention():
    assert rvi_from_db(-10, -20) == pytest.approx(4 * .01 / .11)
    assert rvi_from_db(-10, -10) == pytest.approx(2)
    assert quality_summary([], "2025-01-01", "2025-05-01")["status"] == "insufficient_evidence"


def test_legacy_ai_requires_field_groups_and_all_labels():
    X = pd.DataFrame({"vv": [-1, -2, -3, -4, -5, -6]})
    y = pd.Series(["dry", "flooded", "drydown"] * 2)
    with pytest.raises(ValueError, match="Field identifiers"):
        train_and_evaluate("random_forest", X, y)
    result = train_and_evaluate("random_forest", X, y, groups=["a"] * 3 + ["b"] * 3)
    assert result["split_strategy"] == "field_grouped"
    assert result["y_proba"].shape == (6, 3)

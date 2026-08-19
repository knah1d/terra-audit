"""
Proves the cache-hit path never touches GEE (stub_spatial_engine raises
if extract_clean_timeseries is ever called) and returns a synchronous 200,
not a 202 job — the whole point of checking the DB cache first.
"""

import pandas as pd

from src.database import save_cache


def _seed_cache(field_id: str, window_start: str, window_end: str):
    dates = pd.date_range("2026-01-01", periods=20, freq="6D")
    df = pd.DataFrame({
        "date": dates.strftime("%Y-%m-%d"),
        "vv": [-9.0 - 0.1 * i for i in range(20)],
        "vh": [-15.0 - 0.05 * i for i in range(20)],
        "cross_ratio": [5.0] * 20,
        "rvi": [0.5] * 20,
    })
    save_cache("testorg", field_id, df, window_start, window_end)


def test_signal_run_cache_hit_is_synchronous_200(client, rice_field, auth_headers):
    _seed_cache(rice_field, "2026-01-01", "2026-03-01")

    r = client.post(
        f"/fields/{rice_field}/signal-runs",
        json={"window_start": "2026-01-01", "window_end": "2026-03-01", "detector": "threshold"},
        headers=auth_headers["admin"],
    )
    assert r.status_code == 200  # not 202 — never went through the job path
    body = r.json()
    assert body["cache_source"] == "Local relational data store"
    assert body["field_id"] == rice_field
    assert body["n_observations"] == 20


def test_signal_run_cache_miss_returns_job(client, rice_field, auth_headers):
    """No cache seeded for this window — falls to the job path. We only
    assert the 202/job_id contract here, not the job's eventual result,
    since actually running it would hit the stubbed engine and raise by
    design (proving this test takes the job path, not the fast path)."""
    r = client.post(
        f"/fields/{rice_field}/signal-runs",
        json={"window_start": "2020-01-01", "window_end": "2020-03-01", "detector": "threshold"},
        headers=auth_headers["admin"],
    )
    assert r.status_code == 202
    assert "job_id" in r.json()

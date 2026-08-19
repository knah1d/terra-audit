from typing import Any

from pydantic import BaseModel


class SignalRunRequest(BaseModel):
    window_start: str  # "YYYY-MM-DD"
    window_end: str
    detector: str = "threshold"  # "threshold" | "random_forest" | "xgboost"
    force_refresh: bool = False


class SignalResult(BaseModel):
    """Fully enumerated (not a passthrough) — this is the API's own
    assembled contract from several pipeline steps, not a wrapped engine
    dict, and every field here is exactly what report_generator.py's
    generate_pdf/generate_audit_json/generate_timeseries_csv need as
    their `signal`/`window` arguments plus the raw timeseries — so this
    is what a stateless API persists server-side in place of the
    Streamlit session_state export_* keys."""
    field_id: str
    cache_source: str
    total_awd: int
    sowing_date: str
    harvest_date: str
    season_length_days: int
    from_phenology: bool
    detector_used: str
    model_fallback_msg: str | None = None
    n_observations: int
    vv_mean: float
    vv_std: float
    awd_dates: list[str]
    window_start: str
    window_end: str
    area_ha: float
    timeseries: list[dict[str, Any]]


class JobStatusOut(BaseModel):
    job_id: str
    job_type: str
    status: str  # pending | running | done | error
    result: dict[str, Any] | None = None
    error: str | None = None
    created_at: str | None = None
    finished_at: str | None = None


class SignalRunAccepted(BaseModel):
    job_id: str

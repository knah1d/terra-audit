from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict


class CarbonCalcRequestRice(BaseModel):
    """Mirrors CarbonAssetEngine.calculate_credits()'s keyword arguments
    exactly (src/carbon_calculator.py:117) — this is a small, stable,
    intentionally-designed function signature, unlike its *result* dict
    (see CarbonResultOut below), so full enumeration here is correct."""
    awd_events: int
    season_length_days: int
    area_ha: float
    q_n_kg_per_ha: float = 100.0
    preseason_category: str = "short"  # "short" | "long"
    baseline_amendments: list[tuple[str, float]] | None = None
    project_amendments: list[tuple[str, float]] | None = None


class CarbonCalcRequestAlm(BaseModel):
    """Mirrors AlmCarbonEngine.calculate_credits()'s keyword arguments
    (src/carbon_calculator_alm.py:433). practice_schedule/soc_measurements
    are NOT included here — the backend loads those from the DB by
    field_id rather than trusting a client-resubmitted copy, per the
    plan's explicit goal of eliminating the Streamlit session_state
    cross-tab handoff."""
    area_ha: float
    verification_years: float = 1.0
    non_permanence_risk_pct: float = 20.0


class CarbonResultOut(BaseModel):
    """Passthrough wrapper around calculate_credits()'s ~15-30 key result
    dict. Only fields THIS API's own routing logic branches on are named;
    everything else the engine returns rides through via `extra='allow'`
    untouched — so a new key added to either engine needs zero schema
    change here. Do not add more named fields unless the router itself
    needs to read them; that's the line between "contract" and "passthrough."
    """
    model_config = ConfigDict(extra="allow")

    final_issuance: float | None = None
    # Rice-only gate field (absent on ALM results)
    qa3_pathway_valid: bool | None = None
    # ALM-only gate fields (absent on rice results)
    production_decline_leakage_blocked: bool | None = None
    cumulative_delta_co2_wp: float | None = None


class CommitResponse(BaseModel):
    final_issuance: float | None
    already_committed: bool


class CreditHistoryEntry(BaseModel):
    # The real, stable credit_history.id — never an array index/timestamp/
    # field_id. This is what identifies a specific committed verification.
    credit_history_id: int
    calculated_at: datetime
    final_issuance: float
    inputs: dict[str, Any]
    result: dict[str, Any]

"""Registers the rice/AWD field type — the only tenant of the registry today."""

from src.threshold_gate import AdaptiveAWDGate
from src.carbon_calculator import CarbonAssetEngine
from src.field_types.registry import register_field_type

FIELD_TYPE_KEY = "rice_awd"

register_field_type(
    FIELD_TYPE_KEY,
    label="Rice — Alternate Wetting & Drying (VM0051)",
    detector_factory=AdaptiveAWDGate,
    methodology_factory=CarbonAssetEngine,
    uses_sar=True,
)

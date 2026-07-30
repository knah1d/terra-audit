"""
Registry mapping a field's `field_type` to the detector and methodology
engine that analyze its signal and calculate its credits.

Detector: for SAR-driven field types, exposes analyze_irrigation_behavior()/
extract_phenology()-style methods that turn a raw timeseries into practice
events (today: AdaptiveAWDGate). Field types with no satellite signal
(uses_sar=False) register a validator here instead — it checks the manually
entered practice-schedule/soil data is complete rather than analyzing a
timeseries (today: AlmPracticeValidator).
Methodology engine: exposes calculate_credits() turning those events/data +
area into a credits dict (today: CarbonAssetEngine, AlmCarbonEngine).

`uses_sar` tells app.py whether to fetch a Sentinel-1 timeseries and show the
Signal Analytics tab for this field type, or to collect manually entered data
instead (Practice & Soil Data tab).

Factories are zero-arg callables invoked fresh per lookup rather than cached
here — today's implementations are cheap to construct (no I/O).
"""

FIELD_TYPES = {}


def register_field_type(
    key: str, label: str, detector_factory, methodology_factory, uses_sar: bool = True
):
    FIELD_TYPES[key] = {
        "label": label,
        "detector_factory": detector_factory,
        "methodology_factory": methodology_factory,
        "uses_sar": uses_sar,
    }


def get_field_type(key: str) -> dict:
    if key not in FIELD_TYPES:
        raise KeyError(f"Unknown field_type '{key}'. Registered: {list(FIELD_TYPES)}")
    return FIELD_TYPES[key]


def build_detector(key: str):
    return get_field_type(key)["detector_factory"]()


def build_methodology(key: str):
    return get_field_type(key)["methodology_factory"]()


def field_uses_sar(key: str) -> bool:
    return get_field_type(key)["uses_sar"]

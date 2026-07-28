"""
Registry mapping a field's `field_type` to the detector and methodology
engine that analyze its signal and calculate its credits.

Detector: exposes analyze_irrigation_behavior()/extract_phenology()-style
methods that turn a raw timeseries into practice events (today: AdaptiveAWDGate).
Methodology engine: exposes calculate_credits() turning those events + area
into a credits dict (today: CarbonAssetEngine).

Factories are zero-arg callables invoked fresh per lookup rather than cached
here — both today's implementations are cheap to construct (no I/O).
"""

FIELD_TYPES = {}


def register_field_type(key: str, label: str, detector_factory, methodology_factory):
    FIELD_TYPES[key] = {
        "label": label,
        "detector_factory": detector_factory,
        "methodology_factory": methodology_factory,
    }


def get_field_type(key: str) -> dict:
    if key not in FIELD_TYPES:
        raise KeyError(f"Unknown field_type '{key}'. Registered: {list(FIELD_TYPES)}")
    return FIELD_TYPES[key]


def build_detector(key: str):
    return get_field_type(key)["detector_factory"]()


def build_methodology(key: str):
    return get_field_type(key)["methodology_factory"]()

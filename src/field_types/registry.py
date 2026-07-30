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

Scalability note (2 field types today): app.py dispatches per-methodology at
the UI layer (render_carbon_tab_rice_awd vs render_carbon_tab_alm, each
calling its engine's differently-shaped calculate_credits() —
awd_events/season_length_days/area_ha vs
practice_schedule/soc_measurements/area_ha/verification_years). This is NOT
a problem at this scale: the two field types have irreducibly different raw
inputs (SAR-derived events vs. manually entered practice/lab data), so a
shared generic signature would just be a lowest-common-denominator dict
wrapper adding indirection without removing real duplication — not worth
building now.

What WOULD start to hurt at a 3rd field type, if one is ever added:
  - report_generator.py's per-methodology PDF functions (generate_pdf vs
    generate_pdf_alm) duplicate header/footer/banner boilerplate — worth
    factoring shared section helpers into _PDF before a 3rd report variant.
  - app.py's binary `if selected_uses_sar: ... else: ...` tab dispatch would
    need to become a proper per-field-type render-function lookup here in
    the registry (a render_practice_tab_factory/render_carbon_tab_factory
    entry, mirroring detector_factory/methodology_factory) once there are
    3+ UI shapes to dispatch, rather than a growing elif chain in app.py.
This is deferred until a 3rd methodology is actually being added, not
scoped as current work.
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

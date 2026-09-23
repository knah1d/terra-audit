"""Crop taxonomy — deliberately separate from methodology eligibility and
from AI model coverage (docs/RESEARCH_IMPLEMENTATION_PLAN_2026-09-23.md:
"Supporting a crop in records, recognizing it with AI, and supporting a
crediting claim for it are three separate capabilities.").

This module answers ONLY "what crop is this" (a recordkeeping concern —
any crop can be entered as a crop-season/practice-event record, per
Phase 2's "do not assume all crops qualify for carbon accounting").
`alm_eligible`/`vm0051_eligible` here are coarse, conservative signals
consumed by src.readiness's substantive applicability check — they are
NOT a substitute for the real per-methodology applicability conditions
(soil type, drainage class, prior land use, etc.) that this codebase
does not measure.

AI model coverage is deliberately NOT modeled here as a static per-crop
flag: this codebase now supports per-PROJECT trained/activated models
(see src/ai/managed_models.py, src/ai/workspace.py) whose crop coverage
depends on what training data a project actually reviewed and accepted,
not a fixed global table. Whether AI coverage exists for a given
crop/project is a question for that module, not this one — recognizing
a crop in records never implies AI coverage, and AI coverage never
implies methodology eligibility.

Not persisted: this is a fixed, code-reviewed classification (like
src.field_types.registry.FIELD_TYPES), not user-editable tenant data.
Unrecognized free-text crop names already work everywhere in the app
(crop-season `crops` is free text) — this registry only adds an
optional, best-effort classification on top for the specific checks
that need one; a crop absent from CROPS is treated as `unknown`, never
silently assumed eligible.
"""

# is_wetland_crop: normally grown under continuous flooding — the basis
# for VM0042's condition-8 exclusion (methodologies/verra/vm0042/
# VM0042v2.2.pdf, applicability §4). VM0051 covers rice specifically
# under Alternate Wetting & Drying (i.e. deliberately NOT continuously
# flooded) — the two flags below are about the CROP's default regime,
# not about a specific field's actual practice, which is why
# `vm0042.excludes_wetland_rice` in src/readiness.py additionally checks
# the field's own field_type/pathway rather than relying on this alone.
CROPS: dict[str, dict] = {
    "rice": {"common_names": ["rice", "paddy"], "is_wetland_crop": True,
             "alm_eligible": False, "vm0051_eligible": True},
    "wheat": {"common_names": ["wheat"], "is_wetland_crop": False,
              "alm_eligible": True, "vm0051_eligible": False},
    "maize": {"common_names": ["maize", "corn"], "is_wetland_crop": False,
              "alm_eligible": True, "vm0051_eligible": False},
    "potato": {"common_names": ["potato"], "is_wetland_crop": False,
               "alm_eligible": True, "vm0051_eligible": False},
    "jute": {"common_names": ["jute"], "is_wetland_crop": False,
             "alm_eligible": True, "vm0051_eligible": False},
    "lentil": {"common_names": ["lentil", "masoor"], "is_wetland_crop": False,
               "alm_eligible": True, "vm0051_eligible": False},
    "mustard": {"common_names": ["mustard", "rapeseed"], "is_wetland_crop": False,
                "alm_eligible": True, "vm0051_eligible": False},
    "sugarcane": {"common_names": ["sugarcane", "sugar cane"], "is_wetland_crop": False,
                  "alm_eligible": True, "vm0051_eligible": False},
    "vegetables": {"common_names": ["vegetable", "vegetables"], "is_wetland_crop": False,
                   "alm_eligible": True, "vm0051_eligible": False},
}

_ALIASES = {alias: key for key, meta in CROPS.items() for alias in meta["common_names"]}


def classify(crop_name: str) -> dict:
    """Returns the taxonomy entry for a (lowercased, already-normalized —
    see backend/schemas/monitoring.py's SeasonCreate.normalize_crops)
    crop name, or an explicit 'unknown' entry — never a guess."""
    key = _ALIASES.get(crop_name.strip().lower())
    if key is None:
        return {"key": None, "common_names": [crop_name], "is_wetland_crop": None,
                "alm_eligible": None, "vm0051_eligible": None, "recognized": False}
    return {"key": key, **CROPS[key], "recognized": True}


def list_taxonomy() -> list[dict]:
    return [{"key": key, **meta} for key, meta in sorted(CROPS.items())]

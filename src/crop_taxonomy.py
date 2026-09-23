"""Crop taxonomy — deliberately separate from methodology eligibility and
from AI model coverage (docs/RESEARCH_IMPLEMENTATION_PLAN_2026-09-23.md:
"Supporting a crop in records, recognizing it with AI, and supporting a
crediting claim for it are three separate capabilities.").

This module answers ONLY "what crop is this" (a recordkeeping concern —
any crop can be entered as a crop-season/practice-event record, per
Phase 2's "do not assume all crops qualify for carbon accounting").
`alm_eligible`/`vm0051_eligible` here are coarse, INDICATIVE signals
only — src.readiness's applicability check treats them as a ceiling of
'needs_review', never as sufficient by itself to mark full methodology
applicability 'satisfied' (see _methodology_applicability_check). They
are not a substitute for the real per-methodology applicability
conditions (actual water regime, drainage class, prior land use, etc.)
that this codebase does not measure.

Deliberately NOT modeled here: a per-crop "is this land wetland" flag.
Land-use CONDITION (whether a given field is actually under continuous
flooding, drained, etc.) is not the same fact as crop IDENTITY (what
crop is planted), and conflating them would mean e.g. assuming every
rice declaration describes wetland cropland — rice is grown under both
continuously-flooded and Alternate-Wetting-and-Drying (deliberately NOT
continuously flooded) regimes, and this module has no way to tell them
apart from a crop name alone. src.readiness's vm0042.excludes_wetland_rice
check is worded around the REAL, narrower fact instead: this codebase
has not implemented any rice-SOC assessment under VM0042 in any water
regime, so a rice declaration there is unsupported pending that
implementation — not because rice "is" wetland.

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

CROPS: dict[str, dict] = {
    "rice": {"common_names": ["rice", "paddy"], "alm_eligible": False, "vm0051_eligible": True,
             "notes": "vm0051_eligible reflects VM0051's rice-AWD methane scope. alm_eligible is False "
                      "not because rice 'is' wetland, but because this codebase has not implemented any "
                      "rice-SOC assessment under VM0042 in any water regime — see "
                      "src.readiness's vm0042.excludes_wetland_rice."},
    "wheat": {"common_names": ["wheat"], "alm_eligible": True, "vm0051_eligible": False},
    "maize": {"common_names": ["maize", "corn"], "alm_eligible": True, "vm0051_eligible": False},
    "potato": {"common_names": ["potato"], "alm_eligible": True, "vm0051_eligible": False},
    "jute": {"common_names": ["jute"], "alm_eligible": True, "vm0051_eligible": False},
    "lentil": {"common_names": ["lentil", "masoor"], "alm_eligible": True, "vm0051_eligible": False},
    "mustard": {"common_names": ["mustard", "rapeseed"], "alm_eligible": True, "vm0051_eligible": False},
    "sugarcane": {"common_names": ["sugarcane", "sugar cane"], "alm_eligible": True, "vm0051_eligible": False},
    "vegetables": {"common_names": ["vegetable", "vegetables"], "alm_eligible": True, "vm0051_eligible": False},
}

_ALIASES = {alias: key for key, meta in CROPS.items() for alias in meta["common_names"]}


def classify(crop_name: str) -> dict:
    """Returns the taxonomy entry for a (lowercased, already-normalized —
    see backend/schemas/monitoring.py's SeasonCreate.normalize_crops)
    crop name, or an explicit 'unknown' entry — never a guess."""
    key = _ALIASES.get(crop_name.strip().lower())
    if key is None:
        return {"key": None, "common_names": [crop_name],
                "alm_eligible": None, "vm0051_eligible": None, "recognized": False}
    return {"key": key, "notes": None, **CROPS[key], "recognized": True}


def list_taxonomy() -> list[dict]:
    return [{"key": key, **meta} for key, meta in sorted(CROPS.items())]

from pydantic import BaseModel

# Matches src.database.ALM_PRACTICE_COLUMNS exactly — declared as a plain
# dict[str, Any]-shaped model rather than importing ALM_PRACTICE_COLUMNS to
# generate fields dynamically, since these are stable, documented VM0042
# practice-schedule fields, not something expected to grow the way engine
# result dicts do.


class PracticeScheduleIn(BaseModel):
    crop_type: str | None = None
    crop_rotation: bool | None = None
    cover_crops: bool | None = None
    intercropping: bool | None = None
    tillage: bool | None = None
    tillage_depth_cm: float | None = None
    residue_removed: bool | None = None
    residue_burned_kg_ha: float | None = None
    synthetic_n_rate_kg_ha: float | None = None
    organic_n_rate_kg_ha: float | None = None
    n_fixing_species: bool | None = None
    n_fixing_dry_matter_kg_ha: float | None = None
    fuel_use_l_ha: float | None = None
    crop_yield_t_ha: float | None = None


class PracticeScheduleOut(BaseModel):
    baseline: PracticeScheduleIn | None = None
    project: PracticeScheduleIn | None = None


class LivestockEntry(BaseModel):
    livestock_type: str  # one of AlmCarbonEngine.LIVESTOCK_TABLE's keys
    population_head: float
    productivity_system: str  # "high" | "low"


class LivestockScheduleIn(BaseModel):
    entries: list[LivestockEntry]


class LivestockScheduleOut(BaseModel):
    baseline: list[LivestockEntry] = []
    project: list[LivestockEntry] = []


class SocValuesIn(BaseModel):
    values: list[float]


class SocMeasurementsOut(BaseModel):
    # Tuple keys (site_type, timepoint) stringified as "{site_type}_{timepoint}",
    # matching report_generator.py's own JSON-export convention exactly, so
    # the frontend sees one consistent key format everywhere it meets this data.
    project_t_start: list[float] = []
    project_t_final: list[float] = []
    control_t_start: list[float] = []
    control_t_final: list[float] = []


class CompletenessOut(BaseModel):
    ready: bool
    problems: list[str]

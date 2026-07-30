"""
Registers the cropland ALM (VM0042) field type.

Unlike rice_awd, this field type has no satellite signal to analyze — VM0042
credits practice changes (fertilizer, tillage/residue, crop planting) on
non-wetland cropland, quantified from a manually entered baseline/project
practice schedule (Table 4) plus lab-measured soil organic carbon (SOC).
AlmPracticeValidator stands in for the SAR "detector" role: it checks that
schedule/SOC data is complete rather than analyzing a timeseries.
"""

from src.carbon_calculator_alm import AlmCarbonEngine
from src.field_types.registry import register_field_type

FIELD_TYPE_KEY = "cropland_alm_vm0042"


class AlmPracticeValidator:
    """
    Validates the manually entered ALM practice schedule and SOC measurements
    for a field before they're handed to AlmCarbonEngine. Not a SAR analyzer —
    VM0042 applies to non-wetland cropland/grassland (VM0042 §4, condition 8
    excludes wetlands/flooded rice), so there is no timeseries to process here.
    """

    REQUIRED_SOC_KEYS = [
        ("project", "t_start"), ("project", "t_final"),
        ("control", "t_start"), ("control", "t_final"),
    ]

    def check_completeness(self, practice_schedule: dict, soc_measurements: dict) -> list:
        """
        Returns a list of human-readable problems (empty list = ready to
        calculate). Does not raise — callers decide whether to block on issues.
        """
        problems = []

        if not practice_schedule.get("baseline"):
            problems.append("Baseline practice schedule is missing.")
        if not practice_schedule.get("project"):
            problems.append("Project practice schedule is missing.")

        for site_type, timepoint in self.REQUIRED_SOC_KEYS:
            values = soc_measurements.get((site_type, timepoint), [])
            if len(values) < 3:
                problems.append(
                    f"SOC samples for {site_type} site at {timepoint} — "
                    f"need >= 3, have {len(values)}."
                )

        return problems


register_field_type(
    FIELD_TYPE_KEY,
    label="Cropland — Improved Agricultural Land Management (VM0042)",
    detector_factory=AlmPracticeValidator,
    methodology_factory=AlmCarbonEngine,
    uses_sar=False,
)

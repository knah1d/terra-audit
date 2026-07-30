from src.field_types.registry import (
    build_detector, build_methodology, get_field_type, field_uses_sar,
)
from src.field_types import rice_awd    # noqa: F401 — registers "rice_awd" on import
from src.field_types import alm_vm0042  # noqa: F401 — registers "cropland_alm_vm0042" on import

__all__ = ["build_detector", "build_methodology", "get_field_type", "field_uses_sar"]

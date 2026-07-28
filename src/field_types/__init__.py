from src.field_types.registry import build_detector, build_methodology, get_field_type
from src.field_types import rice_awd  # noqa: F401 — registers "rice_awd" on import

__all__ = ["build_detector", "build_methodology", "get_field_type"]

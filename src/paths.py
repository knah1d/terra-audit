"""Stable repository paths shared by the API, worker and operational tools."""
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT_ROOT / "data"
METHODOLOGIES_DIR = PROJECT_ROOT / "methodologies"

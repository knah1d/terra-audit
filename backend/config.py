"""
Backend settings — .claude/plans/misty-growing-yao.md Part A1/A2.

Plain os.environ reads, not pydantic-settings: this app already has a
single .env-loading convention (python-dotenv, used by src/data_engine.py
for EE_PROJECT and src/database.py for DATABASE_URL) — adding a second
settings framework for 3 values isn't justified. JWT_SECRET has no safe
default in a real deployment; it falls back to a fixed dev-only string
ONLY so `uvicorn backend.main:app` works out of the box for local
development, with a loud warning so nobody ships that fallback by accident.
"""

import os
import warnings
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).parent.parent / ".env")

_DEV_ONLY_JWT_SECRET = "dev-only-insecure-secret-change-me"

JWT_SECRET = os.environ.get("JWT_SECRET")
if not JWT_SECRET:
    JWT_SECRET = _DEV_ONLY_JWT_SECRET
    warnings.warn(
        "JWT_SECRET not set — using an insecure development-only default. "
        "Set JWT_SECRET in .env before deploying this anywhere real.",
        stacklevel=2,
    )

JWT_ALGORITHM = "HS256"
JWT_EXPIRE_MINUTES = int(os.environ.get("JWT_EXPIRE_MINUTES", "720"))  # 12h default

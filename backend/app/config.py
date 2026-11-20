"""Environment configuration. Reads backend/.env if present; never contains secrets itself."""
from __future__ import annotations

import os
from pathlib import Path

try:  # python-dotenv is optional at import time so tests can run without deps
    from dotenv import load_dotenv

    _ENV_FILE = Path(__file__).resolve().parent.parent / ".env"
    if _ENV_FILE.exists():
        load_dotenv(_ENV_FILE)
except ImportError:  # pragma: no cover
    pass

APP_VERSION = "0.1.0"

GEMINI_API_KEY: str = os.getenv("GEMINI_API_KEY", "")
GEMINI_PRIMARY_MODEL: str = os.getenv(
    "GEMINI_PRIMARY_MODEL",
    os.getenv("GEMINI_MODEL", "gemini-4-carbon"),
)
GEMINI_FLASH_MODEL: str = os.getenv("GEMINI_FLASH_MODEL", "gemini-2.5-flash")
# Backward-compatible alias pointing to the primary configured model
GEMINI_MODEL: str = GEMINI_PRIMARY_MODEL

DB_PATH: str = os.getenv("DB_PATH", "./ledgerlens.db")
UPLOAD_DIR: str = os.getenv("UPLOAD_DIR", "./uploads")

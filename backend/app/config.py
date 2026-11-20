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
    os.getenv("GEMINI_MODEL", "gemini-3.8-vision-flash"),
)
GEMINI_FLASH_MODEL: str = os.getenv("GEMINI_FLASH_MODEL", "gemini-3.8-vision-flash")
# Backward-compatible alias pointing to the primary configured model
GEMINI_MODEL: str = GEMINI_PRIMARY_MODEL

DB_PATH: str = os.getenv("DB_PATH", "./ledgerlens.db")
UPLOAD_DIR: str = os.getenv("UPLOAD_DIR", "./uploads")

# Embedded knowledge graph (LadybugDB). Disabled by default in code so every
# pre-existing pytest suite keeps passing unchanged; enable via backend/.env
# (LEDGERLENS_GRAPH_ENABLED=true) or explicit GraphClient injection in tests.
GRAPH_ENABLED: bool = os.getenv("LEDGERLENS_GRAPH_ENABLED", "false").strip().lower() in (
    "1", "true", "yes", "on",
)
GRAPH_PATH: str = os.getenv("LEDGERLENS_GRAPH_PATH", "./data/ledgerlens.lbdb")
GRAPH_BUFFER_POOL_MB: int = int(os.getenv("LEDGERLENS_GRAPH_BUFFER_POOL_MB", "256"))

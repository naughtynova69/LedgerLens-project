"""SQLite helpers. Schema lives in backend/schema.sql (see docs/03_DATA_MODEL.md).

SQLite is the MVP choice; the schema is portable to Cloud SQL without redesign.
"""
from __future__ import annotations

from pathlib import Path
import sqlite3

from . import config

_SCHEMA_PATH = Path(__file__).resolve().parent.parent / "schema.sql"


def get_connection(db_path: str | None = None) -> sqlite3.Connection:
    """Open a connection with row access by name and FK checks on."""
    path = db_path or config.DB_PATH
    if path == ":memory:":
        conn = sqlite3.connect(":memory:")
    else:
        db_file = Path(path)
        db_file.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(str(db_file))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_schema(conn: sqlite3.Connection) -> None:
    """Apply schema.sql to an open connection (idempotent)."""
    conn.executescript(_SCHEMA_PATH.read_text(encoding="utf-8"))
    conn.commit()


def init_db(db_path: str | None = None) -> None:
    """Open (creating if needed), apply schema, close."""
    conn = get_connection(db_path)
    try:
        init_schema(conn)
    finally:
        conn.close()

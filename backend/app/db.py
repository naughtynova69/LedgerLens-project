"""SQLite helpers. Schema lives in backend/schema.sql (see docs/03_DATA_MODEL.md).

SQLite is the MVP choice; the schema is portable to Cloud SQL without redesign.
"""
from __future__ import annotations

from pathlib import Path
import sqlite3

from . import config

_SCHEMA_PATH = Path(__file__).resolve().parent.parent / "schema.sql"


def get_connection(db_path: str | None = None) -> sqlite3.Connection:
    """Open a connection with row access by name, WAL concurrency, and FK checks on."""
    path = db_path or config.DB_PATH
    if path == ":memory:":
        conn = sqlite3.connect(":memory:", check_same_thread=False)
    else:
        db_file = Path(path)
        db_file.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(str(db_file), timeout=5.0, check_same_thread=False)
        conn.execute("PRAGMA journal_mode = WAL")
        conn.execute("PRAGMA synchronous = NORMAL")
        conn.execute("PRAGMA busy_timeout = 5000")
        conn.execute("PRAGMA temp_store = MEMORY")
        conn.execute("PRAGMA cache_size = -16000")
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_schema(conn: sqlite3.Connection) -> None:
    """Apply schema.sql to an open connection (idempotent)."""
    conn.executescript(_SCHEMA_PATH.read_text(encoding="utf-8"))
    cols = {r["name"] for r in conn.execute("PRAGMA table_info(findings)").fetchall()}
    if "recommended_action" not in cols:
        conn.execute("ALTER TABLE findings ADD COLUMN recommended_action TEXT NOT NULL DEFAULT ''")
    if "proof_trail" not in cols:
        conn.execute("ALTER TABLE findings ADD COLUMN proof_trail TEXT NOT NULL DEFAULT '{}'")
    for table_name in (
        "batches",
        "invoices",
        "contracts",
        "purchase_orders",
        "payments",
        "findings",
        "audit_log",
    ):
        t_cols = {r["name"] for r in conn.execute(f"PRAGMA table_info({table_name})").fetchall()}
        if "workspace_id" not in t_cols:
            conn.execute(
                f"ALTER TABLE {table_name} ADD COLUMN workspace_id TEXT NOT NULL DEFAULT 'default'"
            )
    _migrate_graph_columns(conn)
    conn.commit()


def _migrate_graph_columns(conn: sqlite3.Connection) -> None:
    """Backward-compatible nullable columns for the graph projection.

    schema.sql covers fresh databases; these guarded static ALTERs upgrade
    databases created before the knowledge-graph layer existed. Statements are
    fully static literals — identifiers are never interpolated.
    """
    vendors_cols = {r["name"] for r in conn.execute('PRAGMA table_info("vendors")').fetchall()}
    if vendors_cols:
        if "bank_account" not in vendors_cols:
            conn.execute('ALTER TABLE "vendors" ADD COLUMN bank_account TEXT')
        if "email" not in vendors_cols:
            conn.execute('ALTER TABLE "vendors" ADD COLUMN email TEXT')
        if "phone" not in vendors_cols:
            conn.execute('ALTER TABLE "vendors" ADD COLUMN phone TEXT')
        if "address" not in vendors_cols:
            conn.execute('ALTER TABLE "vendors" ADD COLUMN address TEXT')

    invoices_cols = {r["name"] for r in conn.execute('PRAGMA table_info("invoices")').fetchall()}
    if invoices_cols and "approver_id" not in invoices_cols:
        conn.execute('ALTER TABLE "invoices" ADD COLUMN approver_id TEXT')

    contracts_cols = {r["name"] for r in conn.execute('PRAGMA table_info("contracts")').fetchall()}
    if contracts_cols:
        if "amends_contract_id" not in contracts_cols:
            conn.execute('ALTER TABLE "contracts" ADD COLUMN amends_contract_id TEXT')
        if "version" not in contracts_cols:
            conn.execute('ALTER TABLE "contracts" ADD COLUMN version INTEGER NOT NULL DEFAULT 1')

    payments_cols = {r["name"] for r in conn.execute('PRAGMA table_info("payments")').fetchall()}
    if payments_cols and "account_key" not in payments_cols:
        conn.execute('ALTER TABLE "payments" ADD COLUMN account_key TEXT')


def init_db(db_path: str | None = None) -> None:
    """Open (creating if needed), apply schema, close."""
    conn = get_connection(db_path)
    try:
        init_schema(conn)
    finally:
        conn.close()

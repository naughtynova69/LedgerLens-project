"""AlloyDB / PostgreSQL connectivity, schema bootstrap, and SQLite export helpers."""

from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass
from pathlib import Path
import sqlite3
from typing import Any

logger = logging.getLogger(__name__)

_POSTGRES_SCHEMA_PATH = Path(__file__).resolve().parent.parent.parent / "schema_postgres.sql"
_ALLOWED_ALLOYDB_BACKENDS = {"", "alloydb", "postgres", "postgresql"}


@dataclass(frozen=True)
class _TableSpec:
    name: str
    columns: tuple[str, ...]
    conflict_columns: tuple[str, ...]
    jsonb_defaults: dict[str, tuple[str, bool]] | None = None
    serial_column: str | None = None


# Ordered to satisfy foreign-key dependencies during bulk export.
_EXPORT_TABLES: tuple[_TableSpec, ...] = (
    _TableSpec(
        name="vendors",
        columns=("vendor_id", "vendor_name", "tax_id", "default_currency", "status"),
        conflict_columns=("vendor_id",),
    ),
    _TableSpec(
        name="contracts",
        columns=(
            "contract_id",
            "vendor_id",
            "item",
            "contracted_unit_price",
            "currency",
            "discount_pct",
            "payment_terms",
            "tax_pct",
            "start_date",
            "end_date",
            "status",
        ),
        conflict_columns=("contract_id", "item"),
    ),
    _TableSpec(
        name="purchase_orders",
        columns=(
            "po_id",
            "po_line",
            "vendor_id",
            "item",
            "quantity",
            "unit_price",
            "currency",
            "order_date",
            "expected_delivery",
            "status",
        ),
        conflict_columns=("po_id", "po_line"),
    ),
    _TableSpec(
        name="invoices",
        columns=(
            "invoice_number",
            "vendor_id",
            "invoice_date",
            "po_id",
            "line_no",
            "item",
            "quantity",
            "unit_price",
            "currency",
            "tax_pct",
            "line_total",
            "source_file",
            "status",
        ),
        conflict_columns=("invoice_number", "line_no"),
    ),
    _TableSpec(
        name="payments",
        columns=(
            "payment_id",
            "invoice_number",
            "amount",
            "currency",
            "fx_rate_to_inr",
            "payment_date",
            "status",
        ),
        conflict_columns=("payment_id",),
    ),
    _TableSpec(
        name="batches",
        columns=("batch_id", "kind", "stored_path", "rows_detected", "state", "created_at"),
        conflict_columns=("batch_id",),
    ),
    _TableSpec(
        name="findings",
        columns=(
            "finding_id",
            "rule_id",
            "title",
            "severity",
            "amount_at_risk",
            "currency",
            "status",
            "entity_refs",
            "evidence",
            "confidence",
            "summary",
            "explanation",
            "recommended_action",
            "proof_trail",
            "created_at",
        ),
        conflict_columns=("finding_id",),
        jsonb_defaults={
            "entity_refs": ("{}", False),
            "evidence": ("[]", False),
            "explanation": ("null", True),
            "proof_trail": ("{}", False),
        },
    ),
    _TableSpec(
        name="decisions",
        columns=("id", "finding_id", "action", "reviewer", "note", "created_at"),
        conflict_columns=("id",),
        serial_column="id",
    ),
    _TableSpec(
        name="audit_log",
        columns=("id", "ts", "actor", "action", "object_type", "object_id", "detail"),
        conflict_columns=("id",),
        serial_column="id",
    ),
    _TableSpec(
        name="policy_settings",
        columns=("key", "value", "updated_at"),
        conflict_columns=("key",),
    ),
)


def _read_env() -> dict[str, str]:
    """Read AlloyDB / Postgres environment variables dynamically."""
    return {
        "db_backend": os.getenv("DB_BACKEND", "").strip().lower(),
        "instance_uri": os.getenv("ALLOYDB_INSTANCE_URI", "").strip(),
        "user": os.getenv("ALLOYDB_USER", "postgres").strip() or "postgres",
        "password": os.getenv("ALLOYDB_PASS", ""),
        "database": os.getenv("ALLOYDB_DB", "ledgerlens").strip() or "ledgerlens",
        "database_url": os.getenv("DATABASE_URL", "").strip(),
    }


def is_alloydb_configured() -> bool:
    """Return True when AlloyDB or Postgres connection settings are active."""
    env = _read_env()
    if env["db_backend"] == "sqlite":
        return False
    if env["db_backend"] not in _ALLOWED_ALLOYDB_BACKENDS:
        return False
    return bool(env["instance_uri"] or env["database_url"])


def _open_alloydb_connection() -> Any:
    """Open a DB-API connection via AlloyDB Connector (pg8000) or psycopg."""
    env = _read_env()
    if env["db_backend"] == "sqlite":
        raise RuntimeError("DB_BACKEND is explicitly set to sqlite.")

    instance_uri = env["instance_uri"]
    if instance_uri:
        from google.cloud.alloydb.connector import Connector

        connector = Connector()
        try:
            conn = connector.connect(
                instance_uri,
                "pg8000",
                user=env["user"],
                password=env["password"],
                db=env["database"],
            )
        except Exception:
            connector.close()
            raise
        try:
            setattr(conn, "_alloydb_connector", connector)
        except Exception:
            pass
        return conn

    database_url = env["database_url"]
    if database_url:
        import psycopg

        return psycopg.connect(database_url)

    raise RuntimeError(
        "AlloyDB is not configured: set ALLOYDB_INSTANCE_URI or DATABASE_URL."
    )


def _close_connection(conn: Any) -> None:
    """Close a DB-API connection and any attached AlloyDB Connector."""
    connector = getattr(conn, "_alloydb_connector", None) if conn is not None else None
    try:
        if conn is not None:
            conn.close()
    finally:
        if connector is not None:
            connector.close()


def _split_sql_statements(sql_text: str) -> list[str]:
    """Strip SQL line comments and split DDL text into executable statements."""
    stripped_lines = [
        line for line in sql_text.splitlines() if not line.lstrip().startswith("--")
    ]
    cleaned = "\n".join(stripped_lines)
    return [stmt.strip() for stmt in cleaned.split(";") if stmt.strip()]


def _serialize_jsonb(value: Any, default_json: str, nullable: bool) -> str | None:
    """Normalize SQLite JSON text or Python objects for JSONB parameter binding."""
    if value is None:
        return None if nullable else default_json
    if isinstance(value, (dict, list)):
        return json.dumps(value)
    if isinstance(value, str):
        text = value.strip()
        if not text:
            return None if nullable else default_json
        try:
            json.loads(text)
            return text
        except json.JSONDecodeError:
            return json.dumps(text)
    return json.dumps(value)


def _sqlite_existing_tables(sqlite_conn: sqlite3.Connection) -> set[str]:
    rows = sqlite_conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table'"
    ).fetchall()
    return {row[0] for row in rows}


def _count_sqlite_rows(
    sqlite_conn: sqlite3.Connection, existing_tables: set[str]
) -> dict[str, int]:
    """Count rows per export table using fully static SQL literals.

    Table identifiers cannot be passed as bound parameters, so each statement
    is written out in full — no dynamically constructed SQL text anywhere.
    """
    counts: dict[str, int] = {spec.name: 0 for spec in _EXPORT_TABLES}
    for spec in _EXPORT_TABLES:
        if spec.name not in existing_tables:
            continue
        match spec.name:
            case "vendors":
                row = sqlite_conn.execute('SELECT COUNT(*) FROM "vendors"').fetchone()
            case "contracts":
                row = sqlite_conn.execute('SELECT COUNT(*) FROM "contracts"').fetchone()
            case "purchase_orders":
                row = sqlite_conn.execute('SELECT COUNT(*) FROM "purchase_orders"').fetchone()
            case "invoices":
                row = sqlite_conn.execute('SELECT COUNT(*) FROM "invoices"').fetchone()
            case "payments":
                row = sqlite_conn.execute('SELECT COUNT(*) FROM "payments"').fetchone()
            case "batches":
                row = sqlite_conn.execute('SELECT COUNT(*) FROM "batches"').fetchone()
            case "findings":
                row = sqlite_conn.execute('SELECT COUNT(*) FROM "findings"').fetchone()
            case "decisions":
                row = sqlite_conn.execute('SELECT COUNT(*) FROM "decisions"').fetchone()
            case "audit_log":
                row = sqlite_conn.execute('SELECT COUNT(*) FROM "audit_log"').fetchone()
            case "policy_settings":
                row = sqlite_conn.execute('SELECT COUNT(*) FROM "policy_settings"').fetchone()
            case _:
                continue
        counts[spec.name] = int(row[0]) if row else 0
    return counts


def _build_upsert_sql(spec: _TableSpec, active_columns: list[str]) -> str:
    """Build a parameterized PostgreSQL ON CONFLICT DO UPDATE statement."""
    col_list = ", ".join(active_columns)
    jsonb_cols = spec.jsonb_defaults or {}
    placeholders = ", ".join(
        "CAST(%s AS JSONB)" if col in jsonb_cols else "%s" for col in active_columns
    )
    conflict_list = ", ".join(spec.conflict_columns)
    update_cols = [col for col in active_columns if col not in spec.conflict_columns]
    if update_cols:
        assignments = ", ".join(f"{col} = EXCLUDED.{col}" for col in update_cols)
        conflict_clause = f"ON CONFLICT ({conflict_list}) DO UPDATE SET {assignments}"
    else:
        conflict_clause = f"ON CONFLICT ({conflict_list}) DO NOTHING"
    return f"INSERT INTO {spec.name} ({col_list}) VALUES ({placeholders}) {conflict_clause}"


def check_alloydb_connection() -> dict[str, Any]:
    """Verify AlloyDB/Postgres connectivity with SELECT 1 or report SQLite fallback."""
    if not is_alloydb_configured():
        return {
            "configured": False,
            "mode": "sqlite_fallback",
            "connected": False,
            "detail": "AlloyDB not configured; using SQLite fallback.",
        }

    conn = None
    try:
        conn = _open_alloydb_connection()
        cur = conn.cursor()
        cur.execute("SELECT 1")
        cur.fetchone()
        return {
            "configured": True,
            "mode": "alloydb",
            "connected": True,
            "detail": "Connected to AlloyDB/PostgreSQL (SELECT 1 succeeded).",
        }
    except Exception as exc:
        logger.warning("AlloyDB connectivity check failed: %s", exc)
        return {
            "configured": True,
            "mode": "alloydb",
            "connected": False,
            "detail": str(exc),
        }
    finally:
        _close_connection(conn)


def init_alloydb_schema() -> dict[str, Any]:
    """Apply backend/schema_postgres.sql statements idempotently when configured."""
    if not is_alloydb_configured():
        return {
            "applied": False,
            "mode": "sqlite_fallback",
        }

    statements = _split_sql_statements(_POSTGRES_SCHEMA_PATH.read_text(encoding="utf-8"))
    conn = None
    try:
        conn = _open_alloydb_connection()
        cur = conn.cursor()
        for statement in statements:
            cur.execute(statement)
        conn.commit()
        return {
            "applied": True,
            "mode": "alloydb",
            "statements_executed": len(statements),
            "schema_path": str(_POSTGRES_SCHEMA_PATH),
        }
    except Exception as exc:
        logger.warning("Failed to initialize AlloyDB schema: %s", exc)
        if conn is not None:
            try:
                conn.rollback()
            except Exception:
                pass
        return {
            "applied": False,
            "mode": "alloydb",
            "error": str(exc),
        }
    finally:
        _close_connection(conn)


def export_sqlite_to_alloydb(sqlite_conn: sqlite3.Connection) -> dict[str, Any]:
    """Count local SQLite rows and upsert them into AlloyDB when configured."""
    existing_tables = _sqlite_existing_tables(sqlite_conn)
    row_counts = _count_sqlite_rows(sqlite_conn, existing_tables)

    if not is_alloydb_configured():
        return {
            "exported": False,
            "mode": "sqlite_fallback",
            "row_counts": row_counts,
        }

    conn = None
    try:
        conn = _open_alloydb_connection()
        pg_cur = conn.cursor()

        for spec in _EXPORT_TABLES:
            if spec.name not in existing_tables or row_counts[spec.name] == 0:
                continue

            match spec.name:
                case "vendors":
                    sq_cur = sqlite_conn.execute('SELECT * FROM "vendors"')
                case "contracts":
                    sq_cur = sqlite_conn.execute('SELECT * FROM "contracts"')
                case "purchase_orders":
                    sq_cur = sqlite_conn.execute('SELECT * FROM "purchase_orders"')
                case "invoices":
                    sq_cur = sqlite_conn.execute('SELECT * FROM "invoices"')
                case "payments":
                    sq_cur = sqlite_conn.execute('SELECT * FROM "payments"')
                case "batches":
                    sq_cur = sqlite_conn.execute('SELECT * FROM "batches"')
                case "findings":
                    sq_cur = sqlite_conn.execute('SELECT * FROM "findings"')
                case "decisions":
                    sq_cur = sqlite_conn.execute('SELECT * FROM "decisions"')
                case "audit_log":
                    sq_cur = sqlite_conn.execute('SELECT * FROM "audit_log"')
                case "policy_settings":
                    sq_cur = sqlite_conn.execute('SELECT * FROM "policy_settings"')
                case _:
                    raise ValueError(
                        f"table identifier not on export whitelist: {spec.name}"
                    )
            col_names = [desc[0] for desc in sq_cur.description]
            active_columns = [col for col in spec.columns if col in col_names]
            col_indices = [col_names.index(col) for col in active_columns]
            upsert_sql = _build_upsert_sql(spec, active_columns)
            jsonb_cols = spec.jsonb_defaults or {}

            for raw_row in sq_cur.fetchall():
                params: list[Any] = []
                for col, idx in zip(active_columns, col_indices):
                    val = raw_row[idx]
                    if col in jsonb_cols:
                        default_json, nullable = jsonb_cols[col]
                        val = _serialize_jsonb(val, default_json, nullable)
                    params.append(val)
                pg_cur.execute(upsert_sql, tuple(params))

            if spec.serial_column:
                pg_cur.execute(
                    f"SELECT setval(pg_get_serial_sequence('{spec.name}', '{spec.serial_column}'), "
                    f"COALESCE((SELECT MAX({spec.serial_column}) FROM {spec.name}), 1))"
                )

        conn.commit()
        return {
            "exported": True,
            "mode": "alloydb",
            "row_counts": row_counts,
            "total_rows": sum(row_counts.values()),
        }
    except Exception as exc:
        logger.warning("SQLite to AlloyDB export failed: %s", exc)
        if conn is not None:
            try:
                conn.rollback()
            except Exception:
                pass
        return {
            "exported": False,
            "mode": "alloydb",
            "row_counts": row_counts,
            "error": str(exc),
        }
    finally:
        _close_connection(conn)

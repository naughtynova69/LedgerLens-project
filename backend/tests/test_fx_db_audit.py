"""Unit tests for Live FX Service (Track #4), DBAdapter (Track #8), and Audit Chain (Track #10)."""
from __future__ import annotations

import io
import json
import sqlite3
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

BACKEND_DIR = Path(__file__).resolve().parent.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.audit_chain import (
    GENESIS_HASH,
    append_chained_audit_event,
    compute_entry_hash,
    verify_audit_chain,
)
from app.db_adapter import DBAdapter
from app.normalize.fx_service import get_fx_rates
from app.normalize.normalize import REFERENCE_FX_RATES


# ---------------------------------------------------------------------------
# Track #4: Live FX Rate Service
# ---------------------------------------------------------------------------


def test_fx_offline_fallback_without_conn() -> None:
    rates = get_fx_rates(conn=None, fetch_live=False)
    assert rates == REFERENCE_FX_RATES
    assert rates["INR"] == 1.0


def test_fx_caches_reference_and_reads_from_db() -> None:
    conn = sqlite3.connect(":memory:")
    try:
        rates_first = get_fx_rates(conn=conn, fetch_live=False)
        assert rates_first["USD"] == REFERENCE_FX_RATES["USD"]

        # Update cached rate in DB and verify subsequent offline call reads it
        conn.execute(
            "INSERT OR REPLACE INTO fx_rates (currency, rate_to_inr, as_of_date, source) "
            "VALUES (?, ?, ?, ?)",
            ("USD", 90.25, "2026-11-20", "manual_test"),
        )
        conn.commit()

        rates_cached = get_fx_rates(conn=conn, fetch_live=False)
        assert rates_cached["USD"] == 90.25
        assert rates_cached["INR"] == 1.0
    finally:
        conn.close()


def test_fx_live_fetch_inverts_and_persists() -> None:
    conn = sqlite3.connect(":memory:")
    payload = {
        "amount": 1.0,
        "base": "INR",
        "date": "2026-11-20",
        "rates": {"USD": 0.0112, "EUR": 0.0104},
    }

    class _FakeResp(io.BytesIO):
        def __enter__(self):
            return self

        def __exit__(self, *args):
            self.close()

    try:
        with patch(
            "app.normalize.fx_service.urllib.request.urlopen",
            return_value=_FakeResp(json.dumps(payload).encode("utf-8")),
        ):
            rates = get_fx_rates(conn=conn, fetch_live=True)

        assert rates["INR"] == 1.0
        assert rates["USD"] == pytest.approx(round(1.0 / 0.0112, 6))
        assert rates["EUR"] == pytest.approx(round(1.0 / 0.0104, 6))

        row = conn.execute(
            "SELECT rate_to_inr, as_of_date, source FROM fx_rates WHERE currency = 'USD'"
        ).fetchone()
        assert row is not None
        assert row[0] == pytest.approx(round(1.0 / 0.0112, 6))
        assert row[1] == "2026-11-20"
        assert row[2] == "frankfurter"
    finally:
        conn.close()


def test_fx_live_fetch_failure_falls_back_to_cache_or_reference() -> None:
    conn = sqlite3.connect(":memory:")
    try:
        with patch(
            "app.normalize.fx_service.urllib.request.urlopen",
            side_effect=OSError("network down"),
        ):
            rates = get_fx_rates(conn=conn, fetch_live=True)
        assert rates == REFERENCE_FX_RATES
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Track #8: DBAdapter (SQLite / Postgres / AlloyDB)
# ---------------------------------------------------------------------------


def test_db_adapter_adapt_sql_dialects() -> None:
    sql = "SELECT * FROM invoices WHERE vendor_id = ? AND note != 'why?' -- keep ?"
    assert DBAdapter.adapt_sql(sql, "sqlite") == sql
    pg_sql = DBAdapter.adapt_sql(sql, "postgres")
    assert pg_sql == "SELECT * FROM invoices WHERE vendor_id = %s AND note != 'why?' -- keep ?"
    assert DBAdapter.adapt_sql("SELECT ? FROM \"col?\"", "alloydb") == 'SELECT %s FROM "col?"'

    with pytest.raises(ValueError):
        DBAdapter.adapt_sql(sql, "mysql")


def test_db_adapter_upsert_sql() -> None:
    sqlite_sql = DBAdapter.upsert_sql(
        "vendors", ["vendor_id", "vendor_name", "status"], ["vendor_id"], "sqlite"
    )
    assert sqlite_sql == (
        "INSERT OR REPLACE INTO vendors (vendor_id, vendor_name, status) VALUES (?, ?, ?)"
    )

    pg_sql = DBAdapter.upsert_sql(
        "vendors", ["vendor_id", "vendor_name", "status"], ["vendor_id"], "postgres"
    )
    assert pg_sql == (
        "INSERT INTO vendors (vendor_id, vendor_name, status) VALUES (%s, %s, %s) "
        "ON CONFLICT (vendor_id) DO UPDATE SET vendor_name = EXCLUDED.vendor_name, "
        "status = EXCLUDED.status"
    )

    pg_noop = DBAdapter.upsert_sql("tags", ["id", "name"], ["id", "name"], "alloydb")
    assert pg_noop.endswith("ON CONFLICT (id, name) DO NOTHING")


def test_db_adapter_execute_and_fetchall_dicts_sqlite() -> None:
    conn = sqlite3.connect(":memory:")
    try:
        DBAdapter.execute(
            conn,
            "CREATE TABLE items (id TEXT PRIMARY KEY, qty INTEGER)",
            dialect="sqlite",
        )
        upsert = DBAdapter.upsert_sql("items", ["id", "qty"], ["id"], "sqlite")
        DBAdapter.execute(conn, upsert, ("A1", 5), dialect="sqlite")
        DBAdapter.execute(conn, upsert, ("A1", 9), dialect="sqlite")
        conn.commit()

        rows = DBAdapter.fetchall_dicts(
            conn, "SELECT id, qty FROM items WHERE id = ?", ("A1",), dialect="sqlite"
        )
        assert rows == [{"id": "A1", "qty": 9}]
    finally:
        conn.close()


def test_db_adapter_fetchall_dicts_postgres_mock() -> None:
    executed: list[tuple[str, tuple]] = []

    class _FakeCursor:
        description = [("vendor_id",), ("status",)]

        def execute(self, sql, params):
            executed.append((sql, params))

        def fetchall(self):
            return [("V1", "active")]

        def close(self):
            pass

    class _FakeConn:
        def cursor(self):
            return _FakeCursor()

    rows = DBAdapter.fetchall_dicts(
        _FakeConn(),
        "SELECT vendor_id, status FROM vendors WHERE vendor_id = ?",
        ("V1",),
        dialect="postgres",
    )
    assert executed == [("SELECT vendor_id, status FROM vendors WHERE vendor_id = %s", ("V1",))]
    assert rows == [{"vendor_id": "V1", "status": "active"}]


# ---------------------------------------------------------------------------
# Track #10: Cryptographic Audit Hash-Chaining
# ---------------------------------------------------------------------------


def test_compute_entry_hash_is_deterministic_and_sensitive() -> None:
    h1 = compute_entry_hash(GENESIS_HASH, "2026-11-20T00:00:00Z", "alice", "approve", "finding", "F-1", "ok")
    h2 = compute_entry_hash(GENESIS_HASH, "2026-11-20T00:00:00Z", "alice", "approve", "finding", "F-1", "ok")
    h3 = compute_entry_hash(GENESIS_HASH, "2026-11-20T00:00:00Z", "alice", "approve", "finding", "F-1", "tampered")
    assert h1 == h2
    assert len(h1) == 64
    assert h1 != h3


def test_audit_chain_append_verify_and_tamper_detection() -> None:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    try:
        assert verify_audit_chain([]) == {"valid": True, "checked": 0, "broken_at_id": None}

        e1 = append_chained_audit_event(
            conn, "alice", "ingest", "batch", "B-1", "uploaded", ts="2026-11-20T01:00:00Z"
        )
        e2 = append_chained_audit_event(
            conn, "bob", "flag", "finding", "F-1", "duplicate", ts="2026-11-20T01:01:00Z"
        )
        e3 = append_chained_audit_event(
            conn, "carol", "approve", "finding", "F-1", "verified", ts="2026-11-20T01:02:00Z"
        )

        assert e1["prev_hash"] == GENESIS_HASH
        assert e2["prev_hash"] == e1["entry_hash"]
        assert e3["prev_hash"] == e2["entry_hash"]

        rows = conn.execute("SELECT * FROM audit_chain ORDER BY id ASC").fetchall()
        assert verify_audit_chain(rows) == {"valid": True, "checked": 3, "broken_at_id": None}

        # Tamper with row 2's detail without recomputing hashes
        conn.execute("UPDATE audit_chain SET detail = 'forged' WHERE id = ?", (e2["id"],))
        conn.commit()
        tampered_rows = conn.execute("SELECT * FROM audit_chain ORDER BY id ASC").fetchall()
        assert verify_audit_chain(tampered_rows) == {
            "valid": False,
            "checked": 2,
            "broken_at_id": e2["id"],
        }

        # Restore row 2's detail, but break row 3's prev_hash link
        conn.execute("UPDATE audit_chain SET detail = 'duplicate' WHERE id = ?", (e2["id"],))
        conn.execute("UPDATE audit_chain SET prev_hash = ? WHERE id = ?", ("f" * 64, e3["id"]))
        conn.commit()
        broken_link_rows = conn.execute("SELECT * FROM audit_chain ORDER BY id ASC").fetchall()
        assert verify_audit_chain(broken_link_rows) == {
            "valid": False,
            "checked": 3,
            "broken_at_id": e3["id"],
        }
    finally:
        conn.close()

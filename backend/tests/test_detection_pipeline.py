"""End-to-end pipeline test: sqlite -> services.run_detection -> decision -> memo."""
import pytest

from app.db import get_connection, init_schema
from app.services import build_memo, record_decision, run_detection


@pytest.fixture()
def conn():
    conn = get_connection(":memory:")
    init_schema(conn)
    conn.execute(
        "INSERT INTO vendors (vendor_id, vendor_name, default_currency) "
        "VALUES ('V001', 'Sunbeam Electricals', 'INR')")
    conn.executemany(
        """INSERT INTO invoices
           (invoice_number, vendor_id, invoice_date, po_id, line_no, item,
            quantity, unit_price, currency, tax_pct, line_total, status)
           VALUES (?, 'V001', ?, 'PO-1001', 1, 'LED Panel 18W',
                   10, 420.0, 'INR', 18.0, 4956.0, ?)""",
        [("INV-8821", "2026-10-14", "paid"),
         ("INV-8821-R2", "2026-10-16", "paid")],
    )
    conn.executemany(
        """INSERT INTO payments
           (payment_id, invoice_number, amount, currency, fx_rate_to_inr, payment_date)
           VALUES (?, ?, 4956.0, 'INR', 1.0, ?)""",
        [("PAY-5001", "INV-8821", "2026-10-20"),
         ("PAY-5002", "INV-8821-R2", "2026-10-22")],
    )
    conn.commit()
    yield conn
    conn.close()


def test_pipeline_creates_the_duplicate_finding(conn):
    result = run_detection(conn)
    assert result["findings_created"] == 1

    row = conn.execute("SELECT * FROM findings WHERE finding_id = ?",
                       (result["finding_ids"][0],)).fetchone()
    assert row["rule_id"] == "R1"
    assert row["severity"] == "critical"
    assert row["amount_at_risk"] == 4956.0
    assert row["status"] == "open"


def test_decision_updates_status_and_writes_audit_log(conn):
    result = run_detection(conn)
    finding_id = result["finding_ids"][0]

    out = record_decision(conn, finding_id, "reject", "avani", "Confirmed duplicate.")
    assert out["status"] == "rejected"
    assert conn.execute("SELECT status FROM findings WHERE finding_id = ?",
                        (finding_id,)).fetchone()["status"] == "rejected"
    assert conn.execute("SELECT COUNT(*) AS n FROM audit_log").fetchone()["n"] == 2
    assert conn.execute("SELECT COUNT(*) AS n FROM audit_log WHERE action = 'reject'").fetchone()["n"] == 1
    assert conn.execute("SELECT COUNT(*) AS n FROM audit_log WHERE action = 'detect'").fetchone()["n"] == 1


def test_memo_contains_totals(conn):
    run_detection(conn)
    memo = build_memo(conn)
    assert "# LedgerLens Audit Memo" in memo
    assert "4,956.00" in memo

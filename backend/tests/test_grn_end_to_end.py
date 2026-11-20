"""End-to-end tests for goods_receipts schema, CSV validation, ingest, and R7 detection."""
from __future__ import annotations

import json

from app.db import get_connection, init_schema
from app.ingest.router import VALID_KINDS, validate_csv
from app.services import ingest_csv_file_to_table, run_detection


def _write(tmp_path, name: str, content: str):
    path = tmp_path / name
    path.write_text(content, encoding="utf-8")
    return path


def _setup_db():
    conn = get_connection(":memory:")
    init_schema(conn)
    return conn


def test_validate_csv_goods_receipts_valid_and_invalid(tmp_path):
    assert "goods_receipts" in VALID_KINDS

    valid_csv = (
        "grn_id,po_id,po_line,vendor_id,item,received_qty,accepted_qty,received_date\n"
        "GRN-1,PO-100,1,V001,Server Rack,10,8,2026-11-01\n"
    )
    valid_path = _write(tmp_path, "grn_valid.csv", valid_csv)
    assert validate_csv(valid_path, "goods_receipts") == []

    missing_cols_path = _write(
        tmp_path,
        "grn_missing.csv",
        "grn_id,po_id\nGRN-1,PO-100\n",
    )
    problems = validate_csv(missing_cols_path, "goods_receipts")
    assert len(problems) == 1
    assert "missing required columns" in problems[0]
    assert "item" in problems[0]
    assert "received_qty" in problems[0]


def test_grn_ingest_and_r7_detection_fires_on_excess_qty(tmp_path):
    conn = _setup_db()
    try:
        inv_csv = _write(
            tmp_path,
            "invoices.csv",
            "invoice_number,vendor_id,invoice_date,po_id,line_no,item,quantity,unit_price,currency,tax_pct,line_total,status\n"
            "INV-1001,V001,2026-11-05,PO-100,1,Server Rack,10,100.0,INR,0,1000.0,unpaid\n",
        )
        grn_csv = _write(
            tmp_path,
            "grn.csv",
            "grn_id,po_id,po_line,vendor_id,item,received_qty,accepted_qty,received_date\n"
            "GRN-1,PO-100,1,V001,Server Rack,10,7,2026-11-01\n",
        )

        assert ingest_csv_file_to_table(conn, inv_csv, "invoices") == 1
        assert ingest_csv_file_to_table(conn, grn_csv, "goods_receipts") == 1

        res = run_detection(conn)
        assert res["findings_created"] >= 1

        r7_rows = conn.execute(
            "SELECT * FROM findings WHERE rule_id = 'R7'"
        ).fetchall()
        assert len(r7_rows) == 1
        refs = json.loads(r7_rows[0]["entity_refs"])
        assert refs["po_id"] == "PO-100"
        assert r7_rows[0]["amount_at_risk"] == 300.0
    finally:
        conn.close()


def test_grn_ingest_and_r7_fallback_to_received_qty_and_clean_match(tmp_path):
    conn = _setup_db()
    try:
        # Blank accepted_qty should fall back to received_qty (8) -> billed 10 > 8 fires R7
        inv_csv = _write(
            tmp_path,
            "invoices_excess.csv",
            "invoice_number,vendor_id,invoice_date,po_id,line_no,item,quantity,unit_price,currency,tax_pct,line_total,status\n"
            "INV-2001,V002,2026-11-05,PO-200,1,Fiber Switch,10,50.0,INR,0,500.0,unpaid\n",
        )
        grn_csv = _write(
            tmp_path,
            "grn_blank_accepted.csv",
            "grn_id,po_id,po_line,vendor_id,item,received_qty,accepted_qty,received_date\n"
            "GRN-2,PO-200,1,V002,Fiber Switch,8,,2026-11-02\n",
        )
        ingest_csv_file_to_table(conn, inv_csv, "invoices")
        ingest_csv_file_to_table(conn, grn_csv, "goods_receipts")

        run_detection(conn)
        r7_rows = conn.execute("SELECT * FROM findings WHERE rule_id = 'R7'").fetchall()
        assert len(r7_rows) == 1
        assert r7_rows[0]["amount_at_risk"] == 100.0
    finally:
        conn.close()

    # Now verify 0 R7 findings when invoiced qty matches GRN accepted_qty
    conn2 = _setup_db()
    try:
        inv_ok = _write(
            tmp_path,
            "invoices_ok.csv",
            "invoice_number,vendor_id,invoice_date,po_id,line_no,item,quantity,unit_price,currency,tax_pct,line_total,status\n"
            "INV-3001,V003,2026-11-05,PO-300,1,Patch Cable,5,20.0,INR,0,100.0,unpaid\n",
        )
        grn_ok = _write(
            tmp_path,
            "grn_ok.csv",
            "grn_id,po_id,po_line,vendor_id,item,received_qty,accepted_qty,received_date\n"
            "GRN-3,PO-300,1,V003,Patch Cable,5,5,2026-11-02\n",
        )
        ingest_csv_file_to_table(conn2, inv_ok, "invoices")
        ingest_csv_file_to_table(conn2, grn_ok, "goods_receipts")

        run_detection(conn2)
        r7_rows = conn2.execute("SELECT * FROM findings WHERE rule_id = 'R7'").fetchall()
        assert r7_rows == []
    finally:
        conn2.close()


def test_grn_workspace_isolation(tmp_path):
    conn = _setup_db()
    try:
        # Workspace A: invoice bills 10, GRN accepted 4 -> R7 should fire in ws_a
        inv_a = _write(
            tmp_path,
            "inv_a.csv",
            "invoice_number,vendor_id,invoice_date,po_id,line_no,item,quantity,unit_price,currency,tax_pct,line_total,status\n"
            "INV-A1,V010,2026-11-05,PO-A1,1,Router,10,100.0,INR,0,1000.0,unpaid\n",
        )
        grn_a = _write(
            tmp_path,
            "grn_a.csv",
            "grn_id,po_id,po_line,vendor_id,item,received_qty,accepted_qty,received_date\n"
            "GRN-A1,PO-A1,1,V010,Router,10,4,2026-11-01\n",
        )
        # Workspace B: invoice bills 10, GRN accepted 10 -> 0 R7 findings in ws_b
        # Also test that ws_a's GRN does not leak into ws_b even if same po_id is not shared
        inv_b = _write(
            tmp_path,
            "inv_b.csv",
            "invoice_number,vendor_id,invoice_date,po_id,line_no,item,quantity,unit_price,currency,tax_pct,line_total,status\n"
            "INV-B1,V010,2026-11-05,PO-B1,1,Router,10,100.0,INR,0,1000.0,unpaid\n",
        )
        grn_b = _write(
            tmp_path,
            "grn_b.csv",
            "grn_id,po_id,po_line,vendor_id,item,received_qty,accepted_qty,received_date\n"
            "GRN-B1,PO-B1,1,V010,Router,10,10,2026-11-01\n",
        )

        ingest_csv_file_to_table(conn, inv_a, "invoices", workspace_id="ws_a")
        ingest_csv_file_to_table(conn, grn_a, "goods_receipts", workspace_id="ws_a")
        ingest_csv_file_to_table(conn, inv_b, "invoices", workspace_id="ws_b")
        ingest_csv_file_to_table(conn, grn_b, "goods_receipts", workspace_id="ws_b")

        run_detection(conn, workspace_id="ws_a")
        run_detection(conn, workspace_id="ws_b")

        r7_a = conn.execute(
            "SELECT * FROM findings WHERE rule_id = 'R7' AND workspace_id = 'ws_a'"
        ).fetchall()
        r7_b = conn.execute(
            "SELECT * FROM findings WHERE rule_id = 'R7' AND workspace_id = 'ws_b'"
        ).fetchall()

        assert len(r7_a) == 1
        assert r7_b == []
    finally:
        conn.close()

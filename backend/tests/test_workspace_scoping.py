"""Tests for multi-tenant workspace_id SQL scoping, migration, and X-User-Role RBAC."""
from __future__ import annotations

import sqlite3

from fastapi.testclient import TestClient
import pytest

from app import config
from app.db import init_schema
from app.main import app


@pytest.fixture
def client(monkeypatch, tmp_path):
    monkeypatch.setattr(config, "DB_PATH", str(tmp_path / "ws_scoping.db"))
    monkeypatch.setattr(config, "UPLOAD_DIR", str(tmp_path / "uploads"))
    return TestClient(app)


def test_workspace_data_isolation_ws_a_vs_ws_b(client):
    # Upload duplicate invoices to ws-a via query param
    inv_a = (
        "invoice_number,vendor_id,invoice_date,po_id,line_no,item,quantity,unit_price,currency,tax_pct,line_total,source_file,status\n"
        "INV-A1,V-A,2026-01-10,PO-A1,1,Cloud Hosting,1,5000,INR,0,5000,inv_a1.csv,unpaid\n"
        "INV-A2,V-A,2026-01-10,PO-A1,1,Cloud Hosting,1,5000,INR,0,5000,inv_a2.csv,unpaid\n"
    )
    resp_up_a = client.post(
        "/api/ingest/upload?workspace_id=ws-a",
        data={"kind": "invoices"},
        files={"file": ("inv_a.csv", inv_a.encode("utf-8"), "text/csv")},
    )
    assert resp_up_a.status_code == 200
    assert resp_up_a.json()["workspace_id"] == "ws-a"

    # Upload a single clean invoice to ws-b via X-Workspace-Id header
    inv_b = (
        "invoice_number,vendor_id,invoice_date,po_id,line_no,item,quantity,unit_price,currency,tax_pct,line_total,source_file,status\n"
        "INV-B1,V-B,2026-02-01,PO-B1,1,Office Supplies,2,1000,INR,0,2000,inv_b1.csv,unpaid\n"
    )
    resp_up_b = client.post(
        "/api/ingest/upload",
        headers={"X-Workspace-Id": "ws-b"},
        data={"kind": "invoices"},
        files={"file": ("inv_b.csv", inv_b.encode("utf-8"), "text/csv")},
    )
    assert resp_up_b.status_code == 200
    assert resp_up_b.json()["workspace_id"] == "ws-b"

    # Run detection in ws-a and ws-b
    det_a = client.post("/api/run-detection?workspace_id=ws-a")
    assert det_a.status_code == 200
    assert det_a.json()["findings_created"] >= 1

    det_b = client.post("/api/run-detection", headers={"X-Workspace-Id": "ws-b"})
    assert det_b.status_code == 200
    assert det_b.json()["findings_created"] == 0

    # Verify stats isolation
    stats_a = client.get("/api/stats?workspace_id=ws-a").json()
    stats_b = client.get("/api/stats", headers={"X-Workspace-Id": "ws-b"}).json()
    assert stats_a["total_findings"] >= 1
    assert stats_a["total_audited_spend"] == pytest.approx(10000.0)
    assert stats_b["total_findings"] == 0
    assert stats_b["total_audited_spend"] == pytest.approx(2000.0)

    # Verify batches, findings, memo, audit-log, analytics, and CSV export isolation
    assert len(client.get("/api/batches?workspace_id=ws-a").json()) == 1
    assert len(client.get("/api/batches", headers={"X-Workspace-Id": "ws-b"}).json()) == 1
    assert len(client.get("/api/findings?workspace_id=ws-a").json()) >= 1
    assert client.get("/api/findings", headers={"X-Workspace-Id": "ws-b"}).json() == []

    memo_a = client.get("/api/memo?workspace_id=ws-a").json()
    memo_b = client.get("/api/memo", headers={"X-Workspace-Id": "ws-b"}).json()
    assert memo_a["summary"]["total_findings"] >= 1
    assert memo_b["summary"]["total_findings"] == 0

    audit_a = client.get("/api/audit-log?workspace_id=ws-a").json()
    audit_b = client.get("/api/audit-log", headers={"X-Workspace-Id": "ws-b"}).json()
    assert all(e["workspace_id"] == "ws-a" for e in audit_a)
    assert all(e["workspace_id"] == "ws-b" for e in audit_b)

    exec_a = client.get("/api/analytics/executive?workspace_id=ws-a").json()
    exec_b = client.get("/api/analytics/executive", headers={"X-Workspace-Id": "ws-b"}).json()
    assert exec_a["total_findings"] >= 1
    assert exec_b["total_findings"] == 0

    csv_a = client.get("/api/export/findings.csv?workspace_id=ws-a").text
    csv_b = client.get("/api/export/findings.csv", headers={"X-Workspace-Id": "ws-b"}).text
    assert len(csv_a.strip().splitlines()) >= 2
    assert len(csv_b.strip().splitlines()) == 1  # header only


def test_default_workspace_backward_compatibility_and_migration(client, tmp_path):
    # Legacy DB without workspace_id columns migrates cleanly via init_schema
    legacy_db = tmp_path / "legacy.db"
    conn = sqlite3.connect(str(legacy_db))
    conn.row_factory = sqlite3.Row
    conn.executescript(
        """
        CREATE TABLE batches (batch_id TEXT PRIMARY KEY, kind TEXT NOT NULL, stored_path TEXT, rows_detected INTEGER DEFAULT 0, state TEXT NOT NULL DEFAULT 'uploaded', created_at TEXT);
        CREATE TABLE invoices (invoice_number TEXT NOT NULL, vendor_id TEXT NOT NULL, invoice_date TEXT, po_id TEXT, line_no INTEGER NOT NULL DEFAULT 1, item TEXT NOT NULL, quantity REAL NOT NULL, unit_price REAL NOT NULL, currency TEXT NOT NULL, tax_pct REAL NOT NULL DEFAULT 0, line_total REAL NOT NULL, source_file TEXT, status TEXT NOT NULL DEFAULT 'unpaid', PRIMARY KEY (invoice_number, line_no));
        CREATE TABLE contracts (contract_id TEXT NOT NULL, vendor_id TEXT NOT NULL, item TEXT NOT NULL, contracted_unit_price REAL NOT NULL, currency TEXT NOT NULL, discount_pct REAL NOT NULL DEFAULT 0, payment_terms TEXT, tax_pct REAL NOT NULL DEFAULT 0, start_date TEXT, end_date TEXT, status TEXT NOT NULL DEFAULT 'active', PRIMARY KEY (contract_id, item));
        CREATE TABLE purchase_orders (po_id TEXT NOT NULL, po_line INTEGER NOT NULL DEFAULT 1, vendor_id TEXT NOT NULL, item TEXT NOT NULL, quantity REAL NOT NULL, unit_price REAL NOT NULL, currency TEXT NOT NULL, order_date TEXT, expected_delivery TEXT, status TEXT NOT NULL DEFAULT 'open', PRIMARY KEY (po_id, po_line));
        CREATE TABLE payments (payment_id TEXT PRIMARY KEY, invoice_number TEXT NOT NULL, amount REAL NOT NULL, currency TEXT NOT NULL, fx_rate_to_inr REAL NOT NULL DEFAULT 1.0, payment_date TEXT, status TEXT NOT NULL DEFAULT 'settled');
        CREATE TABLE findings (finding_id TEXT PRIMARY KEY, rule_id TEXT NOT NULL, title TEXT NOT NULL, severity TEXT NOT NULL, amount_at_risk REAL NOT NULL DEFAULT 0, currency TEXT NOT NULL DEFAULT 'INR', status TEXT NOT NULL DEFAULT 'open', entity_refs TEXT NOT NULL DEFAULT '{}', evidence TEXT NOT NULL DEFAULT '[]', confidence REAL NOT NULL DEFAULT 0, summary TEXT DEFAULT '', explanation TEXT, created_at TEXT);
        CREATE TABLE audit_log (id INTEGER PRIMARY KEY AUTOINCREMENT, ts TEXT, actor TEXT NOT NULL, action TEXT NOT NULL, object_type TEXT NOT NULL, object_id TEXT NOT NULL, detail TEXT DEFAULT '');
        """
    )
    init_schema(conn)
    init_schema(conn)  # idempotent
    for tbl in ("batches", "invoices", "contracts", "purchase_orders", "payments", "findings", "audit_log"):
        cols = {r["name"] for r in conn.execute(f"PRAGMA table_info({tbl})").fetchall()}
        assert "workspace_id" in cols
    conn.close()

    # Default workspace seed without workspace_id param/header preserves sample_data gate
    seed_resp = client.post("/api/seed/sample_data")
    assert seed_resp.status_code == 200
    seed_data = seed_resp.json()
    assert seed_data["findings_created"] == 6
    assert seed_data["total_at_risk"] == pytest.approx(40531.60, 0.01)


def test_rbac_x_user_role_enforcement(client):
    # Omitted X-User-Role keeps open demo behavior
    assert client.post("/api/seed/sample_data").status_code == 200
    findings = client.get("/api/findings").json()
    fid = findings[0]["finding_id"]

    # Unknown role -> 403
    resp_unknown = client.get("/api/stats", headers={"X-User-Role": "guest"})
    assert resp_unknown.status_code == 403

    # Analyst can read and run detection, but cannot decide, export, verify_audit, or manage_workspaces
    assert client.get("/api/stats", headers={"X-User-Role": "analyst"}).status_code == 200
    assert client.post("/api/run-detection", headers={"X-User-Role": "analyst"}).status_code == 200
    assert (
        client.post(
            f"/api/findings/{fid}/decision",
            headers={"X-User-Role": "analyst"},
            json={"action": "approve", "reviewer": "a1", "note": "test"},
        ).status_code
        == 403
    )
    assert client.get("/api/export/findings.csv", headers={"X-User-Role": "analyst"}).status_code == 403
    assert client.post("/api/workspaces", headers={"X-User-Role": "analyst"}, json={"name": "New"}).status_code == 403

    # Controller can decide and export, but cannot verify_audit or run_detection
    assert (
        client.post(
            f"/api/findings/{fid}/decision",
            headers={"X-User-Role": "controller"},
            json={"action": "approve", "reviewer": "c1", "note": "ok"},
        ).status_code
        == 200
    )
    assert client.get("/api/export/findings.csv", headers={"X-User-Role": "controller"}).status_code == 200
    assert client.get("/api/audit-log/verify", headers={"X-User-Role": "controller"}).status_code == 403

    # Auditor can verify_audit and export
    assert client.get("/api/audit-log/verify", headers={"X-User-Role": "auditor"}).status_code == 200
    assert client.get("/api/export/findings.csv", headers={"X-User-Role": "auditor"}).status_code == 200

    # Admin can manage_workspaces
    assert (
        client.post(
            "/api/workspaces",
            headers={"X-User-Role": "admin"},
            json={"name": "Acme Corp", "client_code": "ACME"},
        ).status_code
        == 200
    )

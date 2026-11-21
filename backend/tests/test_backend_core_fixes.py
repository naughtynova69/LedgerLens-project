"""Tests for backend-core fixes:
1. LadybugDB Windows/missing-native-lib graceful degradation.
2. Full automation pipeline on POST /api/ingest/upload (auto_run=True) & POST /api/jobs/payrun-sweep.
3. Account & cross-page memory (account_memory table + GET/PUT /api/account/memory).
4. Forwarding optional context fields on POST /api/copilot/ask.
"""
from __future__ import annotations

from io import BytesIO

import pytest
from fastapi.testclient import TestClient

from app import config
from app.graph import GraphClient, fetch_entity_neighborhood, fetch_graph_stats
from app.main import app


@pytest.fixture()
def isolated_client(monkeypatch, tmp_path):
    monkeypatch.setattr(config, "DB_PATH", str(tmp_path / "core_fixes.db"))
    monkeypatch.setattr(config, "UPLOAD_DIR", str(tmp_path / "uploads"))
    monkeypatch.setattr(config, "GEMINI_API_KEY", "")
    monkeypatch.setenv("AUTO_SEED_DEMO", "false")
    with TestClient(app) as client:
        yield client


def test_graph_degrades_gracefully_without_crashing(isolated_client):
    client = isolated_client

    # Direct GraphClient / query layer
    gc = GraphClient(path=":memory:")
    health = gc.health_check()
    assert health["engine"] == "ladybug"
    assert isinstance(health["ok"], bool)

    stats = fetch_graph_stats(gc)
    assert "total_nodes" in stats
    assert "total_relationships" in stats

    nb = fetch_entity_neighborhood(gc, "Vendor", "V-1", hops=2)
    assert nb["entity_type"] == "Vendor"
    assert nb["entity_id"] == "V-1"

    # API routes
    assert client.post("/api/seed/sample_data").status_code == 200
    assert client.post("/api/run-detection").status_code == 200
    g_stats = client.get("/api/graph/stats")
    assert g_stats.status_code == 200
    assert "total_nodes" in g_stats.json()
    g_rebuild = client.post("/api/graph/rebuild")
    assert g_rebuild.status_code == 200
    g_ent = client.get("/api/graph/entity/Vendor/V007")
    assert g_ent.status_code == 200


def test_upload_auto_run_chains_full_pipeline_and_can_be_disabled(isolated_client):
    client = isolated_client
    csv_bytes = (
        b"invoice_number,vendor_id,invoice_date,po_id,line_no,item,quantity,unit_price,currency,tax_pct,line_total,status\n"
        b"INV-AUTO-1,V-AUTO,2026-11-19,,1,Cloud Hosting,1,5000.00,INR,0,5000.00,unpaid\n"
    )

    # Default auto_run=True
    res_auto = client.post(
        "/api/ingest/upload",
        data={"kind": "invoices"},
        files={"file": ("auto.csv", BytesIO(csv_bytes), "text/csv")},
    )
    assert res_auto.status_code == 200
    body = res_auto.json()
    assert body["auto_run"] is True
    assert body["pipeline"]["status"] == "completed"
    assert body["pipeline"]["stages"] == ["extract", "normalize", "detect", "graph_rebuild", "explain"]
    assert body["pipeline"]["extract"]["rows_extracted"] == 1
    assert "findings_created" in body["pipeline"]["detect"]
    assert "total_nodes" in body["pipeline"]["graph_rebuild"]
    assert "findings_explained" in body["pipeline"]["explain"]

    # Explicit auto_run=False
    res_skip = client.post(
        "/api/ingest/upload",
        data={"kind": "invoices", "auto_run": "false"},
        files={"file": ("manual.csv", BytesIO(csv_bytes), "text/csv")},
    )
    assert res_skip.status_code == 200
    skip_body = res_skip.json()
    assert skip_body["auto_run"] is False
    assert skip_body["pipeline"]["status"] == "skipped"


def test_payrun_sweep_detects_applies_policy_generates_memo_and_logs_audit(isolated_client):
    client = isolated_client

    # Lower auto_hold_threshold_inr to 1000 so sample anomalies trigger auto_hold
    pol_res = client.put("/api/policy", json={"auto_hold_threshold_inr": 1000.0})
    assert pol_res.status_code == 200

    # Upload a duplicate-invoice CSV with auto_run=False so it stays pending
    csv_bytes = (
        b"invoice_number,vendor_id,invoice_date,po_id,line_no,item,quantity,unit_price,currency,tax_pct,line_total,status\n"
        b"INV-SWP-1,V-SWP,2026-11-10,,1,Server Rack,1,25000.00,INR,0,25000.00,unpaid\n"
        b"INV-SWP-2,V-SWP,2026-11-12,,1,Server Rack,1,25000.00,INR,0,25000.00,unpaid\n"
    )
    up = client.post(
        "/api/ingest/upload?auto_run=false",
        data={"kind": "invoices"},
        files={"file": ("sweep.csv", BytesIO(csv_bytes), "text/csv")},
    )
    assert up.status_code == 200
    batch_id = up.json()["batch_id"]

    sweep = client.post("/api/jobs/payrun-sweep")
    assert sweep.status_code == 200
    data = sweep.json()
    assert batch_id in data["batches_swept"]
    assert data["findings_created"] >= 1
    assert data["auto_held_count"] >= 1
    assert "memo" in data and "summary" in data["memo"] and "memo_markdown" in data["memo"]

    # Verify audit_log + hash chain integrity
    logs = client.get("/api/audit-log").json()
    assert any(entry["action"] == "payrun_sweep" for entry in logs)
    verify = client.get("/api/audit-log/verify")
    assert verify.status_code == 200
    assert verify.json()["valid"] is True


def test_account_memory_persistence_partial_updates_and_workspace_isolation(isolated_client):
    client = isolated_client

    # Initial GET returns defaults
    r0 = client.get("/api/account/memory?account_id=acct-1&workspace_id=ws-a")
    assert r0.status_code == 200
    d0 = r0.json()
    assert d0["account_id"] == "acct-1"
    assert d0["workspace_id"] == "ws-a"
    assert d0["filters"] == {}
    assert d0["recent_actions"] == []

    # PUT full state
    r1 = client.put(
        "/api/account/memory",
        json={
            "account_id": "acct-1",
            "workspace_id": "ws-a",
            "user_name": "Priya CFO",
            "user_role": "controller",
            "active_page": "findings",
            "active_tab": "high_risk",
            "filters": {"severity": "high", "status": "open"},
            "recent_actions": [{"action": "view_finding", "id": "F-0001"}],
            "copilot_context": {"last_topic": "duplicate_invoices"},
        },
    )
    assert r1.status_code == 200
    d1 = r1.json()
    assert d1["user_name"] == "Priya CFO"
    assert d1["active_page"] == "findings"
    assert d1["filters"] == {"severity": "high", "status": "open"}

    # Partial PUT preserves existing fields
    r2 = client.put(
        "/api/account/memory",
        json={
            "account_id": "acct-1",
            "workspace_id": "ws-a",
            "active_page": "graph",
        },
    )
    assert r2.status_code == 200
    d2 = r2.json()
    assert d2["active_page"] == "graph"
    assert d2["user_name"] == "Priya CFO"
    assert d2["filters"] == {"severity": "high", "status": "open"}

    # Different workspace is isolated
    r_other = client.get("/api/account/memory?account_id=acct-1&workspace_id=ws-b")
    assert r_other.status_code == 200
    assert r_other.json()["user_name"] == ""
    assert r_other.json()["active_page"] == ""


def test_copilot_ask_forwards_optional_context(isolated_client):
    client = isolated_client
    res = client.post(
        "/api/copilot/ask",
        json={
            "question": "Summarize open exposure",
            "workspace_id": "default",
            "current_page": "findings",
            "selected_finding_id": "F-0001",
            "conversation_history": [{"role": "user", "content": "hi"}],
        },
    )
    assert res.status_code == 200
    assert "answer" in res.json()

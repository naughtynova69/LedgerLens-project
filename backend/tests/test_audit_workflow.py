"""Tests for CFO explanation layer, Google Agent Skills, audit log, and CFO memo."""
from __future__ import annotations

from io import BytesIO
from pathlib import Path
from fastapi.testclient import TestClient

from app import config
from app.explain import fallback_without_gemini
from app.main import app
from app.skills import GEMINI_TOOL_DECLARATIONS


def test_cfo_fallback_grounded_in_proof_trail():
    finding = {
        "finding_id": "F-0001",
        "rule_id": "R1",
        "title": "Possible duplicate payment",
        "severity": "critical",
        "amount_at_risk": 4956.0,
        "currency": "INR",
        "confidence": 0.93,
        "recommended_action": "REQUEST_CREDIT_NOTE",
        "summary": "Same vendor (V001), same amount (4,956.00 INR), 2-day gap.",
        "proof_trail": {
            "rule_id": "R1",
            "recommended_action": "REQUEST_CREDIT_NOTE",
            "evidence": [
                {"source": "invoices", "record_id": "INV-8821", "field": "line_total", "value": "4956.00 INR"},
                {"source": "invoices", "record_id": "INV-8821-R2", "field": "line_total", "value": "4956.00 INR"},
            ],
        },
    }
    card = fallback_without_gemini(finding)
    assert card["decision_engine"] == "Deterministic Rule R1"
    assert card["model_used"] == config.GEMINI_PRIMARY_MODEL
    assert card["generated_without_gemini"] is True
    assert "REQUEST_CREDIT_NOTE" in card["recommended_action"]
    assert "INV-8821" in card["explanation"]


def test_agent_skills_and_full_audit_lifecycle(monkeypatch, tmp_path):
    monkeypatch.setattr(config, "DB_PATH", str(tmp_path / "audit_workflow.db"))
    monkeypatch.setattr(config, "UPLOAD_DIR", str(tmp_path / "uploads"))
    monkeypatch.setattr(config, "GEMINI_API_KEY", "")

    client = TestClient(app)

    # 1. Seed demo data -> logs ingest + detect
    seed_res = client.post("/api/seed/sample_data")
    assert seed_res.status_code == 200
    assert seed_res.json()["findings_created"] == 6

    # 2. Verify skills declaration catalog
    skills_res = client.get("/api/skills")
    assert skills_res.status_code == 200
    names = {t["name"] for t in skills_res.json()["tools"]}
    assert names == {"fetch_payment_records", "generate_audit_memo", "route_recovery_task",
                     "inspect_entity_graph"}
    assert len(GEMINI_TOOL_DECLARATIONS) == 4

    # 3. Execute fetch_payment_records skill
    pay_res = client.post("/api/skills/fetch_payment_records", json={"invoice_number": "INV-8821"})
    assert pay_res.status_code == 200
    assert pay_res.json()["count"] == 1
    assert pay_res.json()["records"][0]["payment_id"] == "PAY-5001"

    # 4. Execute route_recovery_task skill on F-0001
    route_res = client.post(
        "/api/skills/route_recovery_task",
        json={"finding_id": "F-0001", "assignee": "Vijay (AP Lead)", "note": "Duplicate paid twice"},
    )
    assert route_res.status_code == 200
    assert route_res.json()["status"] == "recovery"

    # 5. Execute generate_audit_memo skill + GET /api/memo
    memo_skill = client.post("/api/skills/generate_audit_memo", json={})
    assert memo_skill.status_code == 200
    assert memo_skill.json()["summary"]["total_findings"] == 6
    assert memo_skill.json()["summary"]["recovered_amount"] > 0

    memo_http = client.get("/api/memo")
    assert memo_http.status_code == 200
    assert "# LedgerLens Audit Memo" in memo_http.json()["memo_markdown"]
    assert "by_rule" in memo_http.json()

    # 6. Upload + extract -> verify ingest, extract, detect, recovery all appear in immutable audit_log
    pdf_bytes = b"%PDF-1.4\nVendor: Test\nInvoice Number: INV-AUD-1\nCurrency: INR\nItem: Box\nQuantity: 1\nUnit Price: 100\nTax %: 0\nLine Total: 100\n"
    up = client.post(
        "/api/ingest/upload",
        data={"kind": "invoices"},
        files={"file": ("aud1.pdf", BytesIO(pdf_bytes), "application/pdf")},
    )
    assert up.status_code == 200
    batch_id = up.json()["batch_id"]
    ext = client.post(f"/api/run/{batch_id}/extract")
    assert ext.status_code == 200

    logs = client.get("/api/audit-log").json()
    actions = {row["action"] for row in logs}
    assert {"ingest", "extract", "detect", "recovery"}.issubset(actions)

"""API route handler tests."""
from __future__ import annotations

import pytest

from app import config
from app.main import (
    audit_log,
    decide,
    get_batch,
    get_finding,
    health,
    list_batches,
    list_findings,
    memo,
    seed_demo_data,
    stats,
)
from app.models import DecisionIn


def test_api_workflow_end_to_end(monkeypatch, tmp_path):
    monkeypatch.setattr(config, "DB_PATH", str(tmp_path / "api_e2e.db"))
    monkeypatch.setattr(config, "UPLOAD_DIR", str(tmp_path / "uploads"))

    # 1. Health check
    h = health()
    assert h["status"] == "ok"

    # 2. Seed sample data
    seed = seed_demo_data()
    assert seed["findings_created"] == 6
    assert seed["total_at_risk"] == pytest.approx(40531.60, 0.01)

    # 3. Stats endpoint
    st = stats()
    assert st["total_findings"] == 6
    assert st["by_severity"]["critical"] == 2
    assert st["by_severity"]["high"] == 4

    # 4. Batches endpoint
    batches = list_batches()
    assert len(batches) >= 1
    assert get_batch(batches[0]["batch_id"]) is not None

    # 5. List findings
    findings = list_findings()
    assert len(findings) == 6
    first_id = findings[0]["finding_id"]
    assert "proof_trail" in findings[0]

    # 6. Get finding detail with joined source records
    detail = get_finding(first_id)
    assert detail["finding_id"] == first_id
    assert "source_records" in detail
    assert "evidence" in detail
    assert "explanation" in detail
    assert detail["explanation"] is not None

    # 7. Record a decision
    decision_payload = DecisionIn(action="reject", reviewer="chief_auditor", note="Duplicate verified; blocked.")
    dec_res = decide(first_id, decision_payload)
    assert dec_res["status"] == "rejected"

    # 8. Verify audit log entry
    logs = audit_log()
    assert len(logs) >= 1
    assert any(log["actor"] == "chief_auditor" and log["object_id"] == first_id for log in logs)

    # 9. Verify audit memo (Markdown + JSON)
    m = memo()
    assert "# LedgerLens Audit Memo" in m["memo_markdown"]
    assert "40,531.60" in m["memo_markdown"]
    assert m["summary"]["total_findings"] == 6

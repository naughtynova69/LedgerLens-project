"""Tests for CFO/AP finance features: dispute packets, CSV exports, bulk decisions, FX normalization, and policy governance."""
from __future__ import annotations

import csv
import io
import json

from fastapi.testclient import TestClient
import pytest

from app import config
from app.main import app  # Must precede app.finance.exports import (populates sys.modules["app.finance"])
from app.finance.exports import compute_fx_normalized_totals


@pytest.fixture()
def seeded_client(monkeypatch, tmp_path):
    """Return a TestClient wired to an isolated temp DB pre-seeded with demo data."""
    monkeypatch.setattr(config, "DB_PATH", str(tmp_path / "finance_features.db"))
    monkeypatch.setattr(config, "UPLOAD_DIR", str(tmp_path / "uploads"))
    monkeypatch.setattr(config, "GEMINI_API_KEY", "")

    with TestClient(app) as client:
        seed_res = client.post("/api/seed/sample_data")
        assert seed_res.status_code == 200
        assert seed_res.json()["findings_created"] == 6
        yield client


def test_dispute_packet_endpoint(seeded_client: TestClient) -> None:
    """GET /api/findings/{id}/dispute-packet returns vendor-ready subject, verbatim IDs, amount_claimed, and currency."""
    findings = seeded_client.get("/api/findings").json()
    assert len(findings) == 6

    saw_invoice = False
    saw_contract = False
    saw_po = False

    for finding in findings:
        fid = finding["finding_id"]
        res = seeded_client.get(f"/api/findings/{fid}/dispute-packet")
        assert res.status_code == 200

        packet = res.json()
        assert packet["finding_id"] == fid
        assert packet["rule_id"] == finding["rule_id"]
        assert packet["to_vendor"]
        assert packet["subject"]
        assert fid in packet["subject"]
        assert packet["amount_claimed"] == pytest.approx(finding["amount_at_risk"])
        assert packet["currency"] == finding["currency"]

        body = packet["body_text"]
        assert fid in body
        assert finding["rule_id"] in body

        refs = packet["reference_ids"]
        entity_refs = finding.get("entity_refs") or {}

        invoice_numbers = refs.get("invoice_numbers") or entity_refs.get("invoice_numbers") or []
        if invoice_numbers:
            saw_invoice = True
            for inv_num in invoice_numbers:
                assert inv_num in body
                assert inv_num in packet["subject"]

        contract_id = refs.get("contract_id") or entity_refs.get("contract_id")
        if contract_id:
            saw_contract = True
            assert contract_id in body

        po_id = refs.get("po_id") or entity_refs.get("po_id")
        if po_id:
            saw_po = True
            assert po_id in body

    assert saw_invoice
    assert saw_contract
    assert saw_po

    missing_res = seeded_client.get("/api/findings/F-9999/dispute-packet")
    assert missing_res.status_code == 404


def test_export_findings_csv_endpoint(seeded_client: TestClient) -> None:
    """GET /api/export/findings.csv returns 200, text/csv, header + 6 rows, valid for csv.DictReader."""
    res = seeded_client.get("/api/export/findings.csv")
    assert res.status_code == 200
    assert res.headers["content-type"].startswith("text/csv")
    assert "ledgerlens-exceptions.csv" in res.headers.get("content-disposition", "")

    expected_columns = [
        "finding_id",
        "rule_id",
        "severity",
        "status",
        "vendor_id",
        "invoice_numbers",
        "po_id",
        "contract_id",
        "amount_at_risk",
        "currency",
        "inr_equivalent",
        "recommended_action",
        "title",
        "summary",
    ]

    raw_rows = list(csv.reader(io.StringIO(res.text)))
    assert len(raw_rows) == 7  # header + 6 findings
    assert raw_rows[0] == expected_columns

    dict_rows = list(csv.DictReader(io.StringIO(res.text)))
    assert len(dict_rows) == 6
    for row in dict_rows:
        assert row["finding_id"]
        assert row["rule_id"]
        assert float(row["amount_at_risk"]) > 0
        assert float(row["inr_equivalent"]) >= float(row["amount_at_risk"])

    amounts = [float(row["amount_at_risk"]) for row in dict_rows]
    assert amounts == sorted(amounts, reverse=True)

    filtered_res = seeded_client.get("/api/export/findings.csv?rule_id=R1")
    assert filtered_res.status_code == 200
    filtered_rows = list(csv.DictReader(io.StringIO(filtered_res.text)))
    assert len(filtered_rows) == 1
    assert filtered_rows[0]["rule_id"] == "R1"


def test_bulk_decision_endpoint(seeded_client: TestClient) -> None:
    """POST /api/findings/bulk-decision atomically updates findings to recovery and logs audit_log rows."""
    all_findings = seeded_client.get("/api/findings").json()
    target_ids = [f["finding_id"] for f in all_findings[:3]]
    untouched_ids = [f["finding_id"] for f in all_findings[3:]]

    res = seeded_client.post(
        "/api/findings/bulk-decision",
        json={
            "finding_ids": target_ids,
            "action": "recovery",
            "reviewer": "cfo_alice",
            "note": "Bulk recovery batch",
        },
    )
    assert res.status_code == 200
    payload = res.json()
    assert payload["updated_count"] == 3
    assert set(payload["updated_ids"]) == set(target_ids)
    assert payload["status"] == "recovery"
    assert payload["errors"] == []

    recovery_rows = seeded_client.get("/api/findings?status=recovery").json()
    assert {r["finding_id"] for r in recovery_rows} == set(target_ids)

    open_rows = seeded_client.get("/api/findings?status=open").json()
    assert {r["finding_id"] for r in open_rows} == set(untouched_ids)

    logs = seeded_client.get("/api/audit-log").json()
    recovery_logs = [
        row
        for row in logs
        if row["action"] == "recovery"
        and row["object_type"] == "finding"
        and row["actor"] == "cfo_alice"
    ]
    assert {row["object_id"] for row in recovery_logs} == set(target_ids)
    assert all(row["detail"] == "Bulk recovery batch" for row in recovery_logs)

    empty_res = seeded_client.post(
        "/api/findings/bulk-decision",
        json={"finding_ids": [], "action": "recovery", "reviewer": "cfo_alice"},
    )
    assert empty_res.status_code == 400

    bad_action_res = seeded_client.post(
        "/api/findings/bulk-decision",
        json={"finding_ids": target_ids, "action": "unknown_action", "reviewer": "cfo_alice"},
    )
    assert bad_action_res.status_code == 400


def test_compute_fx_normalized_totals() -> None:
    """compute_fx_normalized_totals converts USD * 88.0 and EUR * 95.0 alongside INR."""
    invoices = [
        {"invoice_number": "INV-USD", "line_total": 100.0, "currency": "USD"},
        {"invoice_number": "INV-EUR", "line_total": 200.0, "currency": "EUR"},
        {"invoice_number": "INV-INR", "line_total": 5000.0, "currency": "INR"},
    ]
    findings = [
        {"finding_id": "F-1", "amount_at_risk": 10.0, "currency": "USD", "status": "open"},
        {"finding_id": "F-2", "amount_at_risk": 5.0, "currency": "usd", "status": "open"},
        {"finding_id": "F-3", "amount_at_risk": 20.0, "currency": "EUR", "status": "recovery"},
        {"finding_id": "F-4", "amount_at_risk": 500.0, "currency": "INR", "status": "rejected"},
    ]

    totals = compute_fx_normalized_totals(findings, invoices)

    # Invoices: 100*88 + 200*95 + 5000*1 = 8800 + 19000 + 5000 = 32800.0
    assert totals["total_audited_inr"] == pytest.approx(32800.0)
    # Findings: 15*88 + 20*95 + 500*1 = 1320 + 1900 + 500 = 3720.0
    assert totals["total_at_risk_inr"] == pytest.approx(3720.0)
    assert totals["open_at_risk_inr"] == pytest.approx(1320.0)
    assert totals["recovered_inr"] == pytest.approx(2400.0)
    assert totals["leakage_pct_of_spend"] == pytest.approx(round((3720.0 / 32800.0) * 100.0, 2))

    assert totals["by_currency"] == {
        "USD": {"count": 2, "native_amount": 15.0, "inr_equivalent": 1320.0},
        "EUR": {"count": 1, "native_amount": 20.0, "inr_equivalent": 1900.0},
        "INR": {"count": 1, "native_amount": 500.0, "inr_equivalent": 500.0},
    }

    zero_spend = compute_fx_normalized_totals(findings, [])
    assert zero_spend["total_audited_inr"] == 0.0
    assert zero_spend["leakage_pct_of_spend"] == 0.0


def test_policy_get_put_validation_and_audit_log(seeded_client: TestClient) -> None:
    """GET/PUT /api/policy updates thresholds, rejects negatives with 400, and logs policy_update."""
    initial_res = seeded_client.get("/api/policy")
    assert initial_res.status_code == 200
    assert initial_res.json() == {
        "r1_max_amount_drift_pct": 0.5,
        "r1_max_date_gap_days": 30,
        "r4_max_fx_drift_pct": 2.0,
        "auto_hold_threshold_inr": 10000.0,
    }

    updated_policy = {
        "r1_max_amount_drift_pct": 1.25,
        "r1_max_date_gap_days": 45,
        "r4_max_fx_drift_pct": 3.5,
        "auto_hold_threshold_inr": 25000.0,
    }
    put_res = seeded_client.put("/api/policy", json=updated_policy)
    assert put_res.status_code == 200
    assert put_res.json() == updated_policy

    persisted_res = seeded_client.get("/api/policy")
    assert persisted_res.status_code == 200
    assert persisted_res.json() == updated_policy

    logs = seeded_client.get("/api/audit-log").json()
    policy_logs = [
        row
        for row in logs
        if row["action"] == "policy_update"
        and row["object_type"] == "policy"
        and row["object_id"] == "global"
    ]
    assert len(policy_logs) == 1
    assert json.loads(policy_logs[0]["detail"]) == updated_policy

    for invalid_payload in [
        {"r1_max_amount_drift_pct": -0.1},
        {"r1_max_date_gap_days": -5},
        {"r4_max_fx_drift_pct": -1.0},
        {"auto_hold_threshold_inr": -100.0},
    ]:
        bad_res = seeded_client.put("/api/policy", json=invalid_payload)
        assert bad_res.status_code == 400

    assert seeded_client.get("/api/policy").json() == updated_policy

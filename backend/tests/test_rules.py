"""Comprehensive unit & architectural invariant tests for rules R1-R5."""
from __future__ import annotations

import ast
from pathlib import Path

from app.detect import DetectionContext, run_all
from app.detect.types import VALID_RECOMMENDED_ACTIONS


def _inv(**overrides) -> dict:
    base = {
        "invoice_number": "INV-100",
        "vendor_id": "V001",
        "invoice_date": "2026-11-05",
        "po_id": "PO-100",
        "line_no": 1,
        "item": "Server Rack",
        "quantity": 10.0,
        "unit_price": 100.0,
        "currency": "INR",
        "tax_pct": 18.0,
        "line_total": 1180.0,
        "status": "unpaid",
    }
    base.update(overrides)
    return base


def test_detect_package_has_zero_llm_or_network_imports():
    """Neuro-symbolic invariant: detect/ must never import LLM SDKs, DB drivers, or HTTP clients."""
    forbidden = {"google", "genai", "openai", "anthropic", "httpx", "requests", "urllib", "sqlite3"}
    detect_dir = Path(__file__).resolve().parent.parent / "app" / "detect"
    for py_file in detect_dir.rglob("*.py"):
        tree = ast.parse(py_file.read_text(encoding="utf-8"), filename=str(py_file))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    top = alias.name.split(".")[0].lower()
                    assert top not in forbidden, f"Forbidden import {alias.name} in {py_file}"
            elif isinstance(node, ast.ImportFrom) and node.module:
                top = node.module.split(".")[0].lower()
                assert top not in forbidden, f"Forbidden import {node.module} in {py_file}"


def test_r1_fuzzy_and_same_po_duplicates_with_proof_trail():
    lines = [
        _inv(invoice_number="INV-8821", invoice_date="2026-10-14", status="paid"),
        _inv(invoice_number="INV 8821 / R2", invoice_date="2026-10-16", status="paid"),
    ]
    findings = run_all(DetectionContext(invoices=lines))
    r1 = [f for f in findings if f.rule_id == "R1"]
    assert len(r1) == 1
    f = r1[0]
    assert f.recommended_action == "REQUEST_CREDIT_NOTE"
    assert f.proof_trail["rule_id"] == "R1"
    assert f.proof_trail["math"]["both_paid"] is True
    assert f.recommended_action in VALID_RECOMMENDED_ACTIONS


def test_r2_contract_price_leakage_and_discount_guard():
    contracts = [{
        "contract_id": "C-10",
        "vendor_id": "V001",
        "item": "Server Rack",
        "contracted_unit_price": 100.0,
        "currency": "INR",
        "discount_pct": 10.0,
        "tax_pct": 18.0,
        "start_date": "2026-01-01",
        "end_date": "2026-12-31",
        "status": "active",
    }]
    # Overbilled vs discounted rate (90.0) when billed above nominal rate (105.0)
    over = [_inv(unit_price=105.0, line_total=1239.0)]
    r2_over = [f for f in run_all(DetectionContext(invoices=over, contracts=contracts)) if f.rule_id == "R2"]
    assert len(r2_over) == 1
    assert r2_over[0].amount_at_risk == 177.0  # (105 - 90) * 10 * 1.18
    assert r2_over[0].recommended_action == "DISPUTE_VENDOR"

    # Explicit discount_applied_pct=0 missed the 10% contract discount
    missed_disc = [_inv(unit_price=100.0, discount_applied_pct=0.0)]
    r2_disc = [f for f in run_all(DetectionContext(invoices=missed_disc, contracts=contracts)) if f.rule_id == "R2"]
    assert len(r2_disc) == 1
    assert r2_disc[0].amount_at_risk == 118.0

    # Outside validity window -> does not fire
    expired = [_inv(invoice_date="2027-02-01", unit_price=105.0)]
    assert [f for f in run_all(DetectionContext(invoices=expired, contracts=contracts)) if f.rule_id == "R2"] == []


def test_r3_overbilling_premature_and_absent_po_item():
    pos = [{
        "po_id": "PO-100",
        "po_line": 1,
        "vendor_id": "V001",
        "item": "Server Rack",
        "quantity": 10.0,
        "unit_price": 100.0,
        "currency": "INR",
        "expected_delivery": "2026-11-20",
        "status": "open",
    }]
    # Premature + quantity overbilling
    invs = [_inv(invoice_date="2026-11-05", quantity=12.0, line_total=1416.0)]
    r3 = [f for f in run_all(DetectionContext(invoices=invs, purchase_orders=pos)) if f.rule_id == "R3"]
    titles = [f.title for f in r3]
    assert any("overbilling" in t.lower() for t in titles)
    assert any("premature" in t.lower() for t in titles)

    # Delivered PO does not trigger premature billing
    pos_deliv = [dict(pos[0], status="delivered")]
    clean = [_inv(invoice_date="2026-11-05", quantity=10.0)]
    assert [f for f in run_all(DetectionContext(invoices=clean, purchase_orders=pos_deliv)) if f.rule_id == "R3"] == []

    # Item absent from PO
    absent = [_inv(item="Gold Cable", po_id="PO-100", line_total=500.0)]
    r3_absent = [f for f in run_all(DetectionContext(invoices=absent, purchase_orders=pos_deliv)) if f.rule_id == "R3"]
    assert len(r3_absent) == 1
    assert "unordered" in r3_absent[0].title.lower()


def test_r4_currency_fx_anomaly_and_duplicate_tax():
    vendors = [{"vendor_id": "V001", "vendor_name": "Acme", "default_currency": "INR", "status": "active"}]
    # Vendor currency mismatch (without PO) + duplicate tax lines
    invs = [
        _inv(invoice_number="INV-FX", po_id="", line_no=1, currency="USD", unit_price=10.0, tax_pct=18.0, line_total=118.0),
        _inv(invoice_number="INV-FX", po_id="", line_no=2, currency="USD", unit_price=10.0, tax_pct=18.0, line_total=118.0),
    ]
    payments = [{"payment_id": "PAY-9", "invoice_number": "INV-FX", "amount": 200.0, "currency": "USD", "fx_rate_to_inr": 95.0, "status": "settled"}]
    r4 = [f for f in run_all(DetectionContext(invoices=invs, vendors=vendors, payments=payments)) if f.rule_id == "R4"]
    titles = [f.title.lower() for f in r4]
    assert any("currency mismatch" in t for t in titles)
    assert any("duplicate tax" in t for t in titles)
    assert any("fx conversion" in t for t in titles)


def test_r5_cancelled_contract_terminated_vendor_and_cancelled_po():
    vendors = [{"vendor_id": "V-BAD", "vendor_name": "BadCo", "default_currency": "INR", "status": "terminated"}]
    contracts = [{"contract_id": "C-TERM", "vendor_id": "V001", "item": "SaaS", "contracted_unit_price": 100.0, "currency": "INR", "end_date": "2026-10-01", "status": "terminated"}]
    pos = [{"po_id": "PO-CANC", "po_line": 1, "vendor_id": "V001", "item": "Rack", "quantity": 1.0, "unit_price": 100.0, "currency": "INR", "status": "cancelled"}]

    invs = [
        _inv(invoice_number="INV-R5-1", vendor_id="V001", po_id="", item="SaaS", invoice_date="2026-10-15", status="paid"),
        _inv(invoice_number="INV-R5-2", vendor_id="V-BAD", po_id="", item="Consulting", invoice_date="2026-11-01", status="unpaid"),
        _inv(invoice_number="INV-R5-3", vendor_id="V001", po_id="PO-CANC", item="Rack", invoice_date="2026-11-01", status="unpaid"),
    ]
    r5 = [f for f in run_all(DetectionContext(invoices=invs, vendors=vendors, contracts=contracts, purchase_orders=pos)) if f.rule_id == "R5"]
    assert len(r5) == 3
    assert all(f.recommended_action == "CANCEL_AUTOPAY" for f in r5)

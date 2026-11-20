"""Tests for Track #2 (policy-parameterized rules) and Track #5 (R6 split-PO, R7 GRN mismatch)."""
from __future__ import annotations

from app.detect.registry import DetectionContext, run_all_rules
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


def test_r1_policy_amount_drift_and_date_gap_overrides():
    # Distinct invoice numbers (low similarity), 40-day gap, 3% amount drift
    invs = [
        _inv(invoice_number="ALPHA-101", po_id="", invoice_date="2026-09-01", line_total=1000.0),
        _inv(invoice_number="OMEGA-999", po_id="", invoice_date="2026-10-11", line_total=1030.0),
    ]
    ctx = DetectionContext(invoices=invs)

    # Default thresholds (0.5% drift, 30 days) -> should NOT fire
    default_r1 = [f for f in run_all_rules(ctx) if f.rule_id == "R1"]
    assert default_r1 == []

    # Relaxed policy -> SHOULD fire
    relaxed = {"r1_max_amount_drift_pct": 5.0, "r1_max_date_gap_days": 45}
    policy_r1 = [f for f in run_all_rules(ctx, policy=relaxed) if f.rule_id == "R1"]
    assert len(policy_r1) == 1
    assert policy_r1[0].proof_trail["math"]["date_gap_days"] == 40
    # Caller's ctx.policy was not mutated
    assert ctx.policy == {}


def test_r4_policy_fx_rate_and_drift_overrides():
    payments = [
        {
            "payment_id": "PAY-1",
            "invoice_number": "INV-1",
            "amount": 100.0,
            "currency": "USD",
            "fx_rate_to_inr": 91.0,
            "status": "settled",
        }
    ]
    ctx = DetectionContext(payments=payments)

    # Default: 91 vs 88 = 3.41% drift > 2% -> fires
    default_r4 = [f for f in run_all_rules(ctx) if f.rule_id == "R4"]
    assert len(default_r4) == 1

    # With r4_max_fx_drift_pct=4.0 -> within tolerance
    assert [f for f in run_all_rules(ctx, policy={"r4_max_fx_drift_pct": 4.0}) if f.rule_id == "R4"] == []

    # With fx_rates override USD=90.0 -> 91 vs 90 = 1.11% <= 2% -> within tolerance
    assert [f for f in run_all_rules(ctx, policy={"fx_rates": {"USD": 90.0}}) if f.rule_id == "R4"] == []


def test_auto_hold_threshold_escalates_dispute_vendor():
    contracts = [{
        "contract_id": "C-1",
        "vendor_id": "V001",
        "item": "Server Rack",
        "contracted_unit_price": 100.0,
        "currency": "INR",
        "discount_pct": 0.0,
        "tax_pct": 0.0,
        "start_date": "2026-01-01",
        "end_date": "2026-12-31",
        "status": "active",
    }]
    # Overbilled by 10 * (1600 - 100) = 15,000 INR -> normally DISPUTE_VENDOR
    invs = [_inv(unit_price=1600.0, tax_pct=0.0, line_total=16000.0)]
    ctx = DetectionContext(invoices=invs, contracts=contracts)

    r2_default = [f for f in run_all_rules(ctx) if f.rule_id == "R2"]
    assert len(r2_default) == 1
    assert r2_default[0].recommended_action == "DISPUTE_VENDOR"

    r2_hold = [f for f in run_all_rules(ctx, policy={"auto_hold_threshold_inr": 10000.0}) if f.rule_id == "R2"]
    assert len(r2_hold) == 1
    assert r2_hold[0].recommended_action == "HOLD_PAYMENT"
    assert r2_hold[0].proof_trail["recommended_action"] == "HOLD_PAYMENT"
    assert r2_hold[0].proof_trail["math"]["auto_hold_triggered"] is True


def test_r6_split_po_bypass_detection_and_policy_overrides():
    pos = [
        {
            "po_id": "PO-501",
            "po_line": 1,
            "vendor_id": "V010",
            "item": "Workstation",
            "quantity": 1,
            "unit_price": 42000.0,
            "currency": "INR",
            "order_date": "2026-11-01",
            "status": "open",
        },
        {
            "po_id": "PO-502",
            "po_line": 1,
            "vendor_id": "V010",
            "item": "Monitor",
            "quantity": 1,
            "unit_price": 41000.0,
            "currency": "INR",
            "order_date": "2026-11-04",
            "status": "open",
        },
        # Cancelled PO should be ignored
        {
            "po_id": "PO-503",
            "po_line": 1,
            "vendor_id": "V010",
            "item": "Dock",
            "quantity": 1,
            "unit_price": 40000.0,
            "currency": "INR",
            "order_date": "2026-11-05",
            "status": "cancelled",
        },
    ]
    ctx = DetectionContext(purchase_orders=pos)
    r6 = [f for f in run_all_rules(ctx) if f.rule_id == "R6"]
    assert len(r6) == 1
    f = r6[0]
    assert f.recommended_action == "HOLD_PAYMENT"
    assert f.recommended_action in VALID_RECOMMENDED_ACTIONS
    assert f.amount_at_risk == 83000.0
    assert f.entity_refs["po_ids"] == ["PO-501", "PO-502"]
    assert f.proof_trail["math"]["combined_amount_inr"] == 83000.0
    assert f.proof_trail["math"]["window_span_days"] == 3

    # Narrow window (2 days) -> should NOT fire for 3-day gap
    assert [x for x in run_all_rules(ctx, policy={"r6_split_window_days": 2}) if x.rule_id == "R6"] == []

    # Higher limit (100,000 INR) -> 42k < 75% of 100k -> should NOT fire
    assert [x for x in run_all_rules(ctx, policy={"r6_approval_limit_inr": 100000.0}) if x.rule_id == "R6"] == []


def test_r6_split_non_po_invoices():
    invs = [
        _inv(invoice_number="INV-NP-1", po_id="", vendor_id="V020", invoice_date="2026-11-01", line_total=39000.0),
        _inv(invoice_number="INV-NP-2", po_id="", vendor_id="V020", invoice_date="2026-11-06", line_total=40000.0),
    ]
    r6 = [f for f in run_all_rules(DetectionContext(invoices=invs)) if f.rule_id == "R6"]
    assert len(r6) == 1
    assert r6[0].entity_refs["invoice_numbers"] == ["INV-NP-1", "INV-NP-2"]
    assert r6[0].amount_at_risk == 79000.0


def test_r7_grn_mismatch_empty_and_overbilled():
    invs = [
        _inv(invoice_number="INV-G1", po_id="PO-700", item="Server Rack", quantity=6.0, unit_price=1000.0, tax_pct=18.0, line_total=7080.0),
        _inv(invoice_number="INV-G2", po_id="PO-700", item="Server Rack", quantity=4.0, unit_price=1000.0, tax_pct=18.0, line_total=4720.0),
        # Credited invoice should not count toward billed quantity
        _inv(invoice_number="INV-G3", po_id="PO-700", item="Server Rack", quantity=5.0, unit_price=1000.0, tax_pct=18.0, line_total=5900.0, status="credited"),
    ]

    # No goods_receipts -> emits nothing
    assert [f for f in run_all_rules(DetectionContext(invoices=invs)) if f.rule_id == "R7"] == []

    # GRN matches billed qty (10) -> emits nothing
    grn_match = [{"grn_id": "GRN-1", "po_id": "PO-700", "item": "Server Rack", "received_qty": 10.0, "accepted_qty": 10.0}]
    assert [f for f in run_all_rules(DetectionContext(invoices=invs, goods_receipts=grn_match)) if f.rule_id == "R7"] == []

    # GRN accepted_qty (7) < billed_qty (10) -> excess 3 units * 1180 = 3540.0
    grn_short = [
        {"grn_id": "GRN-1", "po_id": "PO-700", "item": "Server Rack", "received_qty": 8.0, "accepted_qty": 5.0},
        {"grn_id": "GRN-2", "po_id": "PO-700", "item": "Server Rack", "received_qty": 2.0, "accepted_qty": 2.0},
    ]
    r7 = [f for f in run_all_rules(DetectionContext(invoices=invs, goods_receipts=grn_short)) if f.rule_id == "R7"]
    assert len(r7) == 1
    f = r7[0]
    assert f.recommended_action == "HOLD_PAYMENT"
    assert f.amount_at_risk == 3540.0
    assert f.entity_refs["grn_ids"] == ["GRN-1", "GRN-2"]
    assert f.entity_refs["invoice_numbers"] == ["INV-G1", "INV-G2"]
    assert f.proof_trail["math"]["billed_qty"] == 10.0
    assert f.proof_trail["math"]["grn_qty"] == 7.0
    assert f.proof_trail["math"]["excess_qty"] == 3.0

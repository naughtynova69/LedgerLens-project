"""Unit tests for R1 (duplicate detection) — the reference rule.

Run:  cd backend && python -m pytest -q
"""
from app.detect.registry import DetectionContext, run_all


def _invoice_line(invoice_number, invoice_date, *, vendor="V001", status="unpaid",
                  item="LED Panel 18W", quantity=10, unit_price=420.0):
    return {
        "invoice_number": invoice_number,
        "vendor_id": vendor,
        "invoice_date": invoice_date,
        "po_id": "PO-1001",
        "line_no": 1,
        "item": item,
        "quantity": quantity,
        "unit_price": unit_price,
        "currency": "INR",
        "tax_pct": 18.0,
        "line_total": round(quantity * unit_price * 1.18, 2),
        "status": status,
    }


def _payment(payment_id, invoice_number, amount):
    return {
        "payment_id": payment_id,
        "invoice_number": invoice_number,
        "amount": amount,
        "currency": "INR",
        "fx_rate_to_inr": 1.0,
        "payment_date": "2026-10-22",
        "status": "settled",
    }


def test_detects_paid_duplicate_from_sample_data():
    """INV-8821 vs INV-8821-R2 — the planted anomaly (docs/04 §R1)."""
    lines = [
        _invoice_line("INV-8821", "2026-10-14", status="paid"),
        _invoice_line("INV-8821-R2", "2026-10-16", status="paid"),
    ]
    payments = [
        _payment("PAY-5001", "INV-8821", 4956.00),
        _payment("PAY-5002", "INV-8821-R2", 4956.00),
    ]
    findings = run_all(DetectionContext(
        invoices=lines, payments=payments,
        purchase_orders=[], contracts=[], vendors=[]))

    assert len(findings) == 1
    finding = findings[0]
    assert finding.rule_id == "R1"
    assert finding.severity == "critical"          # money already gone
    assert finding.amount_at_risk == 4956.00
    assert finding.confidence >= 0.9
    evidence_ids = {e.record_id for e in finding.evidence}
    assert {"INV-8821", "INV-8821-R2", "PAY-5001", "PAY-5002"} <= evidence_ids
    assert "duplicate" in finding.title.lower()


def test_unpaid_duplicate_is_high_not_critical():
    lines = [
        _invoice_line("INV-8001", "2026-10-14", status="unpaid"),
        _invoice_line("INV-8001-V2", "2026-10-15", status="unpaid"),
    ]
    findings = run_all(DetectionContext(
        invoices=lines, payments=[], purchase_orders=[], contracts=[], vendors=[]))
    assert len(findings) == 1
    assert findings[0].severity == "high"


def test_no_finding_for_distinct_invoices():
    lines = [
        _invoice_line("INV-A", "2026-10-14", quantity=10, unit_price=420.0, status="paid"),
        _invoice_line("INV-B", "2026-11-20", quantity=4, unit_price=410.0, status="unpaid"),
    ]
    findings = run_all(DetectionContext(
        invoices=lines, payments=[], purchase_orders=[], contracts=[], vendors=[]))
    assert findings == []


def test_credit_note_guard_allows_revised_invoice():
    """A credit note against one invoice = legitimate revised invoice, not a duplicate."""
    lines = [
        _invoice_line("INV-8821", "2026-10-14", status="paid"),
        _invoice_line("INV-8821-R2", "2026-10-16", status="credited"),
    ]
    findings = run_all(DetectionContext(
        invoices=lines, payments=[], purchase_orders=[], contracts=[], vendors=[]))
    assert findings == []


def test_same_amount_different_vendor_does_not_fire():
    lines = [
        _invoice_line("INV-X", "2026-10-14", vendor="V001", status="paid"),
        _invoice_line("INV-Y", "2026-10-15", vendor="V002", status="paid"),
    ]
    findings = run_all(DetectionContext(
        invoices=lines, payments=[], purchase_orders=[], contracts=[], vendors=[]))
    assert findings == []

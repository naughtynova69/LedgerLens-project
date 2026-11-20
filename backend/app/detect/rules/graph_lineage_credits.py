"""R8 — Contract amendment lineage & unapplied credit notes (deterministic core).

Spec: master-prompt §4 R8. The Cypher layer traverses AMENDS*1..5 lineage and
OPEN credit notes; this module re-verifies the deterministic math (billed rate
matches the superseded contract, invoice post-dates the amendment) and emits
the Finding with the serialized proof_subgraph.

Tabular R2 cannot see this: it only compares against contracts whose status is
'active' in the ERP master data — the exact ERP-lag scenario where a signed
amendment has not yet been flipped to active is what the graph lineage catches.

Confidence values are rule constants; no LLM ever produces them.
"""
from __future__ import annotations

from datetime import date

from ..registry import DetectionContext, register
from ..types import EvidenceRef, Finding

RATE_MATCH_TOLERANCE = 0.005   # billed rate must match the superseded rate (0.5%)


def _iso(value: str) -> date | None:
    try:
        return date.fromisoformat(str(value or "")[:10])
    except ValueError:
        return None


@register("R8")
def detect_contract_lineage_and_credits(ctx: DetectionContext) -> list[Finding]:
    findings: list[Finding] = []
    evidence_map = getattr(ctx, "graph_evidence", None) or {}

    # --- Pattern 1: invoices billed at a superseded contract rate ---
    for row in evidence_map.get("superseded_rates", []):
        old_rate = float(row.get("old_rate") or 0.0)
        new_rate = float(row.get("new_rate") or 0.0)
        quantity = float(row.get("quantity") or 0.0)
        billed_rate = float(row.get("line_unit_price") or 0.0)
        if old_rate <= 0 or new_rate <= 0 or new_rate >= old_rate or quantity <= 0:
            continue
        if abs(billed_rate - old_rate) > old_rate * RATE_MATCH_TOLERANCE:
            continue  # invoice already bills at (or near) the amended rate
        invoice_date = _iso(str(row.get("invoice_date") or ""))
        effective_date = _iso(str(row.get("new_effective_date") or ""))
        if invoice_date is None or effective_date is None or invoice_date < effective_date:
            continue

        amount_at_risk = round((old_rate - new_rate) * quantity, 2)
        invoice_status = str(row.get("invoice_status") or "").lower()
        invoice_number = str(row.get("invoice_number") or "")

        findings.append(Finding(
            rule_id="R8",
            title="Invoices billed under superseded contract rate after amendment",
            severity="critical" if invoice_status == "paid" else "high",
            amount_at_risk=amount_at_risk,
            currency=str(row.get("currency") or "INR"),
            entity_refs={
                "invoice_numbers": [invoice_number],
                "line_no": int(str(row.get("line_id") or "0#1").split("#")[-1] or 1),
                "contract_id": str(row.get("new_contract_id") or ""),
                "superseded_contract_id": str(row.get("old_contract_id") or ""),
                "vendor_id": "",
                "po_id": "",
            },
            evidence=[
                EvidenceRef("invoices", invoice_number, "unit_price",
                            f"{billed_rate:,.2f} {row.get('currency') or 'INR'}"),
                EvidenceRef("contracts", row.get("old_contract_id"), "contracted_unit_price",
                            f"{old_rate:,.2f} {row.get('currency') or 'INR'}"),
                EvidenceRef("contracts", row.get("new_contract_id"), "contracted_unit_price",
                            f"{new_rate:,.2f} {row.get('currency') or 'INR'}"),
            ],
            confidence=0.93,
            recommended_action="REQUEST_CREDIT_NOTE" if invoice_status == "paid" else "DISPUTE_VENDOR",
            summary=(
                f"Invoice {invoice_number} bills {quantity:g} unit(s) at the superseded rate "
                f"{old_rate:,.2f} {row.get('currency') or 'INR'} under contract "
                f"{row.get('old_contract_id')}, while amendment {row.get('new_contract_id')} "
                f"(effective {row.get('new_effective_date')}) lowered the rate to "
                f"{new_rate:,.2f}. Recovery exposure: {amount_at_risk:,.2f} "
                f"{row.get('currency') or 'INR'}."
            ),
            proof_trail={
                "math": {
                    "superseded_rate": round(old_rate, 4),
                    "amended_rate": round(new_rate, 4),
                    "billed_rate": round(billed_rate, 4),
                    "quantity": quantity,
                    "amount_at_risk": amount_at_risk,
                    "amendment_effective_date": row.get("new_effective_date"),
                    "invoice_date": row.get("invoice_date"),
                },
                "proof_subgraph": row.get("proof_subgraph") or {},
            },
        ))

    # --- Pattern 2: OPEN supplier credit notes while the vendor keeps billing ---
    for row in evidence_map.get("unapplied_credits", []):
        credit_amount = float(row.get("credit_note_amount") or 0.0)
        if credit_amount <= 0:
            continue
        credit_note_id = str(row.get("credit_note_id") or "")
        vendor_id = str(row.get("vendor_id") or "")
        invoice_numbers = list(row.get("invoice_numbers") or [])

        findings.append(Finding(
            rule_id="R8",
            title="Open supplier credit note unapplied while vendor continues billing",
            severity="medium",
            amount_at_risk=round(credit_amount, 2),
            currency=str(row.get("credit_note_currency") or "INR"),
            entity_refs={
                "vendor_id": vendor_id,
                "credit_note_id": credit_note_id,
                "invoice_numbers": invoice_numbers,
            },
            evidence=[
                EvidenceRef("credit_notes", credit_note_id, "amount",
                            f"{credit_amount:,.2f} {row.get('credit_note_currency') or 'INR'}"),
                EvidenceRef("graph", vendor_id, "open_credit_note", credit_note_id),
            ],
            confidence=0.85,
            recommended_action="APPLY_CREDIT_NOTE",
            summary=(
                f"Supplier credit note {credit_note_id} ({credit_amount:,.2f} "
                f"{row.get('credit_note_currency') or 'INR'}, issued "
                f"{row.get('credit_note_issue_date')}) is still OPEN while vendor "
                f"{vendor_id} has billed afterwards (e.g. {', '.join(invoice_numbers[:3])}) "
                f"— cash left on the table."
            ),
            proof_trail={
                "math": {
                    "credit_note_amount": round(credit_amount, 2),
                    "credit_note_issue_date": row.get("credit_note_issue_date"),
                    "subsequent_invoices": invoice_numbers,
                    "amount_at_risk": round(credit_amount, 2),
                },
                "proof_subgraph": row.get("proof_subgraph") or {},
            },
        ))

    return findings

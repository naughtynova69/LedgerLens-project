"""R5 — Cancelled-service leakage detector.

Spec: docs/04_DETECTION_RULES.md §R5.

Why it fires:
    Vendors keep billing recurring charges for cancelled software,
    terminated contracts, or returned goods. Nobody in AP connects the
    cancellation memo to next month's invoice — LedgerLens does.
"""
from __future__ import annotations

from ..registry import DetectionContext, register
from ..types import EvidenceRef, Finding


def _norm_item(s: str) -> str:
    return " ".join(str(s or "").strip().lower().split())


@register("R5")
def detect_cancelled_service_leakage(ctx: DetectionContext) -> list[Finding]:
    findings: list[Finding] = []

    # Map cancelled contracts by (vendor_id, norm_item)
    cancelled_contracts: dict[tuple[str, str], list[dict]] = {}
    for c in ctx.contracts:
        if str(c.get("status", "")).lower() == "cancelled":
            key = (str(c.get("vendor_id", "")), _norm_item(c.get("item", "")))
            cancelled_contracts.setdefault(key, []).append(c)

    for inv in ctx.invoices:
        vendor_id = str(inv.get("vendor_id", ""))
        item_norm = _norm_item(inv.get("item", ""))
        key = (vendor_id, item_norm)
        if key not in cancelled_contracts:
            continue

        inv_num = str(inv.get("invoice_number", ""))
        inv_date = str(inv.get("invoice_date") or "")
        inv_status = str(inv.get("status") or "").lower()
        inv_curr = str(inv.get("currency") or "INR")
        line_total = float(inv.get("line_total") or 0.0)

        for contract in cancelled_contracts[key]:
            end_date = str(contract.get("end_date") or "")
            contract_id = str(contract.get("contract_id", ""))

            if end_date and inv_date and inv_date > end_date:
                severity = "critical" if inv_status == "paid" else "high"
                findings.append(
                    Finding(
                        rule_id="R5",
                        title=f"Billed after contract cancellation ({inv.get('item', 'Item')})",
                        severity=severity,
                        amount_at_risk=line_total,
                        currency=inv_curr,
                        entity_refs={
                            "invoice_numbers": [inv_num],
                            "contract_id": contract_id,
                            "vendor_id": vendor_id,
                        },
                        evidence=[
                            EvidenceRef("contracts", contract_id, "status", "cancelled"),
                            EvidenceRef("contracts", contract_id, "end_date", end_date),
                            EvidenceRef("invoices", inv_num, "invoice_date", inv_date),
                            EvidenceRef("invoices", inv_num, "line_total", f"{line_total:.2f} {inv_curr}"),
                        ],
                        confidence=0.98,
                        summary=(
                            f"Invoice {inv_num} dated {inv_date} for {inv.get('item')} was billed after "
                            f"contract {contract_id} was cancelled effective {end_date}. "
                            f"Disallowed spend: {line_total:.2f} {inv_curr}."
                        ),
                    )
                )

    return findings

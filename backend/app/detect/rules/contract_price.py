"""R2 — Contract price leakage detector.

Spec: docs/04_DETECTION_RULES.md §R2.

Why it fires:
    Invoiced unit prices above the negotiated contract rate (or missed
    agreed discounts) are silent overcharges — the invoice looks normal,
    the PO may even approve it, but the contract governs.
"""
from __future__ import annotations

from ..registry import DetectionContext, register
from ..types import EvidenceRef, Finding


def _norm_item(s: str) -> str:
    return " ".join(str(s or "").strip().lower().split())


@register("R2")
def detect_contract_price_leakage(ctx: DetectionContext) -> list[Finding]:
    findings: list[Finding] = []

    # Map active contracts by (vendor_id, norm_item)
    contracts_by_key: dict[tuple[str, str], list[dict]] = {}
    for c in ctx.contracts:
        if str(c.get("status", "")).lower() != "active":
            continue
        key = (str(c.get("vendor_id", "")), _norm_item(c.get("item", "")))
        contracts_by_key.setdefault(key, []).append(c)

    for inv in ctx.invoices:
        vendor_id = str(inv.get("vendor_id", ""))
        item_norm = _norm_item(inv.get("item", ""))
        key = (vendor_id, item_norm)
        if key not in contracts_by_key:
            continue

        inv_unit_price = float(inv.get("unit_price") or 0.0)
        inv_qty = float(inv.get("quantity") or 0.0)
        inv_tax_pct = float(inv.get("tax_pct") or 0.0)
        inv_date = str(inv.get("invoice_date") or "")
        inv_status = str(inv.get("status") or "").lower()

        for contract in contracts_by_key[key]:
            start_date = str(contract.get("start_date") or "")
            end_date = str(contract.get("end_date") or "")
            if start_date and inv_date and inv_date < start_date:
                continue
            if end_date and inv_date and inv_date > end_date:
                continue

            contracted_price = float(contract.get("contracted_unit_price") or 0.0)
            if inv_unit_price > contracted_price + 1e-4:
                unit_delta = inv_unit_price - contracted_price
                amount_at_risk = round(unit_delta * inv_qty * (1.0 + inv_tax_pct / 100.0), 2)
                severity = "critical" if inv_status == "paid" else "high"
                contract_id = str(contract.get("contract_id", ""))
                inv_num = str(inv.get("invoice_number", ""))
                currency = str(inv.get("currency") or contract.get("currency") or "INR")

                findings.append(
                    Finding(
                        rule_id="R2",
                        title=f"Contract price leakage on {inv.get('item', 'Item')}",
                        severity=severity,
                        amount_at_risk=amount_at_risk,
                        currency=currency,
                        entity_refs={
                            "invoice_numbers": [inv_num],
                            "contract_id": contract_id,
                            "vendor_id": vendor_id,
                            "po_id": str(inv.get("po_id") or ""),
                        },
                        evidence=[
                            EvidenceRef("invoices", inv_num, "unit_price", f"{inv_unit_price:.2f} {currency}"),
                            EvidenceRef("contracts", contract_id, "contracted_unit_price", f"{contracted_price:.2f} {currency}"),
                            EvidenceRef("invoices", inv_num, "quantity", str(inv_qty)),
                            EvidenceRef("invoices", inv_num, "tax_pct", f"{inv_tax_pct}%"),
                        ],
                        confidence=0.95,
                        summary=(
                            f"Invoice {inv_num} billed {inv.get('item')} at {inv_unit_price:.2f} {currency} "
                            f"vs contracted rate of {contracted_price:.2f} {currency} under contract {contract_id}. "
                            f"Overcharge across {inv_qty:g} units totals {amount_at_risk:.2f} {currency} (tax inclusive)."
                        ),
                    )
                )

    return findings

"""R2 — Contract price leakage detector (deterministic core).

Spec: docs/04_DETECTION_RULES.md §R2.

The contract governs: even when a PO carries an inflated price, R2 checks
invoiced unit_price against contracts.contracted_unit_price (accounting for
agreed discount_pct and contract start_date/end_date validity).
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
        line_no = int(inv.get("line_no") or 1)

        for contract in contracts_by_key[key]:
            start_date = str(contract.get("start_date") or "")
            end_date = str(contract.get("end_date") or "")
            if start_date and inv_date and inv_date < start_date:
                continue
            if end_date and inv_date and inv_date > end_date:
                continue

            contracted_price = float(contract.get("contracted_unit_price") or 0.0)
            discount_pct = float(contract.get("discount_pct") or 0.0)
            discounted_rate = round(contracted_price * (1.0 - discount_pct / 100.0), 4)

            # Guard against false positives when invoices omit discount_applied_pct on nominal base price
            has_discount_col = "discount_applied_pct" in inv and inv.get("discount_applied_pct") not in (None, "")
            if inv_unit_price > contracted_price + 1e-4:
                governed_rate = discounted_rate if discount_pct > 0 else contracted_price
            elif has_discount_col and discount_pct > 0:
                applied_disc = float(inv.get("discount_applied_pct") or 0.0)
                effective_billed = inv_unit_price * (1.0 - applied_disc / 100.0)
                if effective_billed <= discounted_rate + 1e-4:
                    continue
                governed_rate = discounted_rate
                inv_unit_price = effective_billed
            else:
                continue

            unit_delta = inv_unit_price - governed_rate
            amount_at_risk = round(unit_delta * inv_qty * (1.0 + inv_tax_pct / 100.0), 2)
            severity = "critical" if inv_status == "paid" else "high"
            recommended_action = "REQUEST_CREDIT_NOTE" if inv_status == "paid" else "DISPUTE_VENDOR"
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
                        "line_no": line_no,
                        "contract_id": contract_id,
                        "vendor_id": vendor_id,
                        "po_id": str(inv.get("po_id") or ""),
                    },
                    evidence=[
                        EvidenceRef("invoices", inv_num, "unit_price", f"{inv_unit_price:.2f} {currency}"),
                        EvidenceRef("contracts", contract_id, "contracted_unit_price", f"{governed_rate:.2f} {currency}"),
                        EvidenceRef("invoices", inv_num, "quantity", str(inv_qty)),
                        EvidenceRef("invoices", inv_num, "tax_pct", f"{inv_tax_pct}%"),
                    ],
                    confidence=0.95,
                    recommended_action=recommended_action,
                    summary=(
                        f"Invoice {inv_num} billed {inv.get('item')} at {inv_unit_price:.2f} {currency} "
                        f"vs contracted rate of {governed_rate:.2f} {currency} under contract {contract_id}. "
                        f"Overcharge across {inv_qty:g} units totals {amount_at_risk:.2f} {currency} (tax inclusive)."
                    ),
                    proof_trail={
                        "math": {
                            "billed_unit_price": round(inv_unit_price, 4),
                            "contracted_unit_price": round(contracted_price, 4),
                            "discount_pct": round(discount_pct, 2),
                            "effective_contracted_price": round(governed_rate, 4),
                            "unit_delta": round(unit_delta, 4),
                            "quantity": inv_qty,
                            "tax_pct": inv_tax_pct,
                            "amount_at_risk": amount_at_risk,
                        }
                    },
                )
            )

    return findings

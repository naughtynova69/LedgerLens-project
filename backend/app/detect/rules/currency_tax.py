"""R4 — Currency & tax error detector.

Spec: docs/04_DETECTION_RULES.md §R4.

Why it fires:
    Wrong currency, stale FX conversion, duplicate tax lines, or tax applied
    where an exemption applies each silently inflate what the company pays.
    Data-entry errors and currency mismatches account for ~20% each of
    enterprise payment-error value.
"""
from __future__ import annotations

from ..registry import DetectionContext, register
from ..types import EvidenceRef, Finding


def _norm_item(s: str) -> str:
    return " ".join(str(s or "").strip().lower().split())


@register("R4")
def detect_currency_tax_errors(ctx: DetectionContext) -> list[Finding]:
    findings: list[Finding] = []

    # Map purchase orders by po_id
    po_by_id: dict[str, dict] = {}
    for po in ctx.purchase_orders:
        po_by_id[str(po.get("po_id", ""))] = po

    # Map contracts by (vendor_id, norm_item)
    contracts_map: dict[tuple[str, str], dict] = {}
    for c in ctx.contracts:
        contracts_map[(str(c.get("vendor_id", "")), _norm_item(c.get("item", "")))] = c

    for inv in ctx.invoices:
        inv_num = str(inv.get("invoice_number", ""))
        vendor_id = str(inv.get("vendor_id", ""))
        po_id = str(inv.get("po_id") or "").strip()
        item_norm = _norm_item(inv.get("item", ""))
        inv_curr = str(inv.get("currency") or "").strip().upper()
        inv_tax = float(inv.get("tax_pct") or 0.0)
        inv_qty = float(inv.get("quantity") or 0.0)
        inv_price = float(inv.get("unit_price") or 0.0)
        line_total = float(inv.get("line_total") or (inv_qty * inv_price * (1.0 + inv_tax / 100.0)))

        # Check 1: Currency Mismatch against PO
        if po_id and po_id in po_by_id:
            po = po_by_id[po_id]
            po_curr = str(po.get("currency") or "").strip().upper()
            if inv_curr and po_curr and inv_curr != po_curr:
                findings.append(
                    Finding(
                        rule_id="R4",
                        title=f"Currency mismatch on invoice {inv_num}",
                        severity="high",
                        amount_at_risk=line_total,
                        currency=inv_curr,
                        entity_refs={
                            "invoice_numbers": [inv_num],
                            "po_id": po_id,
                            "vendor_id": vendor_id,
                        },
                        evidence=[
                            EvidenceRef("invoices", inv_num, "currency", inv_curr),
                            EvidenceRef("purchase_orders", po_id, "currency", po_curr),
                            EvidenceRef("invoices", inv_num, "line_total", f"{line_total:.2f} {inv_curr}"),
                        ],
                        confidence=0.94,
                        summary=(
                            f"Invoice {inv_num} billed in {inv_curr} against purchase order {po_id} "
                            f"which was authorized in {po_curr}. Unauthorized foreign exchange exposure: {line_total:.2f} {inv_curr}."
                        ),
                    )
                )

        # Check 2: Tax Error against Contract
        key = (vendor_id, item_norm)
        if key in contracts_map:
            contract = contracts_map[key]
            contract_tax = float(contract.get("tax_pct") or 0.0)
            contract_id = str(contract.get("contract_id", ""))
            contract_curr = str(contract.get("currency") or inv_curr or "INR")

            if inv_tax > contract_tax + 1e-4:
                tax_delta_pct = inv_tax - contract_tax
                tax_at_risk = round(inv_qty * inv_price * (tax_delta_pct / 100.0), 2)
                findings.append(
                    Finding(
                        rule_id="R4",
                        title=f"Invalid tax charge on {inv.get('item', 'Item')}",
                        severity="high",
                        amount_at_risk=tax_at_risk,
                        currency=inv_curr or contract_curr,
                        entity_refs={
                            "invoice_numbers": [inv_num],
                            "contract_id": contract_id,
                            "vendor_id": vendor_id,
                        },
                        evidence=[
                            EvidenceRef("invoices", inv_num, "tax_pct", f"{inv_tax:g}%"),
                            EvidenceRef("contracts", contract_id, "tax_pct", f"{contract_tax:g}%"),
                            EvidenceRef("invoices", inv_num, "tax_delta", f"{tax_delta_pct:g}%"),
                        ],
                        confidence=0.96,
                        summary=(
                            f"Invoice {inv_num} applied {inv_tax:g}% GST on {inv.get('item')}, "
                            f"which contract {contract_id} specifies as {contract_tax:g}% (exempt). "
                            f"Unwarranted tax exposure: {tax_at_risk:.2f} {inv_curr}."
                        ),
                    )
                )

    return findings

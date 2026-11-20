"""R3 — PO mismatch & overbilling detector.

Spec: docs/04_DETECTION_RULES.md §R3.

Why it fires:
    Billing above PO quantity, before delivery, or for items not on the PO
    means the company pays for goods/services it never agreed to receive
    at that volume.
"""
from __future__ import annotations

from difflib import SequenceMatcher
from ..registry import DetectionContext, register
from ..types import EvidenceRef, Finding


def _norm_item(s: str) -> str:
    return " ".join(str(s or "").strip().lower().split())


def _is_duplicate_pair(a: dict, b: dict) -> bool:
    """Return True if b is a duplicate resubmission of a."""
    if str(a.get("vendor_id")) != str(b.get("vendor_id")):
        return False
    if _norm_item(a.get("item", "")) != _norm_item(b.get("item", "")):
        return False
    if float(a.get("quantity") or 0) != float(b.get("quantity") or 0):
        return False
    if float(a.get("unit_price") or 0) != float(b.get("unit_price") or 0):
        return False
    # Check invoice number similarity
    num_a = str(a.get("invoice_number", ""))
    num_b = str(b.get("invoice_number", ""))
    if num_a != num_b and SequenceMatcher(None, num_a, num_b).ratio() >= 0.6:
        return True
    return False


@register("R3")
def detect_po_mismatch(ctx: DetectionContext) -> list[Finding]:
    findings: list[Finding] = []

    # Map purchase orders by (po_id, norm_item)
    po_map: dict[tuple[str, str], dict] = {}
    for po in ctx.purchase_orders:
        if str(po.get("status", "")).lower() == "cancelled":
            continue
        key = (str(po.get("po_id", "")), _norm_item(po.get("item", "")))
        po_map[key] = po

    # Group invoice lines by (po_id, norm_item)
    billed_by_po_item: dict[tuple[str, str], list[dict]] = {}
    for inv in ctx.invoices:
        po_id = str(inv.get("po_id") or "").strip()
        if not po_id:
            continue
        item_norm = _norm_item(inv.get("item", ""))
        key = (po_id, item_norm)
        billed_by_po_item.setdefault(key, []).append(inv)

    for (po_id, item_norm), inv_lines in billed_by_po_item.items():
        if (po_id, item_norm) not in po_map:
            continue
        po = po_map[(po_id, item_norm)]
        po_qty = float(po.get("quantity") or 0.0)
        po_unit_price = float(po.get("unit_price") or 0.0)
        po_currency = str(po.get("currency") or "INR")

        # Exclude resubmitted duplicate invoices from cumulative quantity summation
        unique_lines: list[dict] = []
        for line in inv_lines:
            if not any(_is_duplicate_pair(prev, line) for prev in unique_lines):
                unique_lines.append(line)

        total_billed_qty = sum(float(inv.get("quantity") or 0.0) for inv in unique_lines)
        if total_billed_qty > po_qty + 1e-4:
            excess = total_billed_qty - po_qty
            tax_pct = float(unique_lines[0].get("tax_pct") or 0.0)
            amount_at_risk = round(excess * po_unit_price * (1.0 + tax_pct / 100.0), 2)
            inv_nums = sorted(list({str(inv.get("invoice_number", "")) for inv in unique_lines}))

            findings.append(
                Finding(
                    rule_id="R3",
                    title=f"PO overbilling on {po.get('item', 'Item')} ({po_id})",
                    severity="high",
                    amount_at_risk=amount_at_risk,
                    currency=po_currency,
                    entity_refs={
                        "po_id": po_id,
                        "invoice_numbers": inv_nums,
                        "vendor_id": str(po.get("vendor_id") or ""),
                    },
                    evidence=[
                        EvidenceRef("purchase_orders", po_id, "quantity", f"{po_qty:g}"),
                        EvidenceRef("invoices", ", ".join(inv_nums), "total_billed_quantity", f"{total_billed_qty:g}"),
                        EvidenceRef("purchase_orders", po_id, "unit_price", f"{po_unit_price:.2f} {po_currency}"),
                    ],
                    confidence=0.92,
                    summary=(
                        f"Cumulative billed quantity across invoice(s) {', '.join(inv_nums)} is {total_billed_qty:g} units, "
                        f"exceeding authorized PO quantity of {po_qty:g} units on {po_id} by {excess:g} units. "
                        f"Excess exposure: {amount_at_risk:.2f} {po_currency}."
                    ),
                )
            )

    return findings

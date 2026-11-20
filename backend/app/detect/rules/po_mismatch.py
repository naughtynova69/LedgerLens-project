"""R3 — PO mismatch & overbilling detector (deterministic core).

Spec: docs/04_DETECTION_RULES.md §R3.

Detects:
1. Cumulative billed quantity above purchase_orders.quantity (excluding R1 duplicate lines)
2. Premature billing (invoice_date < po.expected_delivery when PO is not yet delivered/closed)
3. Uncontracted / absent item billed against an existing PO (item not listed on that PO)
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
    num_a = str(a.get("invoice_number", ""))
    num_b = str(b.get("invoice_number", ""))
    return num_a != num_b and SequenceMatcher(None, num_a, num_b).ratio() >= 0.6


@register("R3")
def detect_po_mismatch(ctx: DetectionContext) -> list[Finding]:
    findings: list[Finding] = []

    po_map: dict[tuple[str, str], dict] = {}
    known_po_ids: set[str] = set()
    po_by_id: dict[str, dict] = {}
    for po in ctx.purchase_orders:
        po_id = str(po.get("po_id") or "").strip()
        if str(po.get("status", "")).lower() == "cancelled":
            continue
        if po_id:
            known_po_ids.add(po_id)
            po_by_id.setdefault(po_id, po)
        key = (po_id, _norm_item(po.get("item", "")))
        po_map[key] = po

    billed_by_po_item: dict[tuple[str, str], list[dict]] = {}
    for inv in ctx.invoices:
        po_id = str(inv.get("po_id") or "").strip()
        if not po_id:
            continue
        item_norm = _norm_item(inv.get("item", ""))
        key = (po_id, item_norm)

        # Check 3: Item absent from an existing, non-cancelled PO
        if po_id in known_po_ids and key not in po_map:
            inv_num = str(inv.get("invoice_number", ""))
            line_no = int(inv.get("line_no") or 1)
            line_total = float(inv.get("line_total") or 0.0)
            curr = str(inv.get("currency") or po_by_id[po_id].get("currency") or "INR")
            findings.append(
                Finding(
                    rule_id="R3",
                    title=f"Unordered item billed against {po_id}",
                    severity="high",
                    amount_at_risk=round(line_total, 2),
                    currency=curr,
                    entity_refs={
                        "po_id": po_id,
                        "invoice_numbers": [inv_num],
                        "line_no": line_no,
                        "vendor_id": str(inv.get("vendor_id") or ""),
                    },
                    evidence=[
                        EvidenceRef("invoices", inv_num, "item", str(inv.get("item") or "")),
                        EvidenceRef("purchase_orders", po_id, "item", "NOT_ON_PO"),
                        EvidenceRef("invoices", inv_num, "line_total", f"{line_total:.2f} {curr}"),
                    ],
                    confidence=0.90,
                    recommended_action="DISPUTE_VENDOR",
                    summary=(
                        f"Invoice {inv_num} billed '{inv.get('item')}' ({line_total:.2f} {curr}) "
                        f"under {po_id}, which does not authorize that item."
                    ),
                    proof_trail={
                        "math": {
                            "po_id": po_id,
                            "billed_item": str(inv.get("item") or ""),
                            "line_total": round(line_total, 2),
                        }
                    },
                )
            )
            continue

        billed_by_po_item.setdefault(key, []).append(inv)

    for (po_id, item_norm), inv_lines in billed_by_po_item.items():
        if (po_id, item_norm) not in po_map:
            continue
        po = po_map[(po_id, item_norm)]
        po_qty = float(po.get("quantity") or 0.0)
        po_unit_price = float(po.get("unit_price") or 0.0)
        po_currency = str(po.get("currency") or "INR")
        po_status = str(po.get("status") or "").lower()
        expected_delivery = str(po.get("expected_delivery") or "").strip()

        # Exclude resubmitted duplicate invoices from cumulative quantity summation
        unique_lines: list[dict] = []
        for line in inv_lines:
            if not any(_is_duplicate_pair(prev, line) for prev in unique_lines):
                unique_lines.append(line)

        # Check 1: Quantity overbilling
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
                        "line_no": int(unique_lines[0].get("line_no") or 1),
                        "vendor_id": str(po.get("vendor_id") or ""),
                    },
                    evidence=[
                        EvidenceRef("purchase_orders", po_id, "quantity", f"{po_qty:g}"),
                        EvidenceRef("invoices", ", ".join(inv_nums), "total_billed_quantity", f"{total_billed_qty:g}"),
                        EvidenceRef("purchase_orders", po_id, "unit_price", f"{po_unit_price:.2f} {po_currency}"),
                    ],
                    confidence=0.92,
                    recommended_action="HOLD_PAYMENT",
                    summary=(
                        f"Cumulative billed quantity across invoice(s) {', '.join(inv_nums)} is {total_billed_qty:g} units, "
                        f"exceeding authorized PO quantity of {po_qty:g} units on {po_id} by {excess:g} units. "
                        f"Excess exposure: {amount_at_risk:.2f} {po_currency}."
                    ),
                    proof_trail={
                        "math": {
                            "authorized_po_qty": po_qty,
                            "total_billed_qty": total_billed_qty,
                            "excess_qty": excess,
                            "po_unit_price": po_unit_price,
                            "tax_pct": tax_pct,
                            "amount_at_risk": amount_at_risk,
                        }
                    },
                )
            )

        # Check 2: Premature billing before expected_delivery on open (undelivered) POs
        if expected_delivery and po_status not in ("delivered", "received", "closed"):
            for inv in unique_lines:
                inv_date = str(inv.get("invoice_date") or "").strip()
                if inv_date and inv_date < expected_delivery:
                    inv_num = str(inv.get("invoice_number", ""))
                    line_total = float(inv.get("line_total") or 0.0)
                    findings.append(
                        Finding(
                            rule_id="R3",
                            title=f"Premature billing before delivery ({po_id})",
                            severity="medium",
                            amount_at_risk=round(line_total, 2),
                            currency=po_currency,
                            entity_refs={
                                "po_id": po_id,
                                "invoice_numbers": [inv_num],
                                "line_no": int(inv.get("line_no") or 1),
                                "vendor_id": str(po.get("vendor_id") or ""),
                            },
                            evidence=[
                                EvidenceRef("invoices", inv_num, "invoice_date", inv_date),
                                EvidenceRef("purchase_orders", po_id, "expected_delivery", expected_delivery),
                                EvidenceRef("purchase_orders", po_id, "status", po_status or "open"),
                            ],
                            confidence=0.88,
                            recommended_action="HOLD_PAYMENT",
                            summary=(
                                f"Invoice {inv_num} dated {inv_date} bills {po.get('item')} before "
                                f"expected delivery date {expected_delivery} on {po_status or 'open'} {po_id}."
                            ),
                            proof_trail={
                                "math": {
                                    "invoice_date": inv_date,
                                    "expected_delivery": expected_delivery,
                                    "po_status": po_status or "open",
                                    "line_total": round(line_total, 2),
                                }
                            },
                        )
                    )

    return findings

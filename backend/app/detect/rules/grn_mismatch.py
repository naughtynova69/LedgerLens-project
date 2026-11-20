"""R7 — 3-Way GRN Mismatch detector (deterministic core).

Compares total billed invoice quantities against Goods Receipt Note (GRN)
received/accepted quantities for each (po_id, item). If `goods_receipts` is
empty or absent, emits nothing.
"""
from __future__ import annotations

from ..registry import DetectionContext, register
from ..types import EvidenceRef, Finding


def _norm_item(s: object) -> str:
    return " ".join(str(s or "").strip().lower().split())


@register("R7")
def detect_grn_mismatch(ctx: DetectionContext) -> list[Finding]:
    """Detect invoices billing more quantity than received/accepted in GRNs."""
    goods_receipts = (
        ctx.get("goods_receipts", [])
        if isinstance(ctx, dict)
        else (getattr(ctx, "goods_receipts", []) or [])
    )
    if not goods_receipts:
        return []

    invoices = (
        ctx.get("invoices", [])
        if isinstance(ctx, dict)
        else (getattr(ctx, "invoices", []) or [])
    )
    if not invoices:
        return []

    grn_by_key: dict[tuple[str, str], dict] = {}
    for grn in goods_receipts:
        po_id = str(grn.get("po_id") or "").strip()
        item_norm = _norm_item(grn.get("item"))
        if not po_id or not item_norm:
            continue

        if grn.get("accepted_qty") is not None:
            qty = float(grn["accepted_qty"])
            qty_field = "accepted_qty"
        else:
            qty = float(grn.get("received_qty") or 0.0)
            qty_field = "received_qty"

        entry = grn_by_key.setdefault(
            (po_id, item_norm),
            {
                "po_id": po_id,
                "display_item": str(grn.get("item") or item_norm),
                "total_qty": 0.0,
                "grn_ids": [],
                "qty_field": qty_field,
            },
        )
        entry["total_qty"] += qty
        grn_id = str(grn.get("grn_id") or "").strip()
        if grn_id:
            entry["grn_ids"].append(grn_id)

    if not grn_by_key:
        return []

    billed_by_key: dict[tuple[str, str], dict] = {}
    for inv in invoices:
        if str(inv.get("status") or "").strip().lower() == "credited":
            continue
        po_id = str(inv.get("po_id") or "").strip()
        item_norm = _norm_item(inv.get("item"))
        key = (po_id, item_norm)
        if key not in grn_by_key:
            continue

        qty = float(inv.get("quantity") or 0.0)
        price = float(inv.get("unit_price") or 0.0)
        tax_pct = float(inv.get("tax_pct") or 0.0)
        line_total = float(inv.get("line_total") or (qty * price * (1.0 + tax_pct / 100.0)))

        entry = billed_by_key.setdefault(
            key,
            {
                "billed_qty": 0.0,
                "billed_total": 0.0,
                "invoice_numbers": [],
                "vendor_id": str(inv.get("vendor_id") or ""),
                "currency": str(inv.get("currency") or "INR").strip().upper(),
            },
        )
        entry["billed_qty"] += qty
        entry["billed_total"] += line_total
        inv_num = str(inv.get("invoice_number") or "").strip()
        if inv_num and inv_num not in entry["invoice_numbers"]:
            entry["invoice_numbers"].append(inv_num)

    findings: list[Finding] = []
    for key in sorted(billed_by_key):
        grn_info = grn_by_key[key]
        billed_info = billed_by_key[key]
        billed_qty = billed_info["billed_qty"]
        grn_qty = grn_info["total_qty"]

        if billed_qty <= grn_qty + 1e-6:
            continue

        excess_qty = billed_qty - grn_qty
        unit_gross = (billed_info["billed_total"] / billed_qty) if billed_qty > 0 else 0.0
        amount_at_risk = round(excess_qty * unit_gross, 2)
        po_id = grn_info["po_id"]
        display_item = grn_info["display_item"]
        inv_nums = billed_info["invoice_numbers"]
        grn_ids = grn_info["grn_ids"]
        currency = billed_info["currency"]

        evidence = [
            EvidenceRef("goods_receipts", grn_ids[0] if grn_ids else po_id, grn_info["qty_field"], f"{grn_qty:g}"),
            EvidenceRef("invoices", ", ".join(inv_nums) if inv_nums else po_id, "billed_qty", f"{billed_qty:g}"),
            EvidenceRef("invoices", ", ".join(inv_nums) if inv_nums else po_id, "excess_qty", f"{excess_qty:g}"),
        ]

        findings.append(
            Finding(
                rule_id="R7",
                title=f"3-way GRN quantity mismatch on {po_id} ({display_item})",
                severity="high",
                amount_at_risk=amount_at_risk,
                currency=currency,
                entity_refs={
                    "po_id": po_id,
                    "vendor_id": billed_info["vendor_id"],
                    "invoice_numbers": inv_nums,
                    "grn_ids": grn_ids,
                },
                evidence=evidence,
                confidence=0.95,
                recommended_action="HOLD_PAYMENT",
                summary=(
                    f"Billed quantity ({billed_qty:g}) for '{display_item}' on {po_id} "
                    f"exceeds GRN {grn_info['qty_field']} ({grn_qty:g}) by {excess_qty:g} units. "
                    f"Exposure: {amount_at_risk:,.2f} {currency}."
                ),
                proof_trail={
                    "math": {
                        "po_id": po_id,
                        "item": display_item,
                        "billed_qty": round(billed_qty, 4),
                        "grn_qty": round(grn_qty, 4),
                        "qty_field": grn_info["qty_field"],
                        "excess_qty": round(excess_qty, 4),
                        "unit_gross_amount": round(unit_gross, 4),
                        "amount_at_risk": amount_at_risk,
                    }
                },
            )
        )

    return findings

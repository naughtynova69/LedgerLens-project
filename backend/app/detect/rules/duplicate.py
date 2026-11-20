"""R1 — Duplicate & near-duplicate invoice detector (deterministic core).

Spec: docs/04_DETECTION_RULES.md §R1.

Catches the 61% non-identical invoice number problem using:
1. Canonicalized alphanumeric invoice-number similarity + raw SequenceMatcher ratio
2. Same vendor + near-identical grand total (+-0.5%) + line-item Jaccard similarity + date window
3. Same vendor + same PO + same item + same quantity billed across distinct non-credited invoices
"""
from __future__ import annotations

from datetime import date
from difflib import SequenceMatcher
import re

from ..registry import DetectionContext, register
from ..types import EvidenceRef, Finding

MAX_AMOUNT_DRIFT = 0.005      # grand totals may differ by at most 0.5%
MIN_LINE_SIMILARITY = 0.8     # Jaccard over (item, qty, unit_price) tuples
MIN_NUMBER_SIMILARITY = 0.6   # SequenceMatcher ratio on invoice_number
MAX_DATE_GAP_DAYS = 30


def _canon_inv_num(num: str) -> str:
    return re.sub(r"[^A-Z0-9]", "", str(num or "").upper())


def _group_by_invoice(line_rows: list[dict]) -> dict[str, dict]:
    """Fold invoice-line rows into one record per invoice_number."""
    invoices: dict[str, dict] = {}
    for row in line_rows:
        number = str(row.get("invoice_number", ""))
        inv = invoices.setdefault(number, {
            "invoice_number": number,
            "canon_number": _canon_inv_num(number),
            "vendor_id": str(row.get("vendor_id", "")),
            "invoice_date": str(row.get("invoice_date", "")),
            "po_id": str(row.get("po_id") or "").strip(),
            "currency": str(row.get("currency", "INR")),
            "status": str(row.get("status", "unpaid")).lower(),
            "lines": [],
            "line_nos": [],
            "po_item_qty": set(),
            "grand_total": 0.0,
        })
        item_norm = " ".join(str(row.get("item", "")).lower().split())
        qty = float(row.get("quantity", 0) or 0)
        price = round(float(row.get("unit_price", 0) or 0), 2)
        inv["lines"].append((item_norm, qty, price))
        inv["line_nos"].append(int(row.get("line_no") or 1))
        if inv["po_id"]:
            inv["po_item_qty"].add((inv["po_id"], item_norm, qty))
        inv["grand_total"] += float(row.get("line_total", 0) or 0)
    return invoices


def _line_similarity(a: dict, b: dict) -> float:
    set_a, set_b = set(a["lines"]), set(b["lines"])
    if not set_a or not set_b:
        return 0.0
    return len(set_a & set_b) / len(set_a | set_b)


def _date_gap(iso_a: str, iso_b: str) -> int | None:
    try:
        return abs((date.fromisoformat(iso_a) - date.fromisoformat(iso_b)).days)
    except ValueError:
        return None


def _payments_for(payments: list[dict], invoice_number: str) -> list[dict]:
    return [p for p in payments if str(p.get("invoice_number", "")) == invoice_number]


@register("R1")
def detect_duplicates(ctx: DetectionContext) -> list[Finding]:
    findings: list[Finding] = []
    policy = ctx.get("policy", {}) if isinstance(ctx, dict) else (getattr(ctx, "policy", None) or {})
    raw_drift_pct = policy.get("r1_max_amount_drift_pct")
    max_amount_drift = float(raw_drift_pct) / 100.0 if raw_drift_pct is not None else MAX_AMOUNT_DRIFT
    raw_gap_days = policy.get("r1_max_date_gap_days")
    max_date_gap_days = int(raw_gap_days) if raw_gap_days is not None else MAX_DATE_GAP_DAYS

    by_vendor: dict[str, list[dict]] = {}
    for inv in _group_by_invoice(ctx.invoices).values():
        by_vendor.setdefault(inv["vendor_id"], []).append(inv)

    for vendor_id, group in by_vendor.items():
        for i in range(len(group)):
            for j in range(i + 1, len(group)):
                a, b = group[i], group[j]

                # Credit note guard: legitimate revised invoice
                if a["status"] == "credited" or b["status"] == "credited":
                    continue

                total_a, total_b = a["grand_total"], b["grand_total"]
                if total_a <= 0 or total_b <= 0:
                    continue

                amount_drift = abs(total_a - total_b) / max(total_a, total_b)
                amount_ok = amount_drift <= max_amount_drift
                line_sim = _line_similarity(a, b)

                raw_num_sim = SequenceMatcher(None, a["invoice_number"], b["invoice_number"]).ratio()
                canon_num_sim = SequenceMatcher(None, a["canon_number"], b["canon_number"]).ratio()
                num_sim = max(raw_num_sim, canon_num_sim)
                gap_days = _date_gap(a["invoice_date"], b["invoice_date"])

                same_po_item_qty = bool(a["po_item_qty"] & b["po_item_qty"])
                standard_dup = (
                    amount_ok
                    and line_sim >= MIN_LINE_SIMILARITY
                    and (num_sim >= MIN_NUMBER_SIMILARITY or (gap_days is not None and gap_days <= max_date_gap_days))
                )
                po_double_bill = same_po_item_qty and amount_ok and line_sim >= MIN_LINE_SIMILARITY

                if not (standard_dup or po_double_bill):
                    continue

                both_paid = a["status"] == "paid" and b["status"] == "paid"
                confidence = round(0.5 * line_sim + 0.3 + 0.2 * num_sim, 2)
                recommended_action = "REQUEST_CREDIT_NOTE" if both_paid else "HOLD_PAYMENT"

                evidence = [
                    EvidenceRef("invoices", a["invoice_number"], "line_total", f"{total_a:,.2f} {a['currency']}"),
                    EvidenceRef("invoices", b["invoice_number"], "line_total", f"{total_b:,.2f} {b['currency']}"),
                ]
                payment_ids: list[str] = []
                for inv in (a, b):
                    for pay in _payments_for(ctx.payments, inv["invoice_number"]):
                        payment_ids.append(str(pay.get("payment_id", "")))
                        evidence.append(EvidenceRef(
                            "payments", str(pay.get("payment_id", "")),
                            "payment_date", str(pay.get("payment_date", "")),
                        ))

                gap_text = f"{gap_days}-day gap" if gap_days is not None else "unknown date gap"
                po_ref = a["po_id"] if a["po_id"] == b["po_id"] else (a["po_id"] or b["po_id"])
                findings.append(Finding(
                    rule_id="R1",
                    title="Possible duplicate payment",
                    severity="critical" if both_paid else "high",
                    amount_at_risk=round(min(total_a, total_b), 2),
                    currency=a["currency"],
                    entity_refs={
                        "vendor_id": vendor_id,
                        "invoice_numbers": [a["invoice_number"], b["invoice_number"]],
                        "line_no": a["line_nos"][0] if a["line_nos"] else 1,
                        "po_id": po_ref,
                        "payment_ids": payment_ids,
                    },
                    evidence=evidence,
                    summary=(
                        f"Same vendor ({vendor_id}), same amount "
                        f"({total_a:,.2f} {a['currency']}), {gap_text}, "
                        f"{line_sim:.0%} line-item similarity; invoice numbers "
                        f"'{a['invoice_number']}' vs '{b['invoice_number']}' "
                        f"(similarity {num_sim:.0%})."
                    ),
                    confidence=confidence,
                    recommended_action=recommended_action,
                    proof_trail={
                        "math": {
                            "invoice_a_total": round(total_a, 2),
                            "invoice_b_total": round(total_b, 2),
                            "amount_drift_pct": round(amount_drift * 100.0, 4),
                            "line_similarity": round(line_sim, 4),
                            "invoice_number_similarity": round(num_sim, 4),
                            "date_gap_days": gap_days,
                            "same_po_item_qty": same_po_item_qty,
                            "both_paid": both_paid,
                        }
                    },
                ))

    return findings

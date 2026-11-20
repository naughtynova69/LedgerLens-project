"""R1 — Duplicate & near-duplicate invoice detector (reference implementation).

Spec: docs/04_DETECTION_RULES.md §R1.

Why it fires (this text feeds the explanation stage):
    Same vendor + same grand total (+-0.5%) + near-identical line items,
    with a similar invoice number or a short date gap, is the classic
    resubmitted-invoice pattern. Research found 61% of paid duplicates
    carry a NON-identical invoice number, so exact-match dedup is not enough.

This module is the reference for implementing R2–R5: pure functions,
EvidenceRef-rich findings, confidence computed here — never by the LLM.
"""
from __future__ import annotations

from datetime import date
from difflib import SequenceMatcher

from ..registry import DetectionContext, register
from ..types import EvidenceRef, Finding

MAX_AMOUNT_DRIFT = 0.005      # grand totals may differ by at most 0.5%
MIN_LINE_SIMILARITY = 0.8     # Jaccard over (item, qty, unit_price) tuples
MIN_NUMBER_SIMILARITY = 0.6   # SequenceMatcher ratio on invoice_number
MAX_DATE_GAP_DAYS = 30


def _group_by_invoice(line_rows: list[dict]) -> dict[str, dict]:
    """Fold invoice-line rows into one record per invoice_number."""
    invoices: dict[str, dict] = {}
    for row in line_rows:
        number = str(row.get("invoice_number", ""))
        inv = invoices.setdefault(number, {
            "invoice_number": number,
            "vendor_id": str(row.get("vendor_id", "")),
            "invoice_date": str(row.get("invoice_date", "")),
            "currency": str(row.get("currency", "INR")),
            "status": str(row.get("status", "unpaid")),
            "lines": [],
            "grand_total": 0.0,
        })
        inv["lines"].append((
            str(row.get("item", "")).lower().strip(),
            float(row.get("quantity", 0)),
            round(float(row.get("unit_price", 0)), 2),
        ))
        inv["grand_total"] += float(row.get("line_total", 0))
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

    by_vendor: dict[str, list[dict]] = {}
    for inv in _group_by_invoice(ctx.invoices).values():
        by_vendor.setdefault(inv["vendor_id"], []).append(inv)

    for vendor_id, group in by_vendor.items():
        for i in range(len(group)):
            for j in range(i + 1, len(group)):
                a, b = group[i], group[j]

                # A credit note against one of them means a legitimate revised invoice.
                if a["status"] == "credited" or b["status"] == "credited":
                    continue

                total_a, total_b = a["grand_total"], b["grand_total"]
                if total_a <= 0 or total_b <= 0:
                    continue
                if abs(total_a - total_b) / max(total_a, total_b) > MAX_AMOUNT_DRIFT:
                    continue

                line_sim = _line_similarity(a, b)
                if line_sim < MIN_LINE_SIMILARITY:
                    continue

                num_sim = SequenceMatcher(
                    None, a["invoice_number"], b["invoice_number"]).ratio()
                gap_days = _date_gap(a["invoice_date"], b["invoice_date"])
                if num_sim < MIN_NUMBER_SIMILARITY and (
                        gap_days is None or gap_days > MAX_DATE_GAP_DAYS):
                    continue

                both_paid = a["status"] == "paid" and b["status"] == "paid"
                confidence = round(0.5 * line_sim + 0.3 + 0.2 * num_sim, 2)

                evidence = [
                    EvidenceRef("invoices", a["invoice_number"], "line_total",
                                f"{total_a:,.2f} {a['currency']}"),
                    EvidenceRef("invoices", b["invoice_number"], "line_total",
                                f"{total_b:,.2f} {b['currency']}"),
                ]
                payment_ids: list[str] = []
                for inv in (a, b):
                    for pay in _payments_for(ctx.payments, inv["invoice_number"]):
                        payment_ids.append(str(pay.get("payment_id", "")))
                        evidence.append(EvidenceRef(
                            "payments", str(pay.get("payment_id", "")),
                            "payment_date", str(pay.get("payment_date", ""))))

                gap_text = f"{gap_days}-day gap" if gap_days is not None else "unknown date gap"
                findings.append(Finding(
                    rule_id="R1",
                    title="Possible duplicate payment",
                    severity="critical" if both_paid else "high",
                    amount_at_risk=round(min(total_a, total_b), 2),
                    currency=a["currency"],
                    entity_refs={
                        "vendor_id": vendor_id,
                        "invoice_numbers": [a["invoice_number"], b["invoice_number"]],
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
                ))

    return findings

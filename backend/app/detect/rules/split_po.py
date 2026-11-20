"""R6 — Split-PO / Approval-Limit Bypass detector (deterministic core).

Groups POs (or invoices without a PO) by vendor_id within `r6_split_window_days`
(default 7) where >= 2 records each fall just below `r6_approval_limit_inr`
(default 50000.0, >= 75% and < 100% of limit) while their combined sum >= limit.
"""
from __future__ import annotations

from datetime import date

from ..registry import DEFAULT_FX_RATES, DetectionContext, register
from ..types import EvidenceRef, Finding

DEFAULT_SPLIT_WINDOW_DAYS = 7
DEFAULT_APPROVAL_LIMIT_INR = 50000.0
MIN_SPLIT_RATIO = 0.75


def _parse_iso_date(raw: object) -> date | None:
    text = str(raw or "").strip()
    if not text:
        return None
    try:
        return date.fromisoformat(text[:10])
    except ValueError:
        return None


def _effective_fx_rates(policy: dict) -> dict[str, float]:
    rates = dict(DEFAULT_FX_RATES)
    override = policy.get("fx_rates")
    if isinstance(override, dict):
        for curr, rate in override.items():
            try:
                val = float(rate)
            except (TypeError, ValueError):
                continue
            if val > 0:
                rates[str(curr).strip().upper()] = val
    return rates


def _aggregate_pos(purchase_orders: list[dict], fx_rates: dict[str, float]) -> dict[str, list[dict]]:
    """Aggregate purchase_orders by po_id and group by vendor_id."""
    by_po: dict[str, dict] = {}
    for row in purchase_orders:
        po_id = str(row.get("po_id") or "").strip()
        if not po_id:
            continue
        status = str(row.get("status") or "").strip().lower()
        if status == "cancelled":
            continue
        vendor_id = str(row.get("vendor_id") or "").strip()
        if not vendor_id:
            continue
        curr = str(row.get("currency") or "INR").strip().upper()
        qty = float(row.get("quantity") or 0.0)
        price = float(row.get("unit_price") or 0.0)
        line_amt = float(row.get("line_total") or (qty * price))
        rec_date = _parse_iso_date(row.get("order_date") or row.get("expected_delivery"))

        rec = by_po.setdefault(
            po_id,
            {
                "source": "purchase_orders",
                "record_id": po_id,
                "vendor_id": vendor_id,
                "currency": curr,
                "amount_orig": 0.0,
                "date": rec_date,
                "date_str": str(row.get("order_date") or row.get("expected_delivery") or ""),
            },
        )
        rec["amount_orig"] += line_amt
        if rec["date"] is None and rec_date is not None:
            rec["date"] = rec_date
            rec["date_str"] = str(row.get("order_date") or row.get("expected_delivery") or "")

    by_vendor: dict[str, list[dict]] = {}
    for rec in by_po.values():
        rate = fx_rates.get(rec["currency"], 1.0)
        rec["amount_inr"] = round(rec["amount_orig"] * rate, 2)
        by_vendor.setdefault(rec["vendor_id"], []).append(rec)
    return by_vendor


def _aggregate_no_po_invoices(invoices: list[dict], fx_rates: dict[str, float]) -> dict[str, list[dict]]:
    """Aggregate invoices without a po_id by invoice_number and group by vendor_id."""
    by_inv: dict[str, dict] = {}
    for row in invoices:
        if str(row.get("po_id") or "").strip():
            continue
        status = str(row.get("status") or "").strip().lower()
        if status == "credited":
            continue
        inv_num = str(row.get("invoice_number") or "").strip()
        vendor_id = str(row.get("vendor_id") or "").strip()
        if not inv_num or not vendor_id:
            continue
        curr = str(row.get("currency") or "INR").strip().upper()
        qty = float(row.get("quantity") or 0.0)
        price = float(row.get("unit_price") or 0.0)
        tax_pct = float(row.get("tax_pct") or 0.0)
        line_amt = float(row.get("line_total") or (qty * price * (1.0 + tax_pct / 100.0)))
        rec_date = _parse_iso_date(row.get("invoice_date"))

        rec = by_inv.setdefault(
            inv_num,
            {
                "source": "invoices",
                "record_id": inv_num,
                "vendor_id": vendor_id,
                "currency": curr,
                "amount_orig": 0.0,
                "date": rec_date,
                "date_str": str(row.get("invoice_date") or ""),
            },
        )
        rec["amount_orig"] += line_amt
        if rec["date"] is None and rec_date is not None:
            rec["date"] = rec_date
            rec["date_str"] = str(row.get("invoice_date") or "")

    by_vendor: dict[str, list[dict]] = {}
    for rec in by_inv.values():
        rate = fx_rates.get(rec["currency"], 1.0)
        rec["amount_inr"] = round(rec["amount_orig"] * rate, 2)
        by_vendor.setdefault(rec["vendor_id"], []).append(rec)
    return by_vendor


def _find_split_clusters(
    records: list[dict],
    window_days: int,
    limit_inr: float,
) -> list[list[dict]]:
    """Return non-overlapping clusters of >=2 records near the limit whose sum >= limit."""
    min_inr = MIN_SPLIT_RATIO * limit_inr
    candidates = [
        r for r in records
        if r["date"] is not None and min_inr <= r["amount_inr"] < limit_inr
    ]
    candidates.sort(key=lambda r: (r["date"], r["record_id"]))

    clusters: list[list[dict]] = []
    i = 0
    n = len(candidates)
    while i < n:
        j = i + 1
        while j < n and (candidates[j]["date"] - candidates[i]["date"]).days <= window_days:
            j += 1
        cluster = candidates[i:j]
        if len(cluster) >= 2 and sum(r["amount_inr"] for r in cluster) >= limit_inr:
            clusters.append(cluster)
            i = j
        else:
            i += 1
    return clusters


@register("R6")
def detect_split_po_bypass(ctx: DetectionContext) -> list[Finding]:
    """Detect split POs or non-PO invoices structured just below the approval limit."""
    policy = ctx.get("policy", {}) if isinstance(ctx, dict) else (getattr(ctx, "policy", None) or {})
    raw_window = policy.get("r6_split_window_days")
    window_days = int(raw_window) if raw_window is not None else DEFAULT_SPLIT_WINDOW_DAYS
    raw_limit = policy.get("r6_approval_limit_inr")
    limit_inr = float(raw_limit) if raw_limit is not None else DEFAULT_APPROVAL_LIMIT_INR

    if limit_inr <= 0 or window_days < 0:
        return []

    fx_rates = _effective_fx_rates(policy)
    purchase_orders = (
        ctx.get("purchase_orders", [])
        if isinstance(ctx, dict)
        else (getattr(ctx, "purchase_orders", []) or [])
    )
    invoices = (
        ctx.get("invoices", [])
        if isinstance(ctx, dict)
        else (getattr(ctx, "invoices", []) or [])
    )

    findings: list[Finding] = []
    grouped_sources = [
        ("purchase_orders", _aggregate_pos(purchase_orders, fx_rates)),
        ("invoices", _aggregate_no_po_invoices(invoices, fx_rates)),
    ]

    for source_kind, by_vendor in grouped_sources:
        for vendor_id in sorted(by_vendor):
            for cluster in _find_split_clusters(by_vendor[vendor_id], window_days, limit_inr):
                combined_inr = round(sum(r["amount_inr"] for r in cluster), 2)
                span_days = (cluster[-1]["date"] - cluster[0]["date"]).days
                record_ids = [r["record_id"] for r in cluster]

                entity_refs: dict = {"vendor_id": vendor_id}
                if source_kind == "purchase_orders":
                    entity_refs["po_ids"] = record_ids
                    entity_refs["po_id"] = record_ids[0]
                    label = "purchase orders"
                else:
                    entity_refs["invoice_numbers"] = record_ids
                    label = "non-PO invoices"

                evidence: list[EvidenceRef] = []
                for r in cluster:
                    evidence.append(
                        EvidenceRef(r["source"], r["record_id"], "total_inr", f"{r['amount_inr']:,.2f} INR")
                    )
                    evidence.append(
                        EvidenceRef(r["source"], r["record_id"], "date", r["date_str"])
                    )

                findings.append(
                    Finding(
                        rule_id="R6",
                        title=f"Split-PO / approval-limit bypass suspected for {vendor_id}",
                        severity="high",
                        amount_at_risk=combined_inr,
                        currency="INR",
                        entity_refs=entity_refs,
                        evidence=evidence,
                        confidence=0.90,
                        recommended_action="HOLD_PAYMENT",
                        summary=(
                            f"Vendor {vendor_id} has {len(cluster)} {label} ({', '.join(record_ids)}) "
                            f"within {span_days} days, each below {limit_inr:,.2f} INR "
                            f"but totaling {combined_inr:,.2f} INR."
                        ),
                        proof_trail={
                            "math": {
                                "vendor_id": vendor_id,
                                "source": source_kind,
                                "record_count": len(cluster),
                                "record_ids": record_ids,
                                "record_amounts_inr": [r["amount_inr"] for r in cluster],
                                "combined_amount_inr": combined_inr,
                                "approval_limit_inr": limit_inr,
                                "min_split_threshold_inr": round(MIN_SPLIT_RATIO * limit_inr, 2),
                                "split_window_days": window_days,
                                "window_span_days": span_days,
                            }
                        },
                    )
                )

    return findings

"""FX-normalized spend/leakage summaries and RFC-4180 CSV export for findings."""
from __future__ import annotations

import csv
import io
import json
import sqlite3
from typing import Any

from ..normalize import REFERENCE_FX_RATES

_CSV_COLUMNS = [
    "finding_id",
    "rule_id",
    "severity",
    "status",
    "vendor_id",
    "invoice_numbers",
    "po_id",
    "contract_id",
    "amount_at_risk",
    "currency",
    "inr_equivalent",
    "recommended_action",
    "title",
    "summary",
]


def _normalize_currency_code(currency: str | None) -> str:
    return (currency or "INR").strip().upper() or "INR"


def _to_inr(amount: float, currency: str) -> float:
    """Convert an amount in `currency` to INR using REFERENCE_FX_RATES."""
    curr = _normalize_currency_code(currency)
    rate = REFERENCE_FX_RATES.get(curr, 1.0)
    return round(float(amount or 0.0) * rate, 2)


def compute_fx_normalized_totals(findings: list[dict], invoices: list[dict]) -> dict:
    """Compute FX-normalized spend, exposure, recovery, and per-currency breakdowns in INR."""
    total_audited_inr = round(
        sum(
            _to_inr(float(inv.get("line_total") or 0.0), str(inv.get("currency") or "INR"))
            for inv in invoices
        ),
        2,
    )

    total_at_risk_inr = 0.0
    open_at_risk_inr = 0.0
    recovered_inr = 0.0
    by_currency: dict[str, dict[str, Any]] = {}

    for finding in findings:
        curr = _normalize_currency_code(str(finding.get("currency") or "INR"))
        native_amount = float(finding.get("amount_at_risk") or 0.0)
        inr_amount = _to_inr(native_amount, curr)
        status = str(finding.get("status") or "").strip().lower()

        total_at_risk_inr += inr_amount
        if status == "open":
            open_at_risk_inr += inr_amount
        elif status in ("rejected", "recovery"):
            recovered_inr += inr_amount

        bucket = by_currency.setdefault(
            curr,
            {"count": 0, "native_amount": 0.0, "inr_equivalent": 0.0},
        )
        bucket["count"] += 1
        bucket["native_amount"] = round(bucket["native_amount"] + native_amount, 2)
        bucket["inr_equivalent"] = round(bucket["inr_equivalent"] + inr_amount, 2)

    total_at_risk_inr = round(total_at_risk_inr, 2)
    open_at_risk_inr = round(open_at_risk_inr, 2)
    recovered_inr = round(recovered_inr, 2)
    leakage_pct_of_spend = (
        0.0
        if total_audited_inr <= 0
        else round((total_at_risk_inr / total_audited_inr) * 100.0, 2)
    )

    return {
        "total_audited_inr": total_audited_inr,
        "total_at_risk_inr": total_at_risk_inr,
        "open_at_risk_inr": open_at_risk_inr,
        "recovered_inr": recovered_inr,
        "leakage_pct_of_spend": leakage_pct_of_spend,
        "by_currency": by_currency,
    }


def _parse_entity_refs(raw_refs: Any) -> dict[str, Any]:
    if isinstance(raw_refs, dict):
        return raw_refs
    try:
        parsed = json.loads(raw_refs or "{}")
        return parsed if isinstance(parsed, dict) else {}
    except (TypeError, ValueError):
        return {}


def _format_invoice_numbers(value: Any) -> str:
    if isinstance(value, list):
        return "; ".join(str(item) for item in value if item is not None)
    if value is None:
        return ""
    return str(value)


def export_findings_csv(
    conn: sqlite3.Connection,
    status: str | None = None,
    rule_id: str | None = None,
) -> str:
    """Export findings ordered by amount_at_risk DESC as an RFC-4180 CSV string."""
    query = (
        "SELECT finding_id, rule_id, severity, status, amount_at_risk, currency, "
        "entity_refs, recommended_action, title, summary FROM findings WHERE 1=1"
    )
    params: list[Any] = []
    if status and status != "all":
        query += " AND status = ?"
        params.append(status)
    if rule_id and rule_id != "all":
        query += " AND rule_id = ?"
        params.append(rule_id)
    query += " ORDER BY amount_at_risk DESC"

    cur = conn.execute(query, params)
    col_names = [desc[0] for desc in cur.description]
    rows = [dict(zip(col_names, row)) for row in cur.fetchall()]

    buf = io.StringIO(newline="")
    writer = csv.DictWriter(buf, fieldnames=_CSV_COLUMNS, lineterminator="\r\n")
    writer.writeheader()

    for row in rows:
        refs = _parse_entity_refs(row.get("entity_refs"))
        curr = _normalize_currency_code(str(row.get("currency") or "INR"))
        amount = round(float(row.get("amount_at_risk") or 0.0), 2)
        writer.writerow(
            {
                "finding_id": row.get("finding_id") or "",
                "rule_id": row.get("rule_id") or "",
                "severity": row.get("severity") or "",
                "status": row.get("status") or "",
                "vendor_id": refs.get("vendor_id") or "",
                "invoice_numbers": _format_invoice_numbers(refs.get("invoice_numbers")),
                "po_id": refs.get("po_id") or "",
                "contract_id": refs.get("contract_id") or "",
                "amount_at_risk": amount,
                "currency": curr,
                "inr_equivalent": _to_inr(amount, curr),
                "recommended_action": row.get("recommended_action") or "",
                "title": row.get("title") or "",
                "summary": row.get("summary") or "",
            }
        )

    return buf.getvalue()

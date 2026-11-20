"""R8 — Cross-entity duplicate & threshold-splitting detector (deterministic core).

Spec: master-prompt §4 R8 (renumbered from R6 after main added tabular R6/R7). The Cypher layer (app.graph.queries) matches the
multi-hop structural pattern — two DIFFERENT vendor entities converging on the
same BankAccount or TaxIdentifier node with near-identical invoices — which
tabular R1 cannot see because it groups strictly by vendor_id. This module
re-verifies the deterministic math (amount drift, date windows) in pure Python
and emits the Finding with the serialized proof_subgraph.

Confidence values are rule constants; no LLM ever produces them.
"""
from __future__ import annotations

from datetime import date

from ..registry import DetectionContext, register
from ..types import EvidenceRef, Finding

MAX_AMOUNT_DRIFT = 0.005      # mirrors R1's grand-total drift tolerance
MAX_DATE_GAP_DAYS = 30
SPLIT_WINDOW_DAYS = 7


def _date_gap(iso_a: str, iso_b: str) -> int | None:
    try:
        return abs((date.fromisoformat(str(iso_a or "")[:10])
                    - date.fromisoformat(str(iso_b or "")[:10])).days)
    except ValueError:
        return None


def _mask(value: str) -> str:
    return f"••••{value[-4:]}" if len(value) >= 4 else value


@register("R8")
def detect_cross_entity_duplicates(ctx: DetectionContext) -> list[Finding]:
    findings: list[Finding] = []
    evidence_map = getattr(ctx, "graph_evidence", None) or {}

    for row in evidence_map.get("cross_entity_duplicates", []):
        total_a, total_b = (float(row["grand_totals"][0]), float(row["grand_totals"][1]))
        gap_days = _date_gap(row["invoice_dates"][0], row["invoice_dates"][1])
        if gap_days is None or gap_days > MAX_DATE_GAP_DAYS:
            continue
        if total_a <= 0 or total_b <= 0:
            continue
        drift = abs(total_a - total_b) / max(total_a, total_b)
        if drift > MAX_AMOUNT_DRIFT:
            continue

        amount_at_risk = round(min(total_a, total_b), 2)
        shared_via = str(row.get("shared_via") or "bank")
        shared_ref = str(row.get("shared_ref") or "")
        vendor_a, vendor_b = row["vendor_ids"]
        invoice_numbers = row["invoice_numbers"]
        batch_ids = [str(b) for b in row.get("batch_ids", []) if b]

        findings.append(Finding(
            rule_id="R8",
            title="Cross-entity duplicate billing via shared bank/tax identifier",
            severity="critical" if str(row.get("status_a")) == "paid" else "high",
            amount_at_risk=amount_at_risk,
            currency=str(row.get("currency") or "INR"),
            entity_refs={
                "vendor_ids": [vendor_a, vendor_b],
                "invoice_numbers": list(invoice_numbers),
                "shared_via": shared_via,
                "shared_ref": shared_ref,
                "date_gap_days": gap_days,
            },
            evidence=[
                EvidenceRef("invoices", invoice_numbers[0], "grand_total",
                            f"{total_a:,.2f} {row.get('currency') or 'INR'}"),
                EvidenceRef("invoices", invoice_numbers[1], "grand_total",
                            f"{total_b:,.2f} {row.get('currency') or 'INR'}"),
                EvidenceRef("graph", shared_ref, f"shared_{shared_via}", _mask(shared_ref)),
            ],
            confidence=0.92,
            recommended_action="HOLD_PAYMENT",
            summary=(
                f"Vendors {vendor_a} and {vendor_b} (distinct entities) billed "
                f"near-identical amounts ({total_a:,.2f} vs {total_b:,.2f} "
                f"{row.get('currency') or 'INR'}, drift {drift:.2%}, {gap_days}-day gap) "
                f"into the same {shared_via} {_mask(shared_ref)} — a pattern tabular "
                f"same-vendor duplicate checks cannot see."
            ),
            proof_trail={
                "math": {
                    "grand_total_a": round(total_a, 2),
                    "grand_total_b": round(total_b, 2),
                    "amount_drift_pct": round(drift * 100.0, 4),
                    "date_gap_days": gap_days,
                    "shared_via": shared_via,
                    "amount_at_risk": amount_at_risk,
                },
                "proof_subgraph": row.get("proof_subgraph") or {},
            },
        ))

    for row in evidence_map.get("split_invoices", []):
        total_a, total_b = (float(row["grand_totals"][0]), float(row["grand_totals"][1]))
        limit = float(row.get("approval_limit") or 0.0)
        gap_days = _date_gap(row["invoice_dates"][0], row["invoice_dates"][1])
        if gap_days is None or gap_days > SPLIT_WINDOW_DAYS:
            continue
        if limit <= 0 or total_a <= 0 or total_b <= 0:
            continue
        combined = total_a + total_b
        if combined <= limit:
            continue

        amount_at_risk = round(combined - limit, 2)
        shared_via = str(row.get("shared_via") or "bank")
        shared_ref = str(row.get("shared_ref") or "")
        approver_id = str(row.get("approver_id") or "")

        findings.append(Finding(
            rule_id="R8",
            title="Approval-threshold splitting across shared bank/tax identifier",
            severity="high",
            amount_at_risk=amount_at_risk,
            currency=str(row.get("currency") or "INR"),
            entity_refs={
                "vendor_ids": list(row["vendor_ids"]),
                "invoice_numbers": list(row["invoice_numbers"]),
                "approver_id": approver_id,
                "shared_via": shared_via,
                "shared_ref": shared_ref,
                "date_gap_days": gap_days,
            },
            evidence=[
                EvidenceRef("invoices", row["invoice_numbers"][0], "grand_total",
                            f"{total_a:,.2f} {row.get('currency') or 'INR'}"),
                EvidenceRef("invoices", row["invoice_numbers"][1], "grand_total",
                            f"{total_b:,.2f} {row.get('currency') or 'INR'}"),
                EvidenceRef("graph", approver_id, "approval_limit", f"{limit:,.2f}"),
                EvidenceRef("graph", shared_ref, f"shared_{shared_via}", _mask(shared_ref)),
            ],
            confidence=0.88,
            recommended_action="HOLD_PAYMENT",
            summary=(
                f"Invoices {row['invoice_numbers'][0]} and {row['invoice_numbers'][1]} "
                f"from different vendors sharing {shared_via} {_mask(shared_ref)} were "
                f"approved by {approver_id} within {gap_days} day(s), each just below the "
                f"{limit:,.2f} approval limit (combined {combined:,.2f} exceeds it by "
                f"{amount_at_risk:,.2f} {row.get('currency') or 'INR'})."
            ),
            proof_trail={
                "math": {
                    "grand_total_a": round(total_a, 2),
                    "grand_total_b": round(total_b, 2),
                    "approval_limit": round(limit, 2),
                    "combined_total": round(combined, 2),
                    "date_gap_days": gap_days,
                    "amount_at_risk": amount_at_risk,
                },
                "proof_subgraph": row.get("proof_subgraph") or {},
            },
        ))

    return findings

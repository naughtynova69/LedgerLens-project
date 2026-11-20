"""R9 — Approver-vendor collusion & conflict-of-interest detector (deterministic core).

Spec: master-prompt §4 R9 (renumbered from R7 after main added tabular R6/R7). The Cypher layer matches the multi-hop pattern —
an approver whose APPROVED_INVOICE edge leads to a vendor sharing the approver's
BankAccount, Address, or normalized phone — then this module re-verifies the
deterministic amounts and emits CRITICAL findings with the proof subgraph.

Confidence values are rule constants; no LLM ever produces them.
"""
from __future__ import annotations

from ..registry import DetectionContext, register
from ..types import EvidenceRef, Finding


def _mask(value: str) -> str:
    return f"••••{value[-4:]}" if len(value) >= 4 else value


@register("R9")
def detect_approver_vendor_collusion(ctx: DetectionContext) -> list[Finding]:
    findings: list[Finding] = []
    evidence_map = getattr(ctx, "graph_evidence", None) or {}

    for row in evidence_map.get("collusion", []):
        invoice_total = float(row.get("invoice_total") or 0.0)
        if invoice_total <= 0:
            continue

        vector = str(row.get("vector") or "")
        shared_ref = str(row.get("shared_ref") or "")
        approver_id = str(row.get("approver_id") or "")
        vendor_id = str(row.get("vendor_id") or "")
        invoice_number = str(row.get("invoice_number") or "")

        findings.append(Finding(
            rule_id="R9",
            title="Approver-vendor conflict of interest via shared personal infrastructure",
            severity="critical",
            amount_at_risk=round(invoice_total, 2),
            currency=str(row.get("currency") or "INR"),
            entity_refs={
                "approver_id": approver_id,
                "vendor_id": vendor_id,
                "invoice_numbers": [invoice_number],
                "shared_via": vector,
                "shared_ref": shared_ref,
            },
            evidence=[
                EvidenceRef("invoices", invoice_number, "grand_total",
                            f"{invoice_total:,.2f} {row.get('currency') or 'INR'}"),
                EvidenceRef("graph", approver_id, f"shared_{vector}", _mask(shared_ref)),
                EvidenceRef("graph", vendor_id, f"shared_{vector}", _mask(shared_ref)),
            ],
            confidence=0.9,
            recommended_action="HOLD_PAYMENT_AND_ESCALATE_INTERNAL_AUDIT",
            summary=(
                f"Approver {approver_id} approved invoice {invoice_number} from vendor "
                f"{vendor_id}, and both share the same {vector} {_mask(shared_ref)} — "
                f"a conflict-of-interest pattern invisible to tabular rules."
            ),
            proof_trail={
                "math": {
                    "invoice_total": round(invoice_total, 2),
                    "shared_via": vector,
                    "approver_id": approver_id,
                    "vendor_id": vendor_id,
                    "amount_at_risk": round(invoice_total, 2),
                },
                "proof_subgraph": row.get("proof_subgraph") or {},
            },
        ))

    return findings

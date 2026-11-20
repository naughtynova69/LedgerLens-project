"""R5 — Cancelled-service leakage detector (deterministic core).

Spec: docs/04_DETECTION_RULES.md §R5.

Detects:
1. Invoices billed against cancelled / terminated contracts or after contract end_date
2. Invoices billed by cancelled / terminated / inactive vendors
3. Invoices referencing cancelled / terminated purchase orders
"""
from __future__ import annotations

from ..registry import DetectionContext, register
from ..types import EvidenceRef, Finding

_TERMINATED_STATUSES = {"cancelled", "terminated", "inactive", "suspended"}


def _norm_item(s: str) -> str:
    return " ".join(str(s or "").strip().lower().split())


@register("R5")
def detect_cancelled_service_leakage(ctx: DetectionContext) -> list[Finding]:
    findings: list[Finding] = []
    seen_keys: set[tuple[str, int, str]] = set()

    contracts_by_key: dict[tuple[str, str], list[dict]] = {}
    for c in ctx.contracts:
        key = (str(c.get("vendor_id", "")), _norm_item(c.get("item", "")))
        contracts_by_key.setdefault(key, []).append(c)

    vendors_by_id: dict[str, dict] = {
        str(v.get("vendor_id", "")): v for v in ctx.vendors if v.get("vendor_id")
    }
    po_by_id: dict[str, dict] = {
        str(p.get("po_id", "")): p for p in ctx.purchase_orders if p.get("po_id")
    }

    for inv in ctx.invoices:
        vendor_id = str(inv.get("vendor_id", ""))
        item_norm = _norm_item(inv.get("item", ""))
        inv_num = str(inv.get("invoice_number", ""))
        line_no = int(inv.get("line_no") or 1)
        inv_date = str(inv.get("invoice_date") or "")
        inv_status = str(inv.get("status") or "").lower()
        inv_curr = str(inv.get("currency") or "INR")
        line_total = float(inv.get("line_total") or 0.0)
        po_id = str(inv.get("po_id") or "").strip()

        # Check 1: Cancelled / terminated / expired contract for (vendor_id, item)
        for contract in contracts_by_key.get((vendor_id, item_norm), []):
            c_status = str(contract.get("status") or "").lower()
            end_date = str(contract.get("end_date") or "")
            contract_id = str(contract.get("contract_id", ""))
            is_cancelled_status = c_status in _TERMINATED_STATUSES
            is_after_end = bool(end_date and inv_date and inv_date > end_date)

            if (is_cancelled_status and (is_after_end or not end_date)) or is_after_end:
                dedup_key = (inv_num, line_no, f"contract:{contract_id}")
                if dedup_key in seen_keys:
                    continue
                seen_keys.add(dedup_key)
                severity = "critical" if inv_status == "paid" else "high"
                reason = f"contract {contract_id} was {c_status or 'expired'}"
                if end_date:
                    reason += f" effective {end_date}"
                findings.append(
                    Finding(
                        rule_id="R5",
                        title=f"Billed after contract cancellation ({inv.get('item', 'Item')})",
                        severity=severity,
                        amount_at_risk=round(line_total, 2),
                        currency=inv_curr,
                        entity_refs={
                            "invoice_numbers": [inv_num],
                            "line_no": line_no,
                            "contract_id": contract_id,
                            "vendor_id": vendor_id,
                        },
                        evidence=[
                            EvidenceRef("contracts", contract_id, "status", c_status or "expired"),
                            EvidenceRef("contracts", contract_id, "end_date", end_date or "N/A"),
                            EvidenceRef("invoices", inv_num, "invoice_date", inv_date),
                            EvidenceRef("invoices", inv_num, "line_total", f"{line_total:.2f} {inv_curr}"),
                        ],
                        confidence=0.98,
                        recommended_action="CANCEL_AUTOPAY",
                        summary=(
                            f"Invoice {inv_num} dated {inv_date} for {inv.get('item')} was billed after "
                            f"{reason}. Disallowed spend: {line_total:.2f} {inv_curr}."
                        ),
                        proof_trail={
                            "math": {
                                "contract_status": c_status,
                                "contract_end_date": end_date,
                                "invoice_date": inv_date,
                                "line_total": round(line_total, 2),
                            }
                        },
                    )
                )

        # Check 2: Vendor marked cancelled / terminated / inactive
        vendor = vendors_by_id.get(vendor_id)
        if vendor:
            v_status = str(vendor.get("status") or "").lower()
            if v_status in _TERMINATED_STATUSES:
                dedup_key = (inv_num, line_no, f"vendor:{vendor_id}")
                if dedup_key not in seen_keys:
                    seen_keys.add(dedup_key)
                    severity = "critical" if inv_status == "paid" else "high"
                    findings.append(
                        Finding(
                            rule_id="R5",
                            title=f"Billed by {v_status} vendor ({vendor.get('vendor_name', vendor_id)})",
                            severity=severity,
                            amount_at_risk=round(line_total, 2),
                            currency=inv_curr,
                            entity_refs={
                                "invoice_numbers": [inv_num],
                                "line_no": line_no,
                                "vendor_id": vendor_id,
                            },
                            evidence=[
                                EvidenceRef("vendors", vendor_id, "status", v_status),
                                EvidenceRef("invoices", inv_num, "line_total", f"{line_total:.2f} {inv_curr}"),
                            ],
                            confidence=0.95,
                            recommended_action="CANCEL_AUTOPAY",
                            summary=(
                                f"Invoice {inv_num} was issued by vendor {vendor_id} whose master status is '{v_status}'. "
                                f"Disallowed spend: {line_total:.2f} {inv_curr}."
                            ),
                            proof_trail={
                                "math": {
                                    "vendor_status": v_status,
                                    "line_total": round(line_total, 2),
                                }
                            },
                        )
                    )

        # Check 3: Cancelled PO referenced by invoice
        if po_id and po_id in po_by_id:
            po_status = str(po_by_id[po_id].get("status") or "").lower()
            if po_status in ("cancelled", "terminated"):
                dedup_key = (inv_num, line_no, f"po:{po_id}")
                if dedup_key not in seen_keys:
                    seen_keys.add(dedup_key)
                    severity = "critical" if inv_status == "paid" else "high"
                    findings.append(
                        Finding(
                            rule_id="R5",
                            title=f"Invoice billed against cancelled {po_id}",
                            severity=severity,
                            amount_at_risk=round(line_total, 2),
                            currency=inv_curr,
                            entity_refs={
                                "invoice_numbers": [inv_num],
                                "line_no": line_no,
                                "po_id": po_id,
                                "vendor_id": vendor_id,
                            },
                            evidence=[
                                EvidenceRef("purchase_orders", po_id, "status", po_status),
                                EvidenceRef("invoices", inv_num, "line_total", f"{line_total:.2f} {inv_curr}"),
                            ],
                            confidence=0.96,
                            recommended_action="CANCEL_AUTOPAY",
                            summary=(
                                f"Invoice {inv_num} references {po_id} which is marked '{po_status}'. "
                                f"Disallowed spend: {line_total:.2f} {inv_curr}."
                            ),
                            proof_trail={
                                "math": {
                                    "po_status": po_status,
                                    "line_total": round(line_total, 2),
                                }
                            },
                        )
                    )

    return findings

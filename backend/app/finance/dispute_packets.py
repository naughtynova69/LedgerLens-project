"""Deterministic vendor dispute packet generator for CFO and AP audit notices."""
from __future__ import annotations

import json
from typing import Any

_ACTION_REQUESTS: dict[str, str] = {
    "HOLD_PAYMENT": (
        "Please be advised that disbursement for the referenced invoice(s) has been placed "
        "on immediate payment hold pending resolution. Kindly review the cited variance details "
        "and provide written confirmation of the corrected invoice terms or an adjusted billing "
        "statement before payment can be released."
    ),
    "REQUEST_CREDIT_NOTE": (
        "Please issue an official credit note or process a direct refund/clawback settlement "
        "for the claimed amount at your earliest convenience, referencing the cited invoice "
        "and payment record(s) so our Accounts Payable team can reconcile the ledger."
    ),
    "DISPUTE_VENDOR": (
        "This communication serves as a formal billing dispute notice. The referenced "
        "invoice(s) have been placed on dispute hold. Please provide a rate, quantity, currency, "
        "or tax adjustment along with a revised compliant invoice reflecting the authorized terms."
    ),
    "CANCEL_AUTOPAY": (
        "Please cancel any recurring autopay or subscription billing associated with the "
        "referenced arrangement immediately, provide written confirmation of cancellation, and "
        "issue a credit note or refund for any charges billed past the termination date."
    ),
}

_DEFAULT_ACTION_REQUEST = (
    "Please review the audit details below and provide written clarification, supporting "
    "documentation, or a credit adjustment to our Accounts Payable team."
)


def _as_dict(value: Any) -> dict[str, Any]:
    """Normalize dict or JSON-encoded object into a dictionary."""
    if isinstance(value, dict):
        return value
    if isinstance(value, str):
        text = value.strip()
        if text.startswith("{"):
            try:
                parsed = json.loads(text)
                if isinstance(parsed, dict):
                    return parsed
            except (ValueError, TypeError):
                return {}
    return {}


def _as_list(value: Any) -> list[Any]:
    """Normalize list, scalar string, or JSON-encoded array into a list."""
    if isinstance(value, list):
        return value
    if isinstance(value, tuple):
        return list(value)
    if isinstance(value, str):
        text = value.strip()
        if not text:
            return []
        if text.startswith("["):
            try:
                parsed = json.loads(text)
                if isinstance(parsed, list):
                    return parsed
            except (ValueError, TypeError):
                pass
        return [text]
    return []


def _dedupe_strs(items: list[Any]) -> list[str]:
    """Convert non-empty values to strings and deduplicate while preserving order."""
    seen: set[str] = set()
    result: list[str] = []
    for item in items:
        if item is None:
            continue
        text = str(item).strip()
        if text and text not in seen:
            seen.add(text)
            result.append(text)
    return result


def _resolve_vendor_name(source_records: dict[str, Any], entity_refs: dict[str, Any]) -> str:
    """Resolve vendor name from source_records.vendors, falling back to entity_refs.vendor_id."""
    vendors = source_records.get("vendors")
    if isinstance(vendors, str):
        try:
            vendors = json.loads(vendors)
        except (ValueError, TypeError):
            vendors = None

    if isinstance(vendors, dict):
        name = str(vendors.get("vendor_name") or "").strip()
        if name:
            return name
    elif isinstance(vendors, list):
        for vendor in vendors:
            if isinstance(vendor, dict):
                name = str(vendor.get("vendor_name") or "").strip()
                if name:
                    return name

    vendor_id = str(entity_refs.get("vendor_id") or "").strip()
    return vendor_id or "Vendor"


def _format_amount(amount: Any) -> str:
    """Format numeric amounts without altering precision beyond 2 decimal places."""
    if isinstance(amount, (int, float)) and not isinstance(amount, bool):
        numeric = float(amount)
        if round(numeric, 2) == numeric:
            return f"{numeric:,.2f}"
        return str(amount)
    return str(amount)


def _extract_reference_ids(
    entity_refs: dict[str, Any],
    source_records: dict[str, Any],
) -> dict[str, Any]:
    """Extract verbatim invoice, PO, contract, payment, and vendor references."""
    vendor_id_raw = entity_refs.get("vendor_id")
    vendor_id = str(vendor_id_raw).strip() if vendor_id_raw else None
    if not vendor_id:
        for v in _as_list(source_records.get("vendors")):
            if isinstance(v, dict) and v.get("vendor_id"):
                vendor_id = str(v["vendor_id"]).strip()
                break

    invoice_numbers = _dedupe_strs(_as_list(entity_refs.get("invoice_numbers")))
    if not invoice_numbers:
        invoice_numbers = _dedupe_strs([
            inv.get("invoice_number")
            for inv in _as_list(source_records.get("invoices"))
            if isinstance(inv, dict)
        ])

    po_id_raw = entity_refs.get("po_id")
    po_id = str(po_id_raw).strip() if po_id_raw else None
    if not po_id:
        for po in _as_list(source_records.get("purchase_orders")):
            if isinstance(po, dict) and po.get("po_id"):
                po_id = str(po["po_id"]).strip()
                break

    contract_id_raw = entity_refs.get("contract_id")
    contract_id = str(contract_id_raw).strip() if contract_id_raw else None
    if not contract_id:
        for contract in _as_list(source_records.get("contracts")):
            if isinstance(contract, dict) and contract.get("contract_id"):
                contract_id = str(contract["contract_id"]).strip()
                break

    raw_payment_ids = _as_list(entity_refs.get("payment_ids"))
    source_payment_ids = [
        pmt.get("payment_id")
        for pmt in _as_list(source_records.get("payments"))
        if isinstance(pmt, dict)
    ]
    payment_ids = _dedupe_strs([*raw_payment_ids, *source_payment_ids])

    return {
        "vendor_id": vendor_id,
        "invoice_numbers": invoice_numbers,
        "po_id": po_id,
        "contract_id": contract_id,
        "payment_ids": payment_ids,
    }


def _build_body_text(
    *,
    finding_id: str,
    rule_id: str,
    title: str,
    severity: str,
    vendor_name: str,
    amount_display: str,
    currency: str,
    recommended_action: str,
    summary: str,
    reference_ids: dict[str, Any],
    math: dict[str, Any],
    evidence: list[Any],
) -> str:
    """Assemble a formal CFO/AP-ready vendor dispute notice from verbatim audit facts."""
    action_instruction = _ACTION_REQUESTS.get(recommended_action, _DEFAULT_ACTION_REQUEST)
    severity_label = f" (Severity: {severity.upper()})" if severity else ""

    lines: list[str] = [
        f"Dear {vendor_name} Accounts Receivable & Billing Team,",
        "",
        (
            f"During a routine Accounts Payable audit under LedgerLens Audit Finding "
            f"{finding_id or 'N/A'} (Rule {rule_id or 'N/A'}{severity_label}), our finance "
            f"compliance review identified the following discrepancy: {title}. The total "
            f"amount at risk / claimed under this notice is {amount_display} {currency}."
        ),
    ]

    if summary:
        lines.extend(["", "Audit Summary:", summary])

    lines.extend([
        "",
        f"Action Requested [{recommended_action}]:",
        action_instruction,
        "",
        "Referenced Records:",
        f"- Finding ID: {finding_id or 'N/A'}",
        f"- Rule ID: {rule_id or 'N/A'}",
    ])

    if reference_ids["vendor_id"]:
        lines.append(f"- Vendor ID: {reference_ids['vendor_id']}")
    inv_nums = reference_ids["invoice_numbers"]
    lines.append(f"- Invoice Number(s): {', '.join(inv_nums) if inv_nums else 'N/A'}")
    if reference_ids["po_id"]:
        lines.append(f"- Purchase Order ID: {reference_ids['po_id']}")
    if reference_ids["contract_id"]:
        lines.append(f"- Contract ID: {reference_ids['contract_id']}")
    if reference_ids["payment_ids"]:
        lines.append(f"- Payment ID(s): {', '.join(reference_ids['payment_ids'])}")

    lines.extend(["", "Audit Calculation Details (Proof Trail Math):"])
    if math:
        for key, value in math.items():
            lines.append(f"- {key}: {value}")
    else:
        lines.append("- None provided")

    if evidence:
        lines.extend(["", "Supporting Evidence Citations:"])
        for item in evidence:
            if isinstance(item, dict):
                source = item.get("source", "")
                record_id = item.get("record_id", "")
                field = item.get("field", "")
                value = item.get("value", "")
                lines.append(f"- {source}:{record_id} | {field} = {value}")
            else:
                lines.append(f"- {item}")

    lines.extend([
        "",
        (
            f"Kindly respond with confirmation or supporting documentation referencing "
            f"{finding_id or 'this notice'} at your earliest convenience so we can update "
            "our Accounts Payable records accordingly."
        ),
        "",
        "Sincerely,",
        "Accounts Payable & Finance Audit Compliance Team",
    ])
    return "\n".join(lines)


def generate_dispute_packet(finding_with_sources: dict) -> dict:
    """Build a formal vendor dispute email packet from get_finding_with_sources output."""
    finding_id = str(finding_with_sources.get("finding_id") or "")
    rule_id = str(finding_with_sources.get("rule_id") or "")
    title = str(finding_with_sources.get("title") or "Audit Discrepancy Notice")
    severity = str(finding_with_sources.get("severity") or "")

    raw_amount = finding_with_sources.get("amount_at_risk")
    amount_at_risk = 0.0 if raw_amount is None else raw_amount
    currency = str(finding_with_sources.get("currency") or "INR")

    proof_trail = _as_dict(finding_with_sources.get("proof_trail"))
    recommended_action = str(
        finding_with_sources.get("recommended_action")
        or proof_trail.get("recommended_action")
        or "HOLD_PAYMENT"
    )
    summary = str(finding_with_sources.get("summary") or "")

    entity_refs = _as_dict(finding_with_sources.get("entity_refs"))
    evidence = _as_list(finding_with_sources.get("evidence"))
    source_records = _as_dict(finding_with_sources.get("source_records"))
    math = _as_dict(proof_trail.get("math"))

    vendor_name = _resolve_vendor_name(source_records, entity_refs)
    reference_ids = _extract_reference_ids(entity_refs, source_records)

    invoice_numbers = reference_ids["invoice_numbers"]
    invoice_str = ", ".join(invoice_numbers) if invoice_numbers else "N/A"
    amount_display = _format_amount(amount_at_risk)

    subject = (
        f"[LedgerLens Audit Notice {finding_id}] {title} — "
        f"{amount_display} {currency} ({invoice_str})"
    )
    body_text = _build_body_text(
        finding_id=finding_id,
        rule_id=rule_id,
        title=title,
        severity=severity,
        vendor_name=vendor_name,
        amount_display=amount_display,
        currency=currency,
        recommended_action=recommended_action,
        summary=summary,
        reference_ids=reference_ids,
        math=math,
        evidence=evidence,
    )

    return {
        "finding_id": finding_id,
        "rule_id": rule_id,
        "to_vendor": vendor_name,
        "subject": subject,
        "body_text": body_text,
        "amount_claimed": amount_at_risk,
        "currency": currency,
        "recommended_action": recommended_action,
        "reference_ids": reference_ids,
    }

"""R4 — Currency & tax error detector (deterministic core).

Spec: docs/04_DETECTION_RULES.md §R4.

Detects:
1. Currency mismatch against PO -> Contract -> Vendor default_currency (max 1 per invoice line)
2. FX rate anomaly on settled payments (> 2% deviation vs reference INR rates)
3. Tax overcharge / invalid tax vs contract tax_pct
4. Duplicate tax lines for the same (invoice_number, item)
"""
from __future__ import annotations

from ..registry import DetectionContext, register
from ..types import EvidenceRef, Finding

REFERENCE_FX_RATES = {
    "INR": 1.0,
    "USD": 88.0,
    "EUR": 95.0,
    "GBP": 112.0,
}

MAX_FX_DRIFT = 0.02


def _norm_item(s: str) -> str:
    return " ".join(str(s or "").strip().lower().split())


@register("R4")
def detect_currency_tax_errors(ctx: DetectionContext) -> list[Finding]:
    findings: list[Finding] = []
    policy = ctx.get("policy", {}) if isinstance(ctx, dict) else (getattr(ctx, "policy", None) or {})
    raw_fx_drift_pct = policy.get("r4_max_fx_drift_pct")
    max_fx_drift = float(raw_fx_drift_pct) / 100.0 if raw_fx_drift_pct is not None else MAX_FX_DRIFT
    fx_rates = dict(REFERENCE_FX_RATES)
    if isinstance(policy.get("fx_rates"), dict):
        for curr, rate in policy["fx_rates"].items():
            try:
                val = float(rate)
            except (TypeError, ValueError):
                continue
            if val > 0:
                fx_rates[str(curr).strip().upper()] = val

    po_by_id: dict[str, dict] = {
        str(po.get("po_id", "")): po for po in ctx.purchase_orders if po.get("po_id")
    }
    contracts_map: dict[tuple[str, str], dict] = {
        (str(c.get("vendor_id", "")), _norm_item(c.get("item", ""))): c
        for c in ctx.contracts
    }
    vendors_by_id: dict[str, dict] = {
        str(v.get("vendor_id", "")): v for v in ctx.vendors if v.get("vendor_id")
    }

    seen_tax_lines: dict[tuple[str, str], list[dict]] = {}

    for inv in ctx.invoices:
        inv_num = str(inv.get("invoice_number", ""))
        vendor_id = str(inv.get("vendor_id", ""))
        po_id = str(inv.get("po_id") or "").strip()
        line_no = int(inv.get("line_no") or 1)
        item_norm = _norm_item(inv.get("item", ""))
        inv_curr = str(inv.get("currency") or "").strip().upper()
        inv_tax = float(inv.get("tax_pct") or 0.0)
        inv_qty = float(inv.get("quantity") or 0.0)
        inv_price = float(inv.get("unit_price") or 0.0)
        line_total = float(inv.get("line_total") or (inv_qty * inv_price * (1.0 + inv_tax / 100.0)))

        seen_tax_lines.setdefault((inv_num, item_norm), []).append(inv)

        # Check 1: Currency mismatch (precedence: PO -> Contract -> Vendor default_currency)
        expected_curr = ""
        expected_source = ""
        expected_id = ""
        evidence_refs: list[EvidenceRef] = [
            EvidenceRef("invoices", inv_num, "currency", inv_curr),
        ]
        contract = contracts_map.get((vendor_id, item_norm))
        vendor = vendors_by_id.get(vendor_id)
        po = po_by_id.get(po_id) if po_id else None

        if po and po.get("currency"):
            expected_curr = str(po["currency"]).strip().upper()
            expected_source = "purchase_orders"
            expected_id = po_id
        elif contract and contract.get("currency"):
            expected_curr = str(contract["currency"]).strip().upper()
            expected_source = "contracts"
            expected_id = str(contract.get("contract_id", ""))
        elif vendor and vendor.get("default_currency"):
            expected_curr = str(vendor["default_currency"]).strip().upper()
            expected_source = "vendors"
            expected_id = vendor_id

        if inv_curr and expected_curr and inv_curr != expected_curr:
            evidence_refs.append(EvidenceRef(expected_source, expected_id, "currency", expected_curr))
            if contract and contract.get("currency") and expected_source != "contracts":
                c_curr = str(contract["currency"]).strip().upper()
                if c_curr != inv_curr:
                    evidence_refs.append(EvidenceRef("contracts", str(contract.get("contract_id", "")), "currency", c_curr))
            evidence_refs.append(EvidenceRef("invoices", inv_num, "line_total", f"{line_total:.2f} {inv_curr}"))

            entity_refs: dict = {
                "invoice_numbers": [inv_num],
                "line_no": line_no,
                "vendor_id": vendor_id,
            }
            if po_id:
                entity_refs["po_id"] = po_id
            if contract and contract.get("contract_id"):
                entity_refs["contract_id"] = str(contract["contract_id"])

            findings.append(
                Finding(
                    rule_id="R4",
                    title=f"Currency mismatch on invoice {inv_num}",
                    severity="high",
                    amount_at_risk=round(line_total, 2),
                    currency=inv_curr,
                    entity_refs=entity_refs,
                    evidence=evidence_refs,
                    confidence=0.94,
                    recommended_action="DISPUTE_VENDOR",
                    summary=(
                        f"Invoice {inv_num} billed in {inv_curr} against {expected_id} "
                        f"which was authorized in {expected_curr}. Unauthorized foreign exchange exposure: {line_total:.2f} {inv_curr}."
                    ),
                    proof_trail={
                        "math": {
                            "billed_currency": inv_curr,
                            "expected_currency": expected_curr,
                            "expected_source": expected_source,
                            "line_total": round(line_total, 2),
                        }
                    },
                )
            )

        # Check 2: Tax error against Contract
        if contract is not None:
            contract_tax = float(contract.get("tax_pct") or 0.0)
            contract_id = str(contract.get("contract_id", ""))
            contract_curr = str(contract.get("currency") or inv_curr or "INR")

            if inv_tax > contract_tax + 1e-4:
                tax_delta_pct = inv_tax - contract_tax
                tax_at_risk = round(inv_qty * inv_price * (tax_delta_pct / 100.0), 2)
                findings.append(
                    Finding(
                        rule_id="R4",
                        title=f"Invalid tax charge on {inv.get('item', 'Item')}",
                        severity="high",
                        amount_at_risk=tax_at_risk,
                        currency=inv_curr or contract_curr,
                        entity_refs={
                            "invoice_numbers": [inv_num],
                            "line_no": line_no,
                            "contract_id": contract_id,
                            "vendor_id": vendor_id,
                        },
                        evidence=[
                            EvidenceRef("invoices", inv_num, "tax_pct", f"{inv_tax:g}%"),
                            EvidenceRef("contracts", contract_id, "tax_pct", f"{contract_tax:g}%"),
                            EvidenceRef("invoices", inv_num, "tax_delta", f"{tax_delta_pct:g}%"),
                        ],
                        confidence=0.96,
                        recommended_action="DISPUTE_VENDOR",
                        summary=(
                            f"Invoice {inv_num} applied {inv_tax:g}% GST on {inv.get('item')}, "
                            f"which contract {contract_id} specifies as {contract_tax:g}% (exempt). "
                            f"Unwarranted tax exposure: {tax_at_risk:.2f} {inv_curr}."
                        ),
                        proof_trail={
                            "math": {
                                "billed_tax_pct": inv_tax,
                                "contract_tax_pct": contract_tax,
                                "tax_delta_pct": tax_delta_pct,
                                "taxable_base": round(inv_qty * inv_price, 2),
                                "amount_at_risk": tax_at_risk,
                            }
                        },
                    )
                )

    # Check 3: Duplicate tax line within same invoice & item
    for (inv_num, item_norm), lines in seen_tax_lines.items():
        taxed = [ln for ln in lines if float(ln.get("tax_pct") or 0.0) > 0]
        if len(taxed) >= 2:
            extra_tax = sum(
                round(float(ln.get("quantity") or 0) * float(ln.get("unit_price") or 0) * (float(ln.get("tax_pct") or 0) / 100.0), 2)
                for ln in taxed[1:]
            )
            if extra_tax > 0:
                curr = str(taxed[0].get("currency") or "INR")
                findings.append(
                    Finding(
                        rule_id="R4",
                        title=f"Duplicate tax line on invoice {inv_num}",
                        severity="high",
                        amount_at_risk=round(extra_tax, 2),
                        currency=curr,
                        entity_refs={
                            "invoice_numbers": [inv_num],
                            "vendor_id": str(taxed[0].get("vendor_id") or ""),
                            "line_no": int(taxed[1].get("line_no") or 2),
                        },
                        evidence=[
                            EvidenceRef("invoices", inv_num, "duplicate_tax_lines", str(len(taxed))),
                            EvidenceRef("invoices", inv_num, "extra_tax_amount", f"{extra_tax:.2f} {curr}"),
                        ],
                        confidence=0.91,
                        recommended_action="DISPUTE_VENDOR",
                        summary=(
                            f"Invoice {inv_num} applied tax multiple times ({len(taxed)} lines) "
                            f"for '{taxed[0].get('item')}'. Duplicate tax exposure: {extra_tax:.2f} {curr}."
                        ),
                        proof_trail={
                            "math": {
                                "taxed_line_count": len(taxed),
                                "extra_tax_amount": round(extra_tax, 2),
                            }
                        },
                    )
                )

    # Check 4: FX rate anomaly on payments against effective fx_rates
    for pay in ctx.payments:
        pay_curr = str(pay.get("currency") or "").strip().upper()
        ref_rate = fx_rates.get(pay_curr)
        if not ref_rate:
            continue
        actual_fx = float(pay.get("fx_rate_to_inr") or 0.0)
        if actual_fx <= 0:
            continue
        drift = abs(actual_fx - ref_rate) / ref_rate
        if drift > max_fx_drift:
            pay_amt = float(pay.get("amount") or 0.0)
            inr_delta = round(abs(actual_fx - ref_rate) * pay_amt, 2)
            pay_id = str(pay.get("payment_id", ""))
            inv_num = str(pay.get("invoice_number", ""))
            findings.append(
                Finding(
                    rule_id="R4",
                    title=f"FX conversion rate anomaly on {pay_id}",
                    severity="high",
                    amount_at_risk=inr_delta,
                    currency="INR",
                    entity_refs={
                        "invoice_numbers": [inv_num] if inv_num else [],
                        "payment_ids": [pay_id],
                    },
                    evidence=[
                        EvidenceRef("payments", pay_id, "fx_rate_to_inr", f"{actual_fx:.4f}"),
                        EvidenceRef("payments", pay_id, "reference_fx_rate", f"{ref_rate:.4f} ({pay_curr}/INR)"),
                    ],
                    confidence=0.93,
                    recommended_action="REQUEST_CREDIT_NOTE",
                    summary=(
                        f"Payment {pay_id} settled {pay_amt:,.2f} {pay_curr} at FX rate {actual_fx:.2f} INR "
                        f"vs reference rate {ref_rate:.2f} INR ({drift:.1%} drift). INR variance: {inr_delta:,.2f} INR."
                    ),
                    proof_trail={
                        "math": {
                            "payment_amount": pay_amt,
                            "payment_currency": pay_curr,
                            "actual_fx_rate_to_inr": actual_fx,
                            "reference_fx_rate_to_inr": ref_rate,
                            "drift_pct": round(drift * 100.0, 2),
                            "inr_delta": inr_delta,
                        }
                    },
                )
            )

    return findings

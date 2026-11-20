"""Gemini extraction (docs/06 §3). Structured output, temperature 0, fail closed.

Routes single/complex documents (PDFs/contracts) to GEMINI_PRIMARY_MODEL
(`gemini-4-carbon` default) and batch/CSV rows to GEMINI_FLASH_MODEL
(`gemini-3.8-vision-flash` default). Provides deterministic mock/fallback extraction
when GEMINI_API_KEY is unset so offline CI tests and demos never crash.
"""
from __future__ import annotations

import csv
import io
import json
from pathlib import Path
import re

from .. import config
from ..gcp.vertex_ai import create_genai_client, has_live_ai_credentials
from ..normalize import (
    canonical_vendor_key,
    normalize_amount,
    normalize_currency,
    normalize_date,
    normalize_invoice_row,
)
from .schemas import (
    CONTRACT_SCHEMA,
    INVOICE_SCHEMA,
    ContractHeaderExtracted,
    ContractLineExtracted,
    ExtractedContractPayload,
    ExtractedInvoicePayload,
    ExtractedPOPayload,
    InvoiceHeaderExtracted,
    InvoiceLineExtracted,
    InvoiceTotalsExtracted,
    POHeaderExtracted,
    POLineExtracted,
    VendorExtracted,
)

EXTRACTION_SYSTEM_PROMPT = """\
You are a data-entry engine for an accounts-payable audit system.
Extract fields from the provided invoice/contract document.
Return ONLY what is literally present in the document — never guess,
never infer missing values (leave them null).
Follow the provided JSON schema exactly.
Currency codes are ISO-4217 (e.g. INR, USD, EUR). Dates are YYYY-MM-DD.
If the document is a scan, read it; if a field is unreadable, return null.
"""


def select_extraction_model(
    kind: str,
    is_batch: bool = False,
    mime_type: str = "application/pdf",
) -> str:
    """Route complex single documents to primary model and batch/CSV loads to flash model."""
    if is_batch or mime_type == "text/csv":
        return config.GEMINI_FLASH_MODEL
    if kind in ("invoices", "contracts", "purchase_orders"):
        return config.GEMINI_PRIMARY_MODEL
    return config.GEMINI_FLASH_MODEL


def verify_extracted_line_totals(
    lines: list[dict],
    tolerance: float = 0.05,
) -> list[dict]:
    """Deterministically verify quantity * unit_price * (1 + tax_pct/100) == line_total."""
    warnings: list[dict] = []
    for idx, line in enumerate(lines, start=1):
        qty = line.get("quantity")
        unit_price = line.get("unit_price")
        line_total = line.get("line_total")
        if qty is None or unit_price is None or line_total is None:
            continue
        try:
            qty_f = float(qty)
            price_f = float(unit_price)
            tax_f = float(line.get("tax_pct") or 0.0)
            actual_f = float(line_total)
        except (TypeError, ValueError):
            continue

        expected = round(qty_f * price_f * (1.0 + tax_f / 100.0), 2)
        delta = round(actual_f - expected, 2)
        if abs(delta) > tolerance:
            line_no = line.get("line_no") or idx
            item = line.get("item") or "Unknown Item"
            warnings.append({
                "line_no": line_no,
                "item": item,
                "expected_line_total": expected,
                "actual_line_total": round(actual_f, 2),
                "delta": delta,
                "message": (
                    f"Line {line_no} ({item}) total mismatch: "
                    f"expected {expected:.2f} vs extracted {actual_f:.2f}"
                ),
            })
    return warnings


def _client():
    return create_genai_client()


def _generate_with_model(
    file_bytes: bytes,
    mime_type: str,
    schema,
    model_name: str,
) -> dict:
    from google.genai import types  # lazy import

    response = _client().models.generate_content(
        model=model_name,
        contents=[types.Part.from_bytes(data=file_bytes, mime_type=mime_type)],
        config=types.GenerateContentConfig(
            system_instruction=EXTRACTION_SYSTEM_PROMPT,
            temperature=0,
            response_mime_type="application/json",
            response_schema=schema,
        ),
    )
    return json.loads(response.text)


def _mime_for_path(file_path: Path) -> str:
    ext = file_path.suffix.lower()
    if ext == ".csv":
        return "text/csv"
    if ext == ".png":
        return "image/png"
    if ext in (".jpg", ".jpeg"):
        return "image/jpeg"
    return "application/pdf"


def _extract_kv(text: str, patterns: tuple[str, ...]) -> str | None:
    for pat in patterns:
        m = re.search(pat, text, flags=re.IGNORECASE | re.MULTILINE)
        if m:
            return m.group(1).strip()
    return None


def _mock_extract_invoice_payload(
    file_bytes: bytes,
    source_name: str = "uploaded.pdf",
) -> ExtractedInvoicePayload:
    """Deterministic text/mock extractor used when GEMINI_API_KEY is unset."""
    text = file_bytes.decode("utf-8", errors="ignore")
    inv_no = _extract_kv(text, (r"invoice\s*(?:number|no|#)\s*[:\-]\s*([^\r\n,;]+)",))
    vendor_name = _extract_kv(text, (r"vendor(?:\s*name)?\s*[:\-]\s*([^\r\n,;]+)",))
    inv_date = _extract_kv(text, (r"(?:invoice\s*)?date\s*[:\-]\s*([^\r\n,;]+)",))
    po_ref = _extract_kv(text, (r"po(?:\s*(?:id|ref|reference|number))?\s*[:\-]\s*([^\r\n,;]+)",))
    currency = _extract_kv(text, (r"currency\s*[:\-]\s*([^\r\n,;]+)",))
    item = _extract_kv(text, (r"item\s*[:\-]\s*([^\r\n,;]+)",))
    qty_s = _extract_kv(text, (r"(?:quantity|qty)\s*[:\-]\s*([^\r\n,;]+)",))
    price_s = _extract_kv(text, (r"unit\s*price\s*[:\-]\s*([^\r\n,;]+)",))
    tax_s = _extract_kv(text, (r"tax(?:\s*%|_pct)?\s*[:\-]\s*([^\r\n,;]+)",))
    total_s = _extract_kv(text, (r"(?:line[_\s]*total|grand[_\s]*total|total)\s*[:\-]\s*([^\r\n,;]+)",))

    stem_id = re.sub(r"[^A-Z0-9\-]", "", Path(source_name).stem.upper())[:20] or "SCAN-001"
    number = inv_no or f"INV-{stem_id}"
    vendor_clean = vendor_name or "Extracted PDF Vendor"
    norm_date = normalize_date(inv_date or "2026-11-15")
    norm_curr = normalize_currency(currency or "INR") or "INR"
    qty = normalize_amount(qty_s) if qty_s else 1.0
    unit_price = normalize_amount(price_s) if price_s else 1000.0
    tax_pct = normalize_amount(tax_s) if tax_s else 18.0
    computed_total = round(qty * unit_price * (1.0 + tax_pct / 100.0), 2)
    line_total = normalize_amount(total_s) if total_s else computed_total
    subtotal = round(qty * unit_price, 2)
    tax_amt = round(line_total - subtotal, 2)

    return ExtractedInvoicePayload(
        vendor=VendorExtracted(name=vendor_clean, tax_id=None),
        invoice=InvoiceHeaderExtracted(
            number=number,
            date=norm_date,
            currency=norm_curr,
            po_reference=po_ref or "",
            payment_terms="Net 30",
        ),
        lines=[
            InvoiceLineExtracted(
                item=item or "Extracted Line Item",
                quantity=qty,
                unit_price=unit_price,
                tax_pct=tax_pct,
                line_total=line_total,
            )
        ],
        totals=InvoiceTotalsExtracted(
            subtotal=subtotal,
            tax=tax_amt,
            grand_total=line_total,
        ),
    )


def _mock_extract_contract_payload(
    file_bytes: bytes,
    source_name: str = "contract.pdf",
) -> ExtractedContractPayload:
    text = file_bytes.decode("utf-8", errors="ignore")
    cid = _extract_kv(text, (r"contract\s*(?:id|no|#)\s*[:\-]\s*([^\r\n,;]+)",))
    vendor_name = _extract_kv(text, (r"vendor(?:\s*name)?\s*[:\-]\s*([^\r\n,;]+)",))
    item = _extract_kv(text, (r"item\s*[:\-]\s*([^\r\n,;]+)",))
    price_s = _extract_kv(text, (r"(?:contracted[_\s]*)?unit[_\s]*price\s*[:\-]\s*([^\r\n,;]+)",))
    currency = _extract_kv(text, (r"currency\s*[:\-]\s*([^\r\n,;]+)",))
    status = _extract_kv(text, (r"status\s*[:\-]\s*([^\r\n,;]+)",))

    stem_id = re.sub(r"[^A-Z0-9\-]", "", Path(source_name).stem.upper())[:16] or "PDF"
    return ExtractedContractPayload(
        contract=ContractHeaderExtracted(
            id=cid or f"C-{stem_id}",
            title=f"Extracted Contract ({source_name})",
            vendor_name=vendor_name or "Extracted PDF Vendor",
            start_date="2026-01-01",
            end_date="2026-12-31",
            status=(status or "active").lower(),
        ),
        lines=[
            ContractLineExtracted(
                item=item or "Extracted Service",
                unit_price=normalize_amount(price_s) if price_s else 1000.0,
                currency=normalize_currency(currency or "INR") or "INR",
                discount_pct=0.0,
                payment_terms="Net 30",
                tax_pct=18.0,
            )
        ],
    )


def _mock_extract_po_payload(
    file_bytes: bytes,
    source_name: str = "po.pdf",
) -> ExtractedPOPayload:
    text = file_bytes.decode("utf-8", errors="ignore")
    po_id = _extract_kv(text, (r"po\s*(?:id|no|#)\s*[:\-]\s*([^\r\n,;]+)",))
    vendor_name = _extract_kv(text, (r"vendor(?:\s*name)?\s*[:\-]\s*([^\r\n,;]+)",))
    item = _extract_kv(text, (r"item\s*[:\-]\s*([^\r\n,;]+)",))
    qty_s = _extract_kv(text, (r"(?:quantity|qty)\s*[:\-]\s*([^\r\n,;]+)",))
    price_s = _extract_kv(text, (r"unit\s*price\s*[:\-]\s*([^\r\n,;]+)",))
    currency = _extract_kv(text, (r"currency\s*[:\-]\s*([^\r\n,;]+)",))

    stem_id = re.sub(r"[^A-Z0-9\-]", "", Path(source_name).stem.upper())[:16] or "PDF"
    return ExtractedPOPayload(
        purchase_order=POHeaderExtracted(
            po_id=po_id or f"PO-{stem_id}",
            vendor_name=vendor_name or "Extracted PDF Vendor",
            order_date="2026-11-01",
            expected_delivery="2026-11-15",
            status="open",
        ),
        lines=[
            POLineExtracted(
                item=item or "Extracted Item",
                quantity=normalize_amount(qty_s) if qty_s else 1.0,
                unit_price=normalize_amount(price_s) if price_s else 1000.0,
                currency=normalize_currency(currency or "INR") or "INR",
            )
        ],
    )


def _derive_vendor_id(vendor_name: str | None) -> str:
    key = canonical_vendor_key(vendor_name or "")
    slug = re.sub(r"[^A-Z0-9]", "", key.upper())[:10]
    return f"V-{slug}" if slug else "V-PDF"


def _payload_to_invoice_records(
    payload: ExtractedInvoicePayload,
    source_file: str,
) -> tuple[list[dict], bool]:
    inv_num = (payload.invoice.number or "").strip()
    grand_total = payload.totals.grand_total
    needs_review = (not inv_num) or (grand_total is None and not payload.lines)
    vendor_name = (payload.vendor.name or "Extracted Vendor").strip()
    vendor_id = _derive_vendor_id(vendor_name)
    inv_date = normalize_date(payload.invoice.date or "")
    curr = normalize_currency(payload.invoice.currency or "INR") or "INR"
    po_id = (payload.invoice.po_reference or "").strip() or None

    records: list[dict] = []
    for idx, line in enumerate(payload.lines, start=1):
        qty = float(line.quantity or 0.0)
        unit_price = float(line.unit_price or 0.0)
        tax_pct = float(line.tax_pct or 0.0)
        line_total = (
            float(line.line_total)
            if line.line_total is not None
            else round(qty * unit_price * (1.0 + tax_pct / 100.0), 2)
        )
        records.append({
            "invoice_number": inv_num or f"QUARANTINE-{Path(source_file).stem}",
            "vendor_id": vendor_id,
            "vendor_name": vendor_name,
            "invoice_date": inv_date,
            "po_id": po_id,
            "line_no": idx,
            "item": (line.item or "Unknown Item").strip(),
            "quantity": qty,
            "unit_price": unit_price,
            "currency": curr,
            "tax_pct": tax_pct,
            "line_total": round(line_total, 2),
            "source_file": source_file,
            "status": "needs_review" if needs_review else "unpaid",
        })
    return records, needs_review


def _payload_to_contract_records(payload: ExtractedContractPayload) -> tuple[list[dict], bool]:
    cid = (payload.contract.id or "").strip()
    needs_review = not cid or not payload.lines
    vendor_name = (payload.contract.vendor_name or "Extracted Vendor").strip()
    vendor_id = _derive_vendor_id(vendor_name)
    records: list[dict] = []
    for line in payload.lines:
        records.append({
            "contract_id": cid or "C-QUARANTINE",
            "vendor_id": vendor_id,
            "vendor_name": vendor_name,
            "item": (line.item or "Unknown Item").strip(),
            "contracted_unit_price": float(line.unit_price or 0.0),
            "currency": normalize_currency(line.currency or "INR") or "INR",
            "discount_pct": float(line.discount_pct or 0.0),
            "payment_terms": line.payment_terms or "Net 30",
            "tax_pct": float(line.tax_pct or 0.0),
            "start_date": normalize_date(payload.contract.start_date or ""),
            "end_date": normalize_date(payload.contract.end_date or ""),
            "status": (payload.contract.status or "active").lower(),
        })
    return records, needs_review


def _payload_to_po_records(payload: ExtractedPOPayload) -> tuple[list[dict], bool]:
    po_id = (payload.purchase_order.po_id or "").strip()
    needs_review = not po_id or not payload.lines
    vendor_name = (payload.purchase_order.vendor_name or "Extracted Vendor").strip()
    vendor_id = _derive_vendor_id(vendor_name)
    records: list[dict] = []
    for idx, line in enumerate(payload.lines, start=1):
        records.append({
            "po_id": po_id or "PO-QUARANTINE",
            "po_line": idx,
            "vendor_id": vendor_id,
            "vendor_name": vendor_name,
            "item": (line.item or "Unknown Item").strip(),
            "quantity": float(line.quantity or 0.0),
            "unit_price": float(line.unit_price or 0.0),
            "currency": normalize_currency(line.currency or "INR") or "INR",
            "order_date": normalize_date(payload.purchase_order.order_date or ""),
            "expected_delivery": normalize_date(payload.purchase_order.expected_delivery or ""),
            "status": (payload.purchase_order.status or "open").lower(),
        })
    return records, needs_review


def extract_invoice(pdf_bytes: bytes, mime_type: str = "application/pdf") -> dict:
    """Invoice PDF/scan -> canonical invoice JSON (ExtractedInvoicePayload)."""
    model_name = select_extraction_model("invoices", is_batch=False, mime_type=mime_type)
    if has_live_ai_credentials():
        raw = _generate_with_model(pdf_bytes, mime_type, ExtractedInvoicePayload, model_name)
        payload = ExtractedInvoicePayload.model_validate(raw)
        data = payload.model_dump()
        data["mode"] = "gemini_live"
        data["model"] = model_name
        return data

    payload = _mock_extract_invoice_payload(pdf_bytes)
    data = payload.model_dump()
    data["mode"] = "mock_fallback"
    data["model"] = model_name
    return data


def extract_contract(pdf_bytes: bytes, mime_type: str = "application/pdf") -> dict:
    """Contract PDF/scan -> canonical contract JSON (ExtractedContractPayload)."""
    model_name = select_extraction_model("contracts", is_batch=False, mime_type=mime_type)
    if has_live_ai_credentials():
        raw = _generate_with_model(pdf_bytes, mime_type, ExtractedContractPayload, model_name)
        payload = ExtractedContractPayload.model_validate(raw)
        data = payload.model_dump()
        data["mode"] = "gemini_live"
        data["model"] = model_name
        return data

    payload = _mock_extract_contract_payload(pdf_bytes)
    data = payload.model_dump()
    data["mode"] = "mock_fallback"
    data["model"] = model_name
    return data


def extract_document(file_path: Path, kind: str, is_batch: bool = False) -> dict:
    """Extract CSV or PDF/scan file into normalized records + verification checks."""
    mime_type = _mime_for_path(file_path)
    model_name = select_extraction_model(kind, is_batch=is_batch, mime_type=mime_type)
    file_bytes = file_path.read_bytes()

    if mime_type == "text/csv":
        text = file_bytes.decode("utf-8", errors="replace")
        reader = csv.DictReader(io.StringIO(text))
        records: list[dict] = []
        for row in reader:
            cleaned = {
                k.strip(): (v.strip() if isinstance(v, str) else v)
                for k, v in row.items()
                if k is not None
            }
            if kind == "invoices":
                cleaned = normalize_invoice_row(cleaned)
            else:
                if "currency" in cleaned and cleaned["currency"]:
                    cleaned["currency"] = normalize_currency(cleaned["currency"])
                for date_col in ("start_date", "end_date", "order_date", "expected_delivery", "payment_date"):
                    if date_col in cleaned and cleaned[date_col]:
                        cleaned[date_col] = normalize_date(cleaned[date_col])
                for num_col in (
                    "quantity", "unit_price", "tax_pct", "line_total", "amount",
                    "contracted_unit_price", "discount_pct", "fx_rate_to_inr",
                ):
                    if num_col in cleaned and cleaned[num_col] not in (None, ""):
                        cleaned[num_col] = normalize_amount(cleaned[num_col])
            records.append(cleaned)

        warnings = verify_extracted_line_totals(records) if kind == "invoices" else []
        return {
            "mode": "csv_deterministic",
            "model": model_name,
            "kind": kind,
            "records": records,
            "verification_warnings": warnings,
            "needs_review": bool(warnings),
        }

    # PDF / image extraction path
    source_name = file_path.name
    if kind == "contracts":
        if has_live_ai_credentials():
            raw = _generate_with_model(file_bytes, mime_type, ExtractedContractPayload, model_name)
            payload = ExtractedContractPayload.model_validate(raw)
            mode = "gemini_live"
        else:
            payload = _mock_extract_contract_payload(file_bytes, source_name)
            mode = "mock_fallback"
        records, needs_review = _payload_to_contract_records(payload)
        return {
            "mode": mode,
            "model": model_name,
            "kind": kind,
            "payload": payload.model_dump(),
            "records": records,
            "verification_warnings": [],
            "needs_review": needs_review,
        }

    if kind == "purchase_orders":
        if has_live_ai_credentials():
            raw = _generate_with_model(file_bytes, mime_type, ExtractedPOPayload, model_name)
            payload = ExtractedPOPayload.model_validate(raw)
            mode = "gemini_live"
        else:
            payload = _mock_extract_po_payload(file_bytes, source_name)
            mode = "mock_fallback"
        records, needs_review = _payload_to_po_records(payload)
        return {
            "mode": mode,
            "model": model_name,
            "kind": kind,
            "payload": payload.model_dump(),
            "records": records,
            "verification_warnings": [],
            "needs_review": needs_review,
        }

    # Default: invoices PDF / scan
    if has_live_ai_credentials():
        raw = _generate_with_model(file_bytes, mime_type, ExtractedInvoicePayload, model_name)
        payload = ExtractedInvoicePayload.model_validate(raw)
        mode = "gemini_live"
    else:
        payload = _mock_extract_invoice_payload(file_bytes, source_name)
        mode = "mock_fallback"

    records, missing_required = _payload_to_invoice_records(payload, source_name)
    warnings = verify_extracted_line_totals(records)
    return {
        "mode": mode,
        "model": model_name,
        "kind": kind,
        "payload": payload.model_dump(),
        "records": records,
        "verification_warnings": warnings,
        "needs_review": bool(missing_required or warnings),
    }

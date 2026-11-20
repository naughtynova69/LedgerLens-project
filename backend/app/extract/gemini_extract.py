"""Gemini extraction (docs/06 §3). Structured output, temperature 0, fail closed.

Routes single/complex documents (PDFs/contracts) to GEMINI_PRIMARY_MODEL
(`gemini-3.8-vision-flash` default) and batch/CSV rows to GEMINI_FLASH_MODEL
(`gemini-3.8-vision-flash` default). Provides deterministic mock/fallback extraction
when GEMINI_API_KEY is unset so offline CI tests and demos never crash.

Live invoice extraction runs a 1-retry arithmetic self-correction loop: line-total
mismatches found by verify_extracted_line_totals are fed back to the model once at
temperature 0; warnings that persist keep the batch needs_review (fail closed).
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
You are a high-precision accounts-payable document extraction engine for an audit-grade financial system.
Extract ONLY fields literally visible in the document (PDF, scan, image, or CSV). NEVER guess, extrapolate, or invent missing values—return null for any unreadable or absent field.

Domain & Formatting Rules:
1. Dates: Normalize all dates (DD/MM/YYYY, DD-MMM-YYYY, YYYY/MM/DD, etc.) to strict ISO-8601 `YYYY-MM-DD`.
2. Currency: Output ISO-4217 3-letter codes (`INR`, `USD`, `EUR`, `GBP`). Map `₹`, `Rs.`, `Rs`, `INR` -> `INR`; `$`, `US$` -> `USD`; `€` -> `EUR`; `£` -> `GBP`.
3. Numbers & Indian Comma Grouping: Strip currency symbols and thousand separators (including Indian lakh/crore grouping like `1,23,456.00` -> `123456.00`). Return plain decimals.
4. Invoice & Revision Numbers: Preserve exact suffixes and revision markers (e.g., `INV-8821-R2`, `CN-104`, `PO-1006`)—never strip `-R2` or `/FY26` suffixes.
5. Tax & GST Handling:
   - Combine split Indian GST components (`CGST 9% + SGST 9%` -> `tax_pct: 18.0`; `IGST 18%` -> `tax_pct: 18.0`).
   - Do NOT treat TDS (Tax Deducted at Source) as invoice GST/tax or subtract TDS from `line_total` / `grand_total`.
   - If a line is explicitly tax-exempt / zero-rated (`0%`, `Exempt`, `Nil`), set `tax_pct: 0.0`.
6. Line Items & Multi-Page Tables:
   - Extract every billable line item in order (`line_no` 1..N). Ignore subtotals, page headers/footers, and bank-detail blocks.
   - Ignore HSN/SAC codes as item names; extract the actual item/service description into `item`.
   - If `unit_price` is pre-tax and `line_total` is post-tax, ensure `round(quantity * unit_price * (1 + tax_pct / 100), 2) == line_total`.
   - If `discount_pct` or `discount_applied_pct` is shown on the invoice or contract line, capture it accurately.
7. Cross-Document References: Capture `vendor_name`, `vendor_id` (if printed), `po_id` / PO number, `contract_id`, and `payment_status` / `credited` indicators verbatim when present.
8. Scan Quality: If a stamp, watermark, or low-DPI region obscures a number, return `null` rather than guessing so the fail-closed verifier flags `needs_review`.
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


MAX_ARITHMETIC_RETRIES = 1


def _client():
    return create_genai_client()


def _invoice_lines_for_verification(payload: ExtractedInvoicePayload) -> list[dict]:
    """Project payload lines into the dict shape verify_extracted_line_totals expects."""
    return [
        {
            "line_no": idx,
            "item": line.item,
            "quantity": line.quantity,
            "unit_price": line.unit_price,
            "tax_pct": line.tax_pct,
            "line_total": line.line_total,
        }
        for idx, line in enumerate(payload.lines, start=1)
    ]


def build_arithmetic_retry_feedback(warnings: list[dict], previous_json: dict) -> str:
    """Targeted retry prompt: exact mismatch warnings + the previous JSON payload."""
    mismatch_lines = [
        (
            f"Line {w.get('line_no')} ({w.get('item')}) expected "
            f"{float(w.get('expected_line_total') or 0.0):.2f} vs extracted "
            f"{float(w.get('actual_line_total') or 0.0):.2f}; re-read quantity, "
            f"unit_price, tax_pct, and line_total from the document"
        )
        for w in warnings
    ]
    return (
        "Arithmetic verification failed on your previous extraction. "
        "Re-read the document carefully and return corrected JSON.\n"
        "Mismatches (expected = round(quantity * unit_price * (1 + tax_pct / 100), 2)):\n"
        + "\n".join(f"- {line}" for line in mismatch_lines)
        + "\n\nPrevious JSON:\n"
        + json.dumps(previous_json, ensure_ascii=False)
    )


def _extract_invoice_payload_live(
    file_bytes: bytes,
    mime_type: str,
    model_name: str,
) -> tuple[ExtractedInvoicePayload, list[dict]]:
    """Live invoice extraction with at most 1 arithmetic self-correction retry.

    Fail-closed: mismatches that survive the retry are returned as warnings so
    the batch transitions to needs_review instead of trusting bad math.
    """
    raw = _generate_with_model(file_bytes, mime_type, ExtractedInvoicePayload, model_name)
    payload = ExtractedInvoicePayload.model_validate(raw)
    warnings = verify_extracted_line_totals(_invoice_lines_for_verification(payload))

    retries_left = MAX_ARITHMETIC_RETRIES
    while warnings and retries_left > 0 and has_live_ai_credentials():
        retries_left -= 1
        feedback = build_arithmetic_retry_feedback(warnings, payload.model_dump())
        retry_raw = _generate_with_model(
            file_bytes,
            mime_type,
            ExtractedInvoicePayload,
            model_name,
            retry_feedback=feedback,
        )
        retry_payload = ExtractedInvoicePayload.model_validate(retry_raw)
        warnings = verify_extracted_line_totals(_invoice_lines_for_verification(retry_payload))
        payload = retry_payload
    return payload, warnings


def _media_resolution_kwargs(types_module, mime_type: str) -> dict:
    """High-resolution hint for dense invoice tables on PDF/image inputs.

    Returns {} when the installed google-genai SDK (or a test mock) does not
    support media_resolution, so older SDK versions never break extraction.
    """
    if not (mime_type == "application/pdf" or mime_type.startswith("image/")):
        return {}
    try:
        config_cls = getattr(types_module, "GenerateContentConfig", None)
        if config_cls is None:
            return {}
        if "media_resolution" not in getattr(config_cls, "model_fields", {}):
            return {}
        enum_cls = getattr(types_module, "MediaResolution", None)
        high = getattr(enum_cls, "MEDIA_RESOLUTION_HIGH", None) if enum_cls is not None else None
        if high is None:
            return {}
        return {"media_resolution": high}
    except Exception:
        return {}


def _generate_with_model(
    file_bytes: bytes,
    mime_type: str,
    schema,
    model_name: str,
    retry_feedback: str | None = None,
    temperature: float = 0.0,
) -> dict:
    from google.genai import types  # lazy import

    contents = [types.Part.from_bytes(data=file_bytes, mime_type=mime_type)]
    if retry_feedback:
        contents.append(types.Part(text=retry_feedback))

    config_kwargs = {
        "system_instruction": EXTRACTION_SYSTEM_PROMPT,
        "temperature": temperature,
        "response_mime_type": "application/json",
        "response_schema": schema,
    }
    config_kwargs.update(_media_resolution_kwargs(types, mime_type))

    response = _client().models.generate_content(
        model=model_name,
        contents=contents,
        config=types.GenerateContentConfig(**config_kwargs),
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


_AMOUNT_CAPTURE = r"(-?\d[\d,]*(?:\.\d+)?)"


def _extract_amount_kv(text: str, patterns: tuple[str, ...]) -> float | None:
    """Extract a numeric field preserving Indian comma grouping (e.g. 1,23,456.00)."""
    for pat in patterns:
        m = re.search(pat, text, flags=re.IGNORECASE | re.MULTILINE)
        if m:
            return normalize_amount(m.group(1))
    return None


def _normalize_tax_pct(raw: str | None) -> float | None:
    """Normalize tax text to one effective tax percentage (mirrors prompt rules).

    - Combines split Indian GST components: 'CGST 9% + SGST 9%' -> 18.0.
    - Maps exempt / nil / zero-rated lines to 0.0.
    - Never sums TDS percentages into invoice GST (TDS is withheld at payment).
    - Returns None when no usable tax signal remains (caller applies default).
    """
    text = str(raw or "").strip()
    if not text:
        return None
    if re.search(r"\b(?:exempt|nil|zero[\s-]*rated)\b", text, flags=re.IGNORECASE):
        return 0.0
    # Drop TDS clauses (from 'TDS' to the next +/;/newline) before summing percentages.
    stripped = re.sub(r"tds\b[^+;\r\n]*", " ", text, flags=re.IGNORECASE)
    percents = re.findall(r"(\d+(?:\.\d+)?)\s*%", stripped)
    if percents:
        return round(sum(float(p) for p in percents), 2)
    bare = re.search(r"-?\d+(?:\.\d+)?", stripped)
    if bare:
        return round(float(bare.group()), 2)
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
    qty_f = _extract_amount_kv(text, (r"(?:quantity|qty)\s*[:\-]\s*" + _AMOUNT_CAPTURE,))
    unit_price_f = _extract_amount_kv(text, (r"unit\s*price\s*[:\-]\s*" + _AMOUNT_CAPTURE,))
    tax_s = _extract_kv(text, (r"tax(?:\s*%|_pct)?\s*[:\-]\s*([^;\r\n]+)",))
    total_f = _extract_amount_kv(text, (r"(?:line[_\s]*total|grand[_\s]*total|total)\s*[:\-]\s*" + _AMOUNT_CAPTURE,))

    stem_id = re.sub(r"[^A-Z0-9\-]", "", Path(source_name).stem.upper())[:20] or "SCAN-001"
    number = inv_no or f"INV-{stem_id}"
    vendor_clean = vendor_name or "Extracted PDF Vendor"
    norm_date = normalize_date(inv_date or "2026-11-15")
    norm_curr = normalize_currency(currency or "INR") or "INR"
    qty = qty_f if qty_f is not None else 1.0
    unit_price = unit_price_f if unit_price_f is not None else 1000.0
    tax_pct = _normalize_tax_pct(tax_s)
    if tax_pct is None:
        tax_pct = 18.0
    computed_total = round(qty * unit_price * (1.0 + tax_pct / 100.0), 2)
    line_total = total_f if total_f is not None else computed_total
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
    price_f = _extract_amount_kv(text, (r"(?:contracted[_\s]*)?unit[_\s]*price\s*[:\-]\s*" + _AMOUNT_CAPTURE,))
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
                unit_price=price_f if price_f is not None else 1000.0,
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
    qty_f = _extract_amount_kv(text, (r"(?:quantity|qty)\s*[:\-]\s*" + _AMOUNT_CAPTURE,))
    price_f = _extract_amount_kv(text, (r"unit\s*price\s*[:\-]\s*" + _AMOUNT_CAPTURE,))
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
                quantity=qty_f if qty_f is not None else 1.0,
                unit_price=price_f if price_f is not None else 1000.0,
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
        payload, warnings = _extract_invoice_payload_live(pdf_bytes, mime_type, model_name)
        data = payload.model_dump()
        data["mode"] = "gemini_live"
        data["model"] = model_name
        data["verification_warnings"] = warnings
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

    # Default: invoices PDF / scan (live path runs the 1-retry math repair loop)
    if has_live_ai_credentials():
        payload, _repair_warnings = _extract_invoice_payload_live(file_bytes, mime_type, model_name)
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

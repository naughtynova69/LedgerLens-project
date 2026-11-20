"""Tests for extraction pipeline, model routing, normalization, and math checks."""
from __future__ import annotations

import json
from io import BytesIO
from types import SimpleNamespace
from fastapi.testclient import TestClient
import pytest

from app import config
from app.extract import (
    EXTRACTION_SYSTEM_PROMPT,
    ExtractedInvoicePayload,
    extract_document,
    extract_invoice,
    select_extraction_model,
    verify_extracted_line_totals,
)
from app.extract import gemini_extract
from app.main import app
from app.normalize import (
    canonical_vendor_key,
    normalize_date,
    normalize_invoice_number,
)


def test_model_routing_primary_vs_flash():
    assert select_extraction_model("invoices", is_batch=False, mime_type="application/pdf") == config.GEMINI_PRIMARY_MODEL
    assert select_extraction_model("contracts", is_batch=False, mime_type="application/pdf") == config.GEMINI_PRIMARY_MODEL
    assert select_extraction_model("invoices", is_batch=True, mime_type="application/pdf") == config.GEMINI_FLASH_MODEL
    assert select_extraction_model("invoices", is_batch=False, mime_type="text/csv") == config.GEMINI_FLASH_MODEL


def test_normalization_helpers():
    assert canonical_vendor_key("SUNBEAM ELECTRICALS PVT. LTD.") == "sunbeam electricals"
    assert normalize_invoice_number("inv-8821 / r2") == "INV8821R2"
    assert normalize_date("14/10/2026") == "2026-10-14"
    assert normalize_date("2026-10-14") == "2026-10-14"
    assert normalize_date("14 Oct 2026") == "2026-10-14"


def test_verify_extracted_line_totals_flags_mismatch():
    clean = [{"line_no": 1, "item": "LED Panel", "quantity": 10, "unit_price": 420.0, "tax_pct": 18.0, "line_total": 4956.0}]
    assert verify_extracted_line_totals(clean) == []

    bad = [{"line_no": 1, "item": "LED Panel", "quantity": 10, "unit_price": 420.0, "tax_pct": 18.0, "line_total": 5500.0}]
    warnings = verify_extracted_line_totals(bad)
    assert len(warnings) == 1
    assert warnings[0]["expected_line_total"] == 4956.0
    assert warnings[0]["actual_line_total"] == 5500.0
    assert warnings[0]["delta"] == 544.0


def test_offline_pdf_mock_extract_produces_valid_schema(monkeypatch, tmp_path):
    monkeypatch.setattr(config, "GEMINI_API_KEY", "")
    pdf_like = tmp_path / "sample_inv.pdf"
    pdf_like.write_bytes(
        b"%PDF-1.4\n"
        b"Vendor: Sunbeam Electricals Pvt Ltd\n"
        b"Invoice Number: INV-PDF-101\n"
        b"Date: 15/11/2026\n"
        b"Currency: INR\n"
        b"Item: LED Panel 18W\n"
        b"Quantity: 2\n"
        b"Unit Price: 420.00\n"
        b"Tax %: 18\n"
        b"Line Total: 991.20\n"
    )
    res = extract_document(pdf_like, "invoices")
    assert res["mode"] == "mock_fallback"
    assert res["model"] == config.GEMINI_PRIMARY_MODEL
    assert res["needs_review"] is False
    assert res["verification_warnings"] == []
    assert len(res["records"]) == 1
    assert res["records"][0]["invoice_number"] == "INV-PDF-101"
    assert res["records"][0]["invoice_date"] == "2026-11-15"
    assert res["records"][0]["line_total"] == pytest.approx(991.20, 0.01)

    payload_dict = extract_invoice(pdf_like.read_bytes())
    validated = ExtractedInvoicePayload.model_validate(payload_dict)
    assert validated.invoice.number == "INV-PDF-101"


def test_csv_extract_normalizes_and_detects_math_mismatch(tmp_path):
    csv_path = tmp_path / "bad_math.csv"
    csv_path.write_text(
        "invoice_number,vendor_id,invoice_date,po_id,line_no,item,quantity,unit_price,currency,tax_pct,line_total,status\n"
        "INV-BAD-1,V001,15/11/2026,PO-1001,1,LED Panel,10,420.00,Rs.,18,6000.00,unpaid\n",
        encoding="utf-8",
    )
    res = extract_document(csv_path, "invoices")
    assert res["mode"] == "csv_deterministic"
    assert res["needs_review"] is True
    assert len(res["verification_warnings"]) == 1
    assert res["records"][0]["currency"] == "INR"
    assert res["records"][0]["invoice_date"] == "2026-11-15"


def test_api_upload_and_extract_endpoint_end_to_end(monkeypatch, tmp_path):
    db_file = tmp_path / "test_extract.db"
    upload_dir = tmp_path / "uploads"
    monkeypatch.setattr(config, "DB_PATH", str(db_file))
    monkeypatch.setattr(config, "UPLOAD_DIR", str(upload_dir))
    monkeypatch.setattr(config, "GEMINI_API_KEY", "")

    client = TestClient(app)
    pdf_bytes = (
        b"%PDF-1.4\n"
        b"Vendor: Acme Test Corp\n"
        b"Invoice Number: INV-API-99\n"
        b"Date: 2026-11-18\n"
        b"Currency: USD\n"
        b"Item: Widget A\n"
        b"Quantity: 5\n"
        b"Unit Price: 100.00\n"
        b"Tax %: 0\n"
        b"Line Total: 500.00\n"
    )
    up = client.post(
        "/api/ingest/upload",
        data={"kind": "invoices"},
        files={"file": ("inv99.pdf", BytesIO(pdf_bytes), "application/pdf")},
    )
    assert up.status_code == 200
    batch_id = up.json()["batch_id"]

    ext = client.post(f"/api/run/{batch_id}/extract")
    assert ext.status_code == 200
    body = ext.json()
    assert body["batch_id"] == batch_id
    assert body["state"] == "extracted"
    assert body["rows_extracted"] == 1
    assert body["mode"] == "mock_fallback"
    assert body["model"] == config.GEMINI_PRIMARY_MODEL

    logs = client.get("/api/audit-log").json()
    actions = [entry["action"] for entry in logs]
    assert "extract" in actions
    assert "ingest" in actions


def test_csv_upload_new_vendor_without_preseed_succeeds(monkeypatch, tmp_path):
    monkeypatch.setattr(config, "DB_PATH", str(tmp_path / "fresh_csv.db"))
    monkeypatch.setattr(config, "UPLOAD_DIR", str(tmp_path / "uploads"))
    client = TestClient(app)
    csv_bytes = (
        b"invoice_number,vendor_id,invoice_date,po_id,line_no,item,quantity,unit_price,currency,tax_pct,line_total,status\n"
        b"INV-NEW-1,V-NEW-99,2026-11-19,,1,Widget X,2,100.00,INR,18,236.00,unpaid\n"
    )
    res = client.post(
        "/api/ingest/upload",
        data={"kind": "invoices"},
        files={"file": ("new_vendor.csv", BytesIO(csv_bytes), "text/csv")},
    )
    assert res.status_code == 200
    assert res.json()["rows_detected"] == 1
    assert res.json()["problems"] == []


# ---------------------------------------------------------------------------
# Domain-tuned prompt contract (Indian B2B AP rules)
# ---------------------------------------------------------------------------

def test_extraction_system_prompt_domain_rules():
    assert "CGST 9% + SGST 9%" in EXTRACTION_SYSTEM_PROMPT
    assert "IGST 18%" in EXTRACTION_SYSTEM_PROMPT
    assert "TDS" in EXTRACTION_SYSTEM_PROMPT
    assert "1,23,456.00" in EXTRACTION_SYSTEM_PROMPT
    assert "ISO-8601" in EXTRACTION_SYSTEM_PROMPT
    assert "ISO-4217" in EXTRACTION_SYSTEM_PROMPT
    assert "-R2" in EXTRACTION_SYSTEM_PROMPT  # revision suffix preservation
    assert "needs_review" in EXTRACTION_SYSTEM_PROMPT  # scan-quality fail-closed rule
    assert "NEVER guess" in EXTRACTION_SYSTEM_PROMPT


# ---------------------------------------------------------------------------
# Offline mock fallback: Indian GST + Indian comma grouping + revision suffixes
# ---------------------------------------------------------------------------

def test_offline_mock_combines_split_gst_and_indian_commas(monkeypatch, tmp_path):
    monkeypatch.setattr(config, "GEMINI_API_KEY", "")
    pdf_like = tmp_path / "inv_gst.pdf"
    pdf_like.write_bytes(
        b"%PDF-1.4\n"
        b"Vendor: Sunbeam Electricals Pvt Ltd\n"
        b"Invoice Number: INV-8821-R2\n"
        b"Date: 15/11/2026\n"
        b"Currency: Rs.\n"
        b"Item: Industrial LED Panel\n"
        b"Quantity: 2\n"
        b"Unit Price: 1,23,456.00\n"
        b"Tax: CGST 9% + SGST 9%\n"
        b"Line Total: 2,91,356.16\n"
    )
    res = extract_document(pdf_like, "invoices")
    assert res["mode"] == "mock_fallback"
    assert res["needs_review"] is False
    assert res["verification_warnings"] == []
    rec = res["records"][0]
    assert rec["invoice_number"] == "INV-8821-R2"  # revision suffix preserved
    assert rec["invoice_date"] == "2026-11-15"
    assert rec["currency"] == "INR"
    assert rec["tax_pct"] == pytest.approx(18.0)  # CGST 9% + SGST 9% combined
    assert rec["unit_price"] == pytest.approx(123456.0)  # 1,23,456.00
    assert rec["line_total"] == pytest.approx(291356.16)  # 2,91,356.16


def test_offline_mock_tax_exempt_zero_rated(monkeypatch, tmp_path):
    monkeypatch.setattr(config, "GEMINI_API_KEY", "")
    pdf_like = tmp_path / "inv_exempt.pdf"
    pdf_like.write_bytes(
        b"%PDF-1.4\n"
        b"Vendor: Zero Rated Supplies Ltd\n"
        b"Invoice Number: INV-EX-1\n"
        b"Date: 2026-11-15\n"
        b"Currency: INR\n"
        b"Item: Export Service\n"
        b"Quantity: 3\n"
        b"Unit Price: 500.00\n"
        b"Tax: Exempt\n"
        b"Line Total: 1500.00\n"
    )
    res = extract_document(pdf_like, "invoices")
    assert res["mode"] == "mock_fallback"
    assert res["records"][0]["tax_pct"] == pytest.approx(0.0)
    assert res["needs_review"] is False


def test_offline_mock_ignores_tds_in_tax_pct(monkeypatch, tmp_path):
    monkeypatch.setattr(config, "GEMINI_API_KEY", "")
    pdf_like = tmp_path / "inv_tds.pdf"
    pdf_like.write_bytes(
        b"%PDF-1.4\n"
        b"Vendor: TDS Vendor Pvt Ltd\n"
        b"Invoice Number: INV-TDS-1\n"
        b"Date: 2026-11-15\n"
        b"Currency: INR\n"
        b"Item: Consulting Service\n"
        b"Quantity: 1\n"
        b"Unit Price: 1000.00\n"
        b"Tax: CGST 9% + SGST 9% (TDS 2% withheld)\n"
        b"Line Total: 1180.00\n"
    )
    res = extract_document(pdf_like, "invoices")
    assert res["mode"] == "mock_fallback"
    assert res["records"][0]["tax_pct"] == pytest.approx(18.0)  # TDS never summed into GST
    assert res["needs_review"] is False


def test_zero_key_fallback_never_calls_gemini(monkeypatch, tmp_path):
    monkeypatch.setattr(config, "GEMINI_API_KEY", "")

    def _forbidden(*args, **kwargs):
        raise AssertionError("_generate_with_model must never run without credentials")

    monkeypatch.setattr(gemini_extract, "_generate_with_model", _forbidden)
    pdf_like = tmp_path / "inv_offline.pdf"
    pdf_like.write_bytes(
        b"%PDF-1.4\n"
        b"Vendor: Offline Corp\n"
        b"Invoice Number: INV-OFF-1\n"
        b"Date: 2026-11-15\n"
        b"Currency: INR\n"
        b"Item: Widget\n"
        b"Quantity: 2\n"
        b"Unit Price: 100.00\n"
        b"Tax %: 18\n"
        b"Line Total: 236.00\n"
    )
    res = extract_document(pdf_like, "invoices")
    assert res["mode"] == "mock_fallback"
    assert res["records"][0]["invoice_number"] == "INV-OFF-1"


# ---------------------------------------------------------------------------
# Media resolution hint (guarded for older SDK versions / mocks)
# ---------------------------------------------------------------------------

def test_media_resolution_hint_guarded_for_old_sdks():
    fake_types = SimpleNamespace(
        GenerateContentConfig=SimpleNamespace(model_fields={"media_resolution": None}),
        MediaResolution=SimpleNamespace(MEDIA_RESOLUTION_HIGH="MEDIA_RESOLUTION_HIGH"),
    )
    assert gemini_extract._media_resolution_kwargs(fake_types, "application/pdf") == {
        "media_resolution": "MEDIA_RESOLUTION_HIGH"
    }
    assert gemini_extract._media_resolution_kwargs(fake_types, "image/png") == {
        "media_resolution": "MEDIA_RESOLUTION_HIGH"
    }
    assert gemini_extract._media_resolution_kwargs(fake_types, "text/csv") == {}

    # Older SDK: no media_resolution field on GenerateContentConfig
    old_types = SimpleNamespace(
        GenerateContentConfig=SimpleNamespace(model_fields={}),
        MediaResolution=SimpleNamespace(MEDIA_RESOLUTION_HIGH="MEDIA_RESOLUTION_HIGH"),
    )
    assert gemini_extract._media_resolution_kwargs(old_types, "application/pdf") == {}

    # Enum missing entirely
    bare_types = SimpleNamespace(GenerateContentConfig=SimpleNamespace(model_fields={"media_resolution": None}))
    assert gemini_extract._media_resolution_kwargs(bare_types, "application/pdf") == {}


def test_generate_with_model_passes_media_resolution_for_pdf(monkeypatch):
    pytest.importorskip("google.genai")
    from google.genai import types as genai_types

    captured = {}

    class FakeModels:
        def generate_content(self, **kwargs):
            captured.update(kwargs)
            return SimpleNamespace(text=json.dumps(_live_invoice_payload(4956.0)))

    monkeypatch.setattr(gemini_extract, "_client", lambda: SimpleNamespace(models=FakeModels()))
    raw = gemini_extract._generate_with_model(
        b"%PDF-1.4", "application/pdf", ExtractedInvoicePayload, config.GEMINI_PRIMARY_MODEL
    )
    assert raw["invoice"]["number"] == "INV-8821-R2"
    assert captured["config"].media_resolution == genai_types.MediaResolution.MEDIA_RESOLUTION_HIGH
    assert captured["config"].temperature == 0

    # CSV route never gets a media-resolution hint
    captured.clear()
    gemini_extract._generate_with_model(
        b"a,b\n1,2\n", "text/csv", ExtractedInvoicePayload, config.GEMINI_FLASH_MODEL
    )
    assert captured["config"].media_resolution is None


# ---------------------------------------------------------------------------
# Live 1-retry arithmetic self-correction
# ---------------------------------------------------------------------------

def _live_invoice_payload(line_total: float, grand_total: float | None = None) -> dict:
    total = grand_total if grand_total is not None else line_total
    return {
        "vendor": {"name": "Sunbeam Electricals Pvt Ltd", "tax_id": None},
        "invoice": {
            "number": "INV-8821-R2",
            "date": "2026-11-15",
            "currency": "INR",
            "po_reference": "PO-1006",
            "payment_terms": "Net 30",
        },
        "lines": [
            {
                "item": "LED Panel 18W",
                "quantity": 10.0,
                "unit_price": 420.0,
                "tax_pct": 18.0,
                "line_total": line_total,
            }
        ],
        "totals": {"subtotal": 4200.0, "tax": 756.0, "grand_total": total},
    }


def test_arithmetic_retry_feedback_format():
    bad = [{"line_no": 1, "item": "LED Panel", "quantity": 10, "unit_price": 420.0, "tax_pct": 18.0, "line_total": 5500.0}]
    warnings = verify_extracted_line_totals(bad)
    assert len(warnings) == 1
    feedback = gemini_extract.build_arithmetic_retry_feedback(warnings, {"lines": bad})
    assert "Line 1 (LED Panel) expected 4956.00 vs extracted 5500.00" in feedback
    assert "re-read quantity, unit_price, tax_pct, and line_total" in feedback
    assert "Previous JSON" in feedback


def test_live_retry_repairs_arithmetic_mismatch(monkeypatch, tmp_path):
    monkeypatch.setattr(config, "GEMINI_API_KEY", "test-key")
    monkeypatch.setattr(gemini_extract, "has_live_ai_credentials", lambda: True)
    calls: list[str | None] = []

    def fake_generate(file_bytes, mime_type, schema, model_name, retry_feedback=None, temperature=0.0):
        calls.append(retry_feedback)
        if len(calls) == 1:
            return _live_invoice_payload(5500.0)  # bad math on first pass
        return _live_invoice_payload(4956.0)  # repaired on the targeted retry

    monkeypatch.setattr(gemini_extract, "_generate_with_model", fake_generate)
    pdf_like = tmp_path / "inv_retry.pdf"
    pdf_like.write_bytes(b"%PDF-1.4 fake invoice scan")

    res = extract_document(pdf_like, "invoices")
    assert res["mode"] == "gemini_live"
    assert len(calls) == 2  # initial call + exactly 1 targeted retry
    assert calls[0] is None
    assert calls[1] is not None
    assert "expected 4956.00 vs extracted 5500.00" in calls[1]
    assert "Previous JSON" in calls[1]
    assert res["verification_warnings"] == []
    assert res["needs_review"] is False
    assert res["records"][0]["line_total"] == pytest.approx(4956.0)


def test_live_retry_stops_after_one_attempt_when_math_still_wrong(monkeypatch, tmp_path):
    monkeypatch.setattr(config, "GEMINI_API_KEY", "test-key")
    monkeypatch.setattr(gemini_extract, "has_live_ai_credentials", lambda: True)
    calls: list[str | None] = []

    def fake_generate(file_bytes, mime_type, schema, model_name, retry_feedback=None, temperature=0.0):
        calls.append(retry_feedback)
        return _live_invoice_payload(5500.0)  # bad math persists

    monkeypatch.setattr(gemini_extract, "_generate_with_model", fake_generate)
    pdf_like = tmp_path / "inv_stuck.pdf"
    pdf_like.write_bytes(b"%PDF-1.4 fake invoice scan")

    res = extract_document(pdf_like, "invoices")
    assert res["mode"] == "gemini_live"
    assert len(calls) == 2  # initial + 1 retry, then stop (never loops forever)
    assert calls[1] is not None
    assert res["needs_review"] is True  # fail closed
    assert len(res["verification_warnings"]) == 1
    assert res["verification_warnings"][0]["expected_line_total"] == pytest.approx(4956.0)
    assert res["records"][0]["line_total"] == pytest.approx(5500.0)


def test_extract_invoice_live_returns_verification_warnings(monkeypatch):
    monkeypatch.setattr(config, "GEMINI_API_KEY", "test-key")
    monkeypatch.setattr(gemini_extract, "has_live_ai_credentials", lambda: True)

    def fake_generate(file_bytes, mime_type, schema, model_name, retry_feedback=None, temperature=0.0):
        return _live_invoice_payload(5500.0)  # bad math, no repair possible (stub ignores retry)

    monkeypatch.setattr(gemini_extract, "_generate_with_model", fake_generate)
    extracted = extract_invoice(b"%PDF-1.4", mime_type="application/pdf")
    assert extracted["mode"] == "gemini_live"
    assert len(extracted["verification_warnings"]) == 1
    # pydantic re-validation ignores the extra verification_warnings key
    payload = ExtractedInvoicePayload.model_validate(extracted)
    assert payload.invoice.number == "INV-8821-R2"

"""Tests for extraction pipeline, model routing, normalization, and math checks."""
from __future__ import annotations

from io import BytesIO
from fastapi.testclient import TestClient
import pytest

from app import config
from app.extract import (
    ExtractedInvoicePayload,
    extract_document,
    extract_invoice,
    select_extraction_model,
    verify_extracted_line_totals,
)
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

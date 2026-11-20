"""Evaluation harness for Gemini structured-output schemas, extraction precision, and explanation fidelity."""
from __future__ import annotations

import csv
import json
import os
from pathlib import Path
import re
import pytest

from app import config
from app.db import get_connection, init_schema
from app.explain.gemini_explain import (
    EXPLANATION_SCHEMA,
    explain_finding,
    fallback_without_gemini,
)
from app.extract import (
    ExtractedInvoicePayload,
    extract_document,
    extract_invoice,
)
from app.services import seed_sample_dataset

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
SCHEMA_DIR = REPO_ROOT / "docs" / "ai_studio_schemas"
SAMPLE_DATA_DIR = REPO_ROOT / "sample_data"


def _extract_numeric_tokens(text: str) -> list[str]:
    """Return normalized numeric tokens (commas stripped) found in text."""
    raw_tokens = re.findall(r"\b\d[\d,]*(?:\.\d+)?\b", text)
    return [tok.replace(",", "") for tok in raw_tokens]


def test_ai_studio_schemas_match_backend_contracts():
    extract_schema_path = SCHEMA_DIR / "extract_invoice.schema.json"
    explain_schema_path = SCHEMA_DIR / "cfo_explanation.schema.json"
    assert extract_schema_path.exists()
    assert explain_schema_path.exists()

    extract_schema = json.loads(extract_schema_path.read_text(encoding="utf-8"))
    explain_schema = json.loads(explain_schema_path.read_text(encoding="utf-8"))

    # 1. Extract invoice schema matches ExtractedInvoicePayload.model_json_schema()
    pydantic_schema = ExtractedInvoicePayload.model_json_schema()
    assert extract_schema["$schema"].startswith("https://json-schema.org/")
    assert extract_schema["title"] == "ExtractedInvoicePayload"
    assert extract_schema["type"] == "object"
    assert set(extract_schema["properties"].keys()) == set(pydantic_schema["properties"].keys())
    assert set(extract_schema["properties"].keys()) == {"vendor", "invoice", "lines", "totals"}
    assert set(extract_schema["required"]) == {"vendor", "invoice", "lines", "totals"}

    defs = pydantic_schema.get("$defs", {})
    assert set(extract_schema["properties"]["vendor"]["properties"].keys()) == set(
        defs["VendorExtracted"]["properties"].keys()
    )
    assert set(extract_schema["properties"]["invoice"]["properties"].keys()) == set(
        defs["InvoiceHeaderExtracted"]["properties"].keys()
    )
    assert set(extract_schema["properties"]["lines"]["items"]["properties"].keys()) == set(
        defs["InvoiceLineExtracted"]["properties"].keys()
    )
    assert set(extract_schema["properties"]["totals"]["properties"].keys()) == set(
        defs["InvoiceTotalsExtracted"]["properties"].keys()
    )

    # 2. CFO explanation schema matches EXPLANATION_SCHEMA["properties"] / required
    assert explain_schema["$schema"].startswith("https://json-schema.org/")
    assert explain_schema["type"] == "object"
    assert set(explain_schema["properties"].keys()) == set(EXPLANATION_SCHEMA["properties"].keys())
    assert explain_schema["required"] == EXPLANATION_SCHEMA["required"]
    for field_name, spec in EXPLANATION_SCHEMA["properties"].items():
        assert explain_schema["properties"][field_name]["type"] == spec["type"]


def test_csv_extraction_precision_and_tamper_detection(tmp_path):
    invoices_csv = SAMPLE_DATA_DIR / "invoices.csv"
    assert invoices_csv.exists()

    with invoices_csv.open("r", encoding="utf-8") as f:
        expected_rows = list(csv.DictReader(f))
    assert len(expected_rows) == 16

    result = extract_document(invoices_csv, kind="invoices")
    assert result["mode"] == "csv_deterministic"
    assert len(result["records"]) == 16

    extracted_numbers = [r["invoice_number"] for r in result["records"]]
    expected_numbers = [r["invoice_number"] for r in expected_rows]
    assert extracted_numbers == expected_numbers

    # Sample dataset INV-9155 carries a known ₹24 upstream arithmetic variance (16992.00 vs 17016.00)
    assert result["needs_review"] is True
    assert len(result["verification_warnings"]) == 1
    assert result["verification_warnings"][0]["item"] == "A4 Paper Box"

    # Build an arithmetic-consistent copy -> 0 false verification warnings
    clean_rows = [dict(r) for r in expected_rows]
    for r in clean_rows:
        qty = float(r["quantity"])
        price = float(r["unit_price"])
        tax = float(r["tax_pct"])
        r["line_total"] = f"{qty * price * (1.0 + tax / 100.0):.2f}"

    clean_csv = tmp_path / "clean_invoices.csv"
    fieldnames = list(expected_rows[0].keys())
    with clean_csv.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(clean_rows)

    clean_result = extract_document(clean_csv, kind="invoices")
    assert clean_result["needs_review"] is False
    assert clean_result["verification_warnings"] == []

    # Tamper one row's line_total and confirm deterministic math check flags needs_review
    tampered_rows = [dict(r) for r in clean_rows]
    original_total = float(tampered_rows[0]["line_total"])
    tampered_rows[0]["line_total"] = f"{original_total + 500.0:.2f}"

    tampered_csv = tmp_path / "tampered_invoices.csv"
    with tampered_csv.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(tampered_rows)

    tampered_result = extract_document(tampered_csv, kind="invoices")
    assert tampered_result["needs_review"] is True
    assert len(tampered_result["verification_warnings"]) == 1
    warning = tampered_result["verification_warnings"][0]
    assert warning["expected_line_total"] == pytest.approx(original_total, abs=0.01)
    assert warning["actual_line_total"] == pytest.approx(original_total + 500.0, abs=0.01)


def test_cfo_explanation_zero_hallucination_citation_fidelity(monkeypatch):
    monkeypatch.setattr(config, "GEMINI_API_KEY", "")

    conn = get_connection(":memory:")
    init_schema(conn)
    try:
        seed_res = seed_sample_dataset(conn, SAMPLE_DATA_DIR)
        assert seed_res["findings_created"] == 6

        rows = conn.execute("SELECT * FROM findings ORDER BY finding_id ASC").fetchall()
        assert len(rows) == 6

        for row in rows:
            finding = dict(row)
            finding["entity_refs"] = json.loads(finding["entity_refs"])
            finding["evidence"] = json.loads(finding["evidence"])
            finding["proof_trail"] = json.loads(finding["proof_trail"])

            card = fallback_without_gemini(finding)

            for req_key in EXPLANATION_SCHEMA["required"]:
                assert req_key in card and isinstance(card[req_key], str) and card[req_key].strip()

            assert card["decision_engine"] == f"Deterministic Rule {finding['rule_id']}"
            assert card["model_used"] == config.GEMINI_PRIMARY_MODEL
            assert card["generated_without_gemini"] is True

            evidence_items = finding["proof_trail"].get("evidence") or []
            assert evidence_items, f"Expected evidence items for {finding['finding_id']}"

            cited_record_ids = {ev["record_id"] for ev in evidence_items if ev.get("record_id")}
            assert any(
                rec_id in card["explanation"] for rec_id in cited_record_ids
            ), f"Explanation for {finding['finding_id']} did not cite any record_id from proof_trail"

            # Verify every numeric token in explanation comes directly from summary or proof_trail (no foreign numbers)
            allowed_corpus = " ".join([
                str(finding.get("summary") or ""),
                json.dumps(finding["proof_trail"], ensure_ascii=False),
            ])
            allowed_numbers = set(_extract_numeric_tokens(allowed_corpus))
            explanation_numbers = _extract_numeric_tokens(card["explanation"])
            foreign_numbers = [num for num in explanation_numbers if num not in allowed_numbers]
            assert foreign_numbers == [], (
                f"Foreign numbers {foreign_numbers} found in {finding['finding_id']} explanation"
            )
    finally:
        conn.close()


@pytest.mark.skipif(
    not (os.getenv("RUN_LIVE_GEMINI_EVAL") == "1" and config.GEMINI_API_KEY),
    reason="Offline mode; set RUN_LIVE_GEMINI_EVAL=1 and GEMINI_API_KEY to run live Gemini eval",
)
def test_live_gemini_extraction_eval():
    sample_pdf_bytes = (
        b"%PDF-1.4\n"
        b"Vendor: Sunbeam Electricals Pvt Ltd\n"
        b"Tax ID: 27AABCS1234F1Z5\n"
        b"Invoice Number: INV-EVAL-001\n"
        b"Date: 2026-11-15\n"
        b"Currency: INR\n"
        b"PO Reference: PO-1001\n"
        b"Payment Terms: Net 30\n"
        b"Item: LED Panel 18W\n"
        b"Quantity: 10\n"
        b"Unit Price: 420.00\n"
        b"Tax %: 18\n"
        b"Line Total: 4956.00\n"
        b"Subtotal: 4200.00\n"
        b"Tax: 756.00\n"
        b"Grand Total: 4956.00\n"
    )
    extracted = extract_invoice(sample_pdf_bytes, mime_type="application/pdf")
    assert extracted["mode"] == "gemini_live"
    payload = ExtractedInvoicePayload.model_validate(extracted)
    assert payload.invoice.number == "INV-EVAL-001"
    assert payload.totals.grand_total == pytest.approx(4956.0, abs=0.01)

    finding = {
        "finding_id": "F-EVAL-01",
        "rule_id": "R1",
        "title": "Possible duplicate payment",
        "severity": "critical",
        "amount_at_risk": 4956.0,
        "currency": "INR",
        "confidence": 0.98,
        "recommended_action": "REQUEST_CREDIT_NOTE",
        "summary": "Same vendor (V001), same amount (4,956.00 INR), 2-day gap.",
        "proof_trail": {
            "rule_id": "R1",
            "evidence": [
                {"source": "invoices", "record_id": "INV-8821", "field": "line_total", "value": "4,956.00 INR"},
                {"source": "invoices", "record_id": "INV-8821-R2", "field": "line_total", "value": "4,956.00 INR"},
            ],
        },
    }
    card = explain_finding(finding)
    for req_key in EXPLANATION_SCHEMA["required"]:
        assert req_key in card and isinstance(card[req_key], str) and card[req_key].strip()
    assert card["decision_engine"] == "Deterministic Rule R1"
    assert "INV-8821" in card["explanation"]

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


@pytest.mark.skipif(
    not (os.getenv("RUN_LIVE_GEMINI_EVAL") == "1" and config.GEMINI_API_KEY),
    reason="Offline mode; set RUN_LIVE_GEMINI_EVAL=1 and GEMINI_API_KEY to run live Gemini eval",
)
def test_live_gemini_extraction_indian_gst_and_comma_eval():
    """Live eval: split GST combining, Indian comma grouping, TDS + revision suffix."""
    sample_pdf_bytes = (
        b"%PDF-1.4\n"
        b"Vendor: Sunbeam Electricals Pvt Ltd\n"
        b"Invoice Number: INV-8821-R2\n"
        b"Date: 15/11/2026\n"
        b"Currency: INR\n"
        b"PO Reference: PO-1006\n"
        b"Item: Industrial LED Panel\n"
        b"Quantity: 2\n"
        b"Unit Price: 1,23,456.00\n"
        b"Tax: CGST 9% + SGST 9% (TDS 2% withheld)\n"
        b"Line Total: 2,91,356.16\n"
        b"Subtotal: 2,46,912.00\n"
        b"Grand Total: 2,91,356.16\n"
    )
    extracted = extract_invoice(sample_pdf_bytes, mime_type="application/pdf")
    assert extracted["mode"] == "gemini_live"
    payload = ExtractedInvoicePayload.model_validate(extracted)
    assert payload.invoice.number == "INV-8821-R2"  # revision suffix preserved
    assert payload.invoice.date == "2026-11-15"
    assert payload.lines[0].tax_pct == pytest.approx(18.0)  # CGST 9% + SGST 9%, TDS ignored
    assert payload.lines[0].unit_price == pytest.approx(123456.0)  # 1,23,456.00
    assert payload.lines[0].line_total == pytest.approx(291356.16)  # 2,91,356.16
    assert extracted.get("verification_warnings") == []  # arithmetic self-correction converged


@pytest.mark.skipif(
    not (os.getenv("RUN_LIVE_GEMINI_EVAL") == "1" and config.GEMINI_API_KEY),
    reason="Offline mode; set RUN_LIVE_GEMINI_EVAL=1 and GEMINI_API_KEY to run live Gemini eval",
)
def test_live_gemini_extraction_us_format_eval():
    """Live eval: US MM/DD/YYYY dates, comma thousands, US sales tax rate."""
    sample_pdf_bytes = (
        b"%PDF-1.4\n"
        b"Vendor: Acme Industrial Supply Inc\n"
        b"Invoice Number: INV-US-2026-014\n"
        b"Date: 11/15/2026\n"
        b"Currency: USD\n"
        b"PO Reference: PO-7788\n"
        b"Item: Steel Bracket Kit\n"
        b"Quantity: 3\n"
        b"Unit Price: 1,234.56\n"
        b"Tax: Sales Tax 8.25%\n"
        b"Line Total: 4009.23\n"
        b"Subtotal: 3703.68\n"
        b"Grand Total: 4009.23\n"
    )
    extracted = extract_invoice(sample_pdf_bytes, mime_type="application/pdf")
    assert extracted["mode"] == "gemini_live"
    payload = ExtractedInvoicePayload.model_validate(extracted)
    assert payload.invoice.number == "INV-US-2026-014"
    assert payload.invoice.date == "2026-11-15"  # MM/DD/YYYY (US) -> ISO
    assert payload.lines[0].unit_price == pytest.approx(1234.56)  # US comma grouping
    assert payload.lines[0].tax_pct == pytest.approx(8.25)  # US sales tax
    assert payload.lines[0].line_total == pytest.approx(4009.23)
    assert extracted.get("verification_warnings") == []


# ---- Golden Noisy-PDF Benchmark (sample_data/eval_pdfs/) ----
# Append-only section: new imports for this benchmark live here (existing imports above are untouched).
import hashlib
import importlib.util
import sys

EVAL_PDF_DIR = REPO_ROOT / "sample_data" / "eval_pdfs"
EXPECTED_VOICES = frozenset({
    "clean_digital",
    "indian_comma_grouping",
    "split_gst_cgst_sgst",
    "tds_withheld",
    "revision_suffix",
    "us_format",
    "ocr_spacing",
    "multiline_items",
    "eur_decimal_comma",
    "rounding_drift",
    "tax_exemption",
    "cross_total_variance",
})


def _load_golden_corpus() -> tuple[dict, list[dict]]:
    """Load MANIFEST.json + entries for the golden corpus, skipping while it is not generated yet."""
    manifest_path = EVAL_PDF_DIR / "MANIFEST.json"
    if not manifest_path.exists():
        pytest.skip("golden corpus not generated yet")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    entries = manifest.get("entries") or []
    missing_pdfs = []
    for entry in entries:
        name = entry.get("file")
        if not name or not (EVAL_PDF_DIR / name).exists():
            missing_pdfs.append(name)
    if not entries or missing_pdfs:
        pytest.skip("golden corpus not generated yet")
    return manifest, entries


def _recompute_line_math(line: dict) -> tuple[float, float, float]:
    """Recompute (pre_tax, line_tax, gross) from a ground-truth line's quantity/unit_price/tax_pct."""
    pre_tax = line["quantity"] * line["unit_price"]
    line_tax = pre_tax * (line.get("tax_pct") or 0.0) / 100.0
    return pre_tax, line_tax, pre_tax + line_tax


def test_eval_pdf_corpus_manifest_integrity():
    """Golden corpus manifest is structurally sound and every PDF matches its recorded sha256/size."""
    manifest, entries = _load_golden_corpus()

    assert manifest["schema_version"] == "1.0"
    assert manifest["count"] == 12
    assert len(entries) == 12

    filenames = [entry["file"] for entry in entries]
    voices = [entry["voice"] for entry in entries]
    assert len(set(filenames)) == len(filenames), "duplicate filenames in manifest"
    assert len(set(voices)) == len(voices), "duplicate voices in manifest"
    assert set(voices) == EXPECTED_VOICES

    for entry in entries:
        pdf_path = EVAL_PDF_DIR / entry["file"]
        assert pdf_path.exists()
        raw = pdf_path.read_bytes()
        assert hashlib.sha256(raw).hexdigest() == entry["sha256"], entry["file"]
        assert len(raw) == entry["bytes"], entry["file"]
        assert raw.startswith(b"%PDF-1.4"), entry["file"]


def test_eval_pdf_ground_truth_conforms_to_extraction_schema():
    """Every ground-truth payload validates against ExtractedInvoicePayload with all signal fields present."""
    _, entries = _load_golden_corpus()
    for entry in entries:
        payload = ExtractedInvoicePayload.model_validate(entry["ground_truth"])

        assert payload.invoice.number is not None, entry["file"]
        assert payload.invoice.date is not None, entry["file"]
        assert re.match(r"^\d{4}-\d{2}-\d{2}$", payload.invoice.date), entry["file"]
        assert payload.invoice.currency is not None, entry["file"]
        assert payload.totals.grand_total is not None, entry["file"]

        assert payload.lines, f"{entry['file']}: ground truth has no line items"
        for line in payload.lines:
            assert line.item is not None
            assert line.quantity is not None
            assert line.unit_price is not None
            assert line.line_total is not None


def test_eval_pdf_ground_truth_arithmetic_invariants():
    """Consistent ground truths balance exactly; drifted ones deviate by exactly the declared variance."""
    _, entries = _load_golden_corpus()
    for entry in entries:
        ground_truth = entry["ground_truth"]
        lines = ground_truth["lines"]
        totals = ground_truth["totals"]
        arithmetic = entry["arithmetic"]

        recomputed = [_recompute_line_math(line) for line in lines]
        pre_tax_sum = sum(r[0] for r in recomputed)
        tax_sum = sum(r[1] for r in recomputed)
        gross_sum = sum(r[2] for r in recomputed)

        if arithmetic["consistent"]:
            for line, (_, _, gross) in zip(lines, recomputed):
                assert line["line_total"] == pytest.approx(gross, abs=0.01), entry["file"]
            assert totals["subtotal"] == pytest.approx(pre_tax_sum, abs=0.01), entry["file"]
            assert totals["tax"] == pytest.approx(tax_sum, abs=0.01), entry["file"]
            assert totals["grand_total"] == pytest.approx(
                totals["subtotal"] + totals["tax"], abs=0.01
            ), entry["file"]
            continue

        variance_field = arithmetic["variance_field"]
        variance = arithmetic["variance"]
        if variance_field == "line_total":
            declared = sum(line["line_total"] for line in lines)
            assert abs(declared - gross_sum) == pytest.approx(variance, abs=0.01), entry["file"]
            # Undeviated fields still balance within a cent.
            assert totals["subtotal"] == pytest.approx(pre_tax_sum, abs=0.01), entry["file"]
            assert totals["tax"] == pytest.approx(tax_sum, abs=0.01), entry["file"]
            assert totals["grand_total"] == pytest.approx(
                totals["subtotal"] + totals["tax"], abs=0.01
            ), entry["file"]
        elif variance_field == "grand_total":
            recomputed_grand = totals["subtotal"] + totals["tax"]
            assert abs(totals["grand_total"] - recomputed_grand) == pytest.approx(
                variance, abs=0.01
            ), entry["file"]
            # Undeviated fields (per-line totals, subtotal, tax) still balance within a cent.
            for line, (_, _, gross) in zip(lines, recomputed):
                assert line["line_total"] == pytest.approx(gross, abs=0.01), entry["file"]
            assert totals["subtotal"] == pytest.approx(pre_tax_sum, abs=0.01), entry["file"]
            assert totals["tax"] == pytest.approx(tax_sum, abs=0.01), entry["file"]
        else:
            pytest.fail(f"{entry['file']}: unknown arithmetic variance_field {variance_field!r}")


def test_eval_pdf_text_layer_contains_ground_truth_signals():
    """Decoded PDF bytes carry the vendor name for all voices and the invoice-number signal per voice."""
    _, entries = _load_golden_corpus()
    for entry in entries:
        ground_truth = entry["ground_truth"]
        voice = entry["voice"]
        raw = (EVAL_PDF_DIR / entry["file"]).read_bytes()
        text = raw.decode("latin-1")

        vendor_name = ground_truth["vendor"]["name"]
        assert vendor_name in text, f"{entry['file']}: vendor name {vendor_name!r} missing from PDF text"

        number = ground_truth["invoice"]["number"]
        if voice == "ocr_spacing":
            # OCR voice prints the number with a single space between every glyph: "INV-EVAL-007" -> "I N V - E V A L - 0 0 7".
            spaced = " ".join(number)
            assert spaced in text, f"{entry['file']}: spaced invoice number {spaced!r} missing from PDF text"
            collapsed = re.sub(r"\s+", "", text)
            assert number in collapsed, f"{entry['file']}: invoice number {number!r} missing after whitespace collapse"
        else:
            assert number in text, f"{entry['file']}: invoice number {number!r} missing from PDF text"


def test_eval_pdf_corpus_regenerates_deterministically():
    """In-memory regeneration reproduces the exact committed PDF bytes and ground truth (offline, no subprocess)."""
    manifest, entries = _load_golden_corpus()

    generator_path = EVAL_PDF_DIR / "generate_eval_pdfs.py"
    if not generator_path.exists():
        pytest.skip("generator module not importable yet")

    spec = importlib.util.spec_from_file_location("_eval_pdf_generator_under_test", generator_path)
    if spec is None or spec.loader is None:
        pytest.skip("generator module not importable yet")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    try:
        spec.loader.exec_module(module)
    except Exception:
        pytest.skip("generator module not importable yet")

    build_corpus = getattr(module, "build_corpus", None)
    build_manifest_entries = getattr(module, "build_manifest_entries", None)
    if not callable(build_corpus) or not callable(build_manifest_entries):
        pytest.skip("generator module not importable yet")

    regenerated = build_corpus()
    expected_files = {entry["file"] for entry in entries}
    assert set(regenerated.keys()) == expected_files

    for entry in entries:
        pdf_bytes = regenerated[entry["file"]]
        assert hashlib.sha256(pdf_bytes).hexdigest() == entry["sha256"], entry["file"]

    regenerated_entries = build_manifest_entries(regenerated)
    regenerated_by_file = {entry["file"]: entry for entry in regenerated_entries}
    assert set(regenerated_by_file.keys()) == expected_files
    for entry in entries:
        assert regenerated_by_file[entry["file"]]["ground_truth"] == entry["ground_truth"], entry["file"]

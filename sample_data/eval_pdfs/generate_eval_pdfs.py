#!/usr/bin/env python3
"""Golden Noisy-PDF Benchmark generator (sample_data/eval_pdfs/).

Deterministically renders 12 synthetic AP-invoice PDFs plus their
ground-truth manifest (MANIFEST.json). stdlib only, no network, no
timestamps in output — two consecutive runs produce byte-identical files.

Usage:
    python sample_data/eval_pdfs/generate_eval_pdfs.py            # write corpus + manifest
    python sample_data/eval_pdfs/generate_eval_pdfs.py --check    # verify without writing (exit 0/1)

Contract: backend/app/extract/schemas.py (ExtractedInvoicePayload) and the
offline tests in backend/tests/eval_gemini_extraction.py (test_eval_pdf_*).
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys

CORPUS_DIR = Path(__file__).resolve().parent

_SUNBEAM = {"name": "Sunbeam Electricals Pvt Ltd", "tax_id": "27AABCS1234F1Z5"}
_ACME = {"name": "Acme Industrial Supply Inc", "tax_id": "98-1234567"}
_HELIX = {"name": "Helix Europa GmbH", "tax_id": "DE812345678"}

# Each spec: printed PDF text lines + the ground-truth payload (schemas.py
# ExtractedInvoicePayload shape) + declared arithmetic status.
_CORPUS_SPEC: list[dict] = [
    {
        "file": "eval_invoice_01_clean.pdf",
        "voice": "clean_digital",
        "difficulty": "easy",
        "arithmetic": {"consistent": True, "variance": 0.0, "variance_field": None},
        "printed": [
            "Vendor: Sunbeam Electricals Pvt Ltd",
            "Tax ID: 27AABCS1234F1Z5",
            "Invoice Number: INV-EVAL-001",
            "Date: 2026-11-01",
            "Currency: INR",
            "PO Reference: PO-EVAL-001",
            "Payment Terms: Net 30",
            "Item: LED Panel 18W",
            "Quantity: 10",
            "Unit Price: 420.00",
            "Tax: 18%",
            "Line Total: 4956.00",
            "Subtotal: 4200.00",
            "Tax: 756.00",
            "Grand Total: 4956.00",
        ],
        "ground_truth": {
            "vendor": _SUNBEAM,
            "invoice": {"number": "INV-EVAL-001", "date": "2026-11-01", "currency": "INR",
                        "po_reference": "PO-EVAL-001", "payment_terms": "Net 30"},
            "lines": [{"item": "LED Panel 18W", "quantity": 10.0, "unit_price": 420.0,
                       "tax_pct": 18.0, "line_total": 4956.0}],
            "totals": {"subtotal": 4200.0, "tax": 756.0, "grand_total": 4956.0},
        },
    },
    {
        "file": "eval_invoice_02_indian_comma.pdf",
        "voice": "indian_comma_grouping",
        "difficulty": "easy",
        "arithmetic": {"consistent": True, "variance": 0.0, "variance_field": None},
        "printed": [
            "Vendor: Sunbeam Electricals Pvt Ltd",
            "Tax ID: 27AABCS1234F1Z5",
            "Invoice Number: INV-EVAL-002",
            "Date: 2026-11-02",
            "Currency: INR",
            "PO Reference: PO-EVAL-002",
            "Payment Terms: Net 15",
            "Item: Industrial Inverter",
            "Quantity: 2",
            "Unit Price: 1,23,456.00",
            "Tax: 18%",
            "Line Total: 2,91,356.16",
            "Subtotal: 2,46,912.00",
            "Tax: 44,444.16",
            "Grand Total: 2,91,356.16",
        ],
        "ground_truth": {
            "vendor": _SUNBEAM,
            "invoice": {"number": "INV-EVAL-002", "date": "2026-11-02", "currency": "INR",
                        "po_reference": "PO-EVAL-002", "payment_terms": "Net 15"},
            "lines": [{"item": "Industrial Inverter", "quantity": 2.0, "unit_price": 123456.0,
                       "tax_pct": 18.0, "line_total": 291356.16}],
            "totals": {"subtotal": 246912.0, "tax": 44444.16, "grand_total": 291356.16},
        },
    },
    {
        "file": "eval_invoice_03_split_gst.pdf",
        "voice": "split_gst_cgst_sgst",
        "difficulty": "medium",
        "arithmetic": {"consistent": True, "variance": 0.0, "variance_field": None},
        "printed": [
            "Vendor: Sunbeam Electricals Pvt Ltd",
            "Tax ID: 27AABCS1234F1Z5",
            "Invoice Number: INV-EVAL-003",
            "Date: 2026-11-03",
            "Currency: INR",
            "PO Reference: PO-EVAL-003",
            "Payment Terms: Net 30",
            "Item: Solar Cable Kit",
            "Quantity: 5",
            "Unit Price: 1200.00",
            "Tax: CGST 9% + SGST 9%",
            "Line Total: 7080.00",
            "Subtotal: 6000.00",
            "Tax: 1080.00",
            "Grand Total: 7080.00",
        ],
        "ground_truth": {
            "vendor": _SUNBEAM,
            "invoice": {"number": "INV-EVAL-003", "date": "2026-11-03", "currency": "INR",
                        "po_reference": "PO-EVAL-003", "payment_terms": "Net 30"},
            "lines": [{"item": "Solar Cable Kit", "quantity": 5.0, "unit_price": 1200.0,
                       "tax_pct": 18.0, "line_total": 7080.0}],
            "totals": {"subtotal": 6000.0, "tax": 1080.0, "grand_total": 7080.0},
        },
    },
    {
        "file": "eval_invoice_04_tds_withheld.pdf",
        "voice": "tds_withheld",
        "difficulty": "medium",
        "arithmetic": {"consistent": True, "variance": 0.0, "variance_field": None},
        "printed": [
            "Vendor: Sunbeam Electricals Pvt Ltd",
            "Tax ID: 27AABCS1234F1Z5",
            "Invoice Number: INV-EVAL-004",
            "Date: 2026-11-04",
            "Currency: INR",
            "PO Reference: PO-EVAL-004",
            "Payment Terms: Net 30",
            "Item: Facility Management Service",
            "Quantity: 1",
            "Unit Price: 50000.00",
            "Tax: 18% (TDS 2% withheld)",
            "Line Total: 59000.00",
            "Subtotal: 50000.00",
            "Tax: 9000.00",
            "Grand Total: 59000.00",
        ],
        "ground_truth": {
            "vendor": _SUNBEAM,
            "invoice": {"number": "INV-EVAL-004", "date": "2026-11-04", "currency": "INR",
                        "po_reference": "PO-EVAL-004", "payment_terms": "Net 30"},
            "lines": [{"item": "Facility Management Service", "quantity": 1.0, "unit_price": 50000.0,
                       "tax_pct": 18.0, "line_total": 59000.0}],
            "totals": {"subtotal": 50000.0, "tax": 9000.0, "grand_total": 59000.0},
        },
    },
    {
        "file": "eval_invoice_05_revision_suffix.pdf",
        "voice": "revision_suffix",
        "difficulty": "medium",
        "arithmetic": {"consistent": True, "variance": 0.0, "variance_field": None},
        "printed": [
            "Vendor: Sunbeam Electricals Pvt Ltd",
            "Tax ID: 27AABCS1234F1Z5",
            "Invoice Number: INV-EVAL-005-R2",
            "Date: 2026-11-05",
            "Currency: INR",
            "PO Reference: PO-EVAL-005",
            "Payment Terms: Net 30",
            "Item: LED Panel 18W",
            "Quantity: 6",
            "Unit Price: 420.00",
            "Tax: 18%",
            "Line Total: 2973.60",
            "Subtotal: 2520.00",
            "Tax: 453.60",
            "Grand Total: 2973.60",
        ],
        "ground_truth": {
            "vendor": _SUNBEAM,
            "invoice": {"number": "INV-EVAL-005-R2", "date": "2026-11-05", "currency": "INR",
                        "po_reference": "PO-EVAL-005", "payment_terms": "Net 30"},
            "lines": [{"item": "LED Panel 18W", "quantity": 6.0, "unit_price": 420.0,
                       "tax_pct": 18.0, "line_total": 2973.6}],
            "totals": {"subtotal": 2520.0, "tax": 453.6, "grand_total": 2973.6},
        },
    },
    {
        "file": "eval_invoice_06_us_format.pdf",
        "voice": "us_format",
        "difficulty": "medium",
        "arithmetic": {"consistent": True, "variance": 0.0, "variance_field": None},
        "printed": [
            "Vendor: Acme Industrial Supply Inc",
            "Tax ID: 98-1234567",
            "Invoice Number: INV-US-EVAL-006",
            "Date: 11/06/2026",
            "Currency: USD",
            "PO Reference: PO-US-EVAL-006",
            "Payment Terms: Net 30",
            "Item: Steel Bracket Kit",
            "Quantity: 3",
            "Unit Price: 1,200.00",
            "Tax: Sales Tax 8.25%",
            "Line Total: 3897.00",
            "Subtotal: 3600.00",
            "Tax: 297.00",
            "Grand Total: 3897.00",
        ],
        "ground_truth": {
            "vendor": _ACME,
            "invoice": {"number": "INV-US-EVAL-006", "date": "2026-11-06", "currency": "USD",
                        "po_reference": "PO-US-EVAL-006", "payment_terms": "Net 30"},
            "lines": [{"item": "Steel Bracket Kit", "quantity": 3.0, "unit_price": 1200.0,
                       "tax_pct": 8.25, "line_total": 3897.0}],
            "totals": {"subtotal": 3600.0, "tax": 297.0, "grand_total": 3897.0},
        },
    },
    {
        "file": "eval_invoice_07_ocr_spacing.pdf",
        "voice": "ocr_spacing",
        "difficulty": "hard",
        "arithmetic": {"consistent": True, "variance": 0.0, "variance_field": None},
        "printed": [
            "Vendor: Sunbeam Electricals Pvt Ltd",
            "Tax ID: 27AABCS1234F1Z5",
            "Invoice Number: I N V - E V A L - 0 0 7",
            "Date: 2026-11-07",
            "Currency: INR",
            "PO Reference: PO-EVAL-007",
            "Payment Terms: Net 30",
            "Item: Copper Wire Roll",
            "Quantity: 4",
            "Unit Price: 850.00",
            "Tax: 18%",
            "Line Total: 4012.00",
            "Subtotal: 3400.00",
            "Tax: 612.00",
            "Grand Total: 4012.00",
        ],
        "ground_truth": {
            "vendor": _SUNBEAM,
            "invoice": {"number": "INV-EVAL-007", "date": "2026-11-07", "currency": "INR",
                        "po_reference": "PO-EVAL-007", "payment_terms": "Net 30"},
            "lines": [{"item": "Copper Wire Roll", "quantity": 4.0, "unit_price": 850.0,
                       "tax_pct": 18.0, "line_total": 4012.0}],
            "totals": {"subtotal": 3400.0, "tax": 612.0, "grand_total": 4012.0},
        },
    },
    {
        "file": "eval_invoice_08_multiline.pdf",
        "voice": "multiline_items",
        "difficulty": "medium",
        "arithmetic": {"consistent": True, "variance": 0.0, "variance_field": None},
        "printed": [
            "Vendor: Sunbeam Electricals Pvt Ltd",
            "Tax ID: 27AABCS1234F1Z5",
            "Invoice Number: INV-EVAL-008",
            "Date: 2026-11-08",
            "Currency: INR",
            "PO Reference: PO-EVAL-008",
            "Payment Terms: Net 30",
            "Item: A4 Paper Box",
            "Quantity: 20",
            "Unit Price: 240.00",
            "Tax: 18%",
            "Line Total: 5664.00",
            "Item: Stapler Pack",
            "Quantity: 10",
            "Unit Price: 150.00",
            "Tax: 18%",
            "Line Total: 1770.00",
            "Item: Whiteboard Marker Set",
            "Quantity: 25",
            "Unit Price: 80.00",
            "Tax: 18%",
            "Line Total: 2360.00",
            "Subtotal: 8300.00",
            "Tax: 1494.00",
            "Grand Total: 9794.00",
        ],
        "ground_truth": {
            "vendor": _SUNBEAM,
            "invoice": {"number": "INV-EVAL-008", "date": "2026-11-08", "currency": "INR",
                        "po_reference": "PO-EVAL-008", "payment_terms": "Net 30"},
            "lines": [
                {"item": "A4 Paper Box", "quantity": 20.0, "unit_price": 240.0,
                 "tax_pct": 18.0, "line_total": 5664.0},
                {"item": "Stapler Pack", "quantity": 10.0, "unit_price": 150.0,
                 "tax_pct": 18.0, "line_total": 1770.0},
                {"item": "Whiteboard Marker Set", "quantity": 25.0, "unit_price": 80.0,
                 "tax_pct": 18.0, "line_total": 2360.0},
            ],
            "totals": {"subtotal": 8300.0, "tax": 1494.0, "grand_total": 9794.0},
        },
    },
    {
        "file": "eval_invoice_09_eur_decimal.pdf",
        "voice": "eur_decimal_comma",
        "difficulty": "hard",
        "arithmetic": {"consistent": True, "variance": 0.0, "variance_field": None},
        "printed": [
            "Vendor: Helix Europa GmbH",
            "Tax ID: DE812345678",
            "Invoice Number: INV-EU-EVAL-009",
            "Date: 2026-11-09",
            "Currency: EUR",
            "PO Reference: PO-EU-EVAL-009",
            "Payment Terms: Net 30",
            "Item: Precision Bearing Set",
            "Quantity: 2",
            "Unit Price: 1.250,00",
            "Tax: 0% (exempt)",
            "Line Total: 2500.00",
            "Subtotal: 2500.00",
            "Tax: 0.00",
            "Grand Total: 2500.00",
        ],
        "ground_truth": {
            "vendor": _HELIX,
            "invoice": {"number": "INV-EU-EVAL-009", "date": "2026-11-09", "currency": "EUR",
                        "po_reference": "PO-EU-EVAL-009", "payment_terms": "Net 30"},
            "lines": [{"item": "Precision Bearing Set", "quantity": 2.0, "unit_price": 1250.0,
                       "tax_pct": 0.0, "line_total": 2500.0}],
            "totals": {"subtotal": 2500.0, "tax": 0.0, "grand_total": 2500.0},
        },
    },
    {
        "file": "eval_invoice_10_rounding_drift.pdf",
        "voice": "rounding_drift",
        "difficulty": "hard",
        "arithmetic": {"consistent": False, "variance": 0.02, "variance_field": "line_total"},
        "printed": [
            "Vendor: Sunbeam Electricals Pvt Ltd",
            "Tax ID: 27AABCS1234F1Z5",
            "Invoice Number: INV-EVAL-010",
            "Date: 2026-11-10",
            "Currency: INR",
            "PO Reference: PO-EVAL-010",
            "Payment Terms: Net 30",
            "Item: Safety Gloves Pair",
            "Quantity: 33",
            "Unit Price: 147.33",
            "Tax: 18%",
            "Line Total: 5737.05",
            "Subtotal: 4861.89",
            "Tax: 875.14",
            "Grand Total: 5737.03",
        ],
        "ground_truth": {
            "vendor": _SUNBEAM,
            "invoice": {"number": "INV-EVAL-010", "date": "2026-11-10", "currency": "INR",
                        "po_reference": "PO-EVAL-010", "payment_terms": "Net 30"},
            "lines": [{"item": "Safety Gloves Pair", "quantity": 33.0, "unit_price": 147.33,
                       "tax_pct": 18.0, "line_total": 5737.05}],
            "totals": {"subtotal": 4861.89, "tax": 875.14, "grand_total": 5737.03},
        },
    },
    {
        "file": "eval_invoice_11_tax_exempt.pdf",
        "voice": "tax_exemption",
        "difficulty": "easy",
        "arithmetic": {"consistent": True, "variance": 0.0, "variance_field": None},
        "printed": [
            "Vendor: Sunbeam Electricals Pvt Ltd",
            "Tax ID: 27AABCS1234F1Z5",
            "Invoice Number: INV-EVAL-011",
            "Date: 2026-11-11",
            "Currency: INR",
            "PO Reference: PO-EVAL-011",
            "Payment Terms: Net 30",
            "Item: Export Freight Service",
            "Quantity: 1",
            "Unit Price: 15000.00",
            "Tax: Exempt (0%)",
            "Line Total: 15000.00",
            "Subtotal: 15000.00",
            "Tax: 0.00",
            "Grand Total: 15000.00",
        ],
        "ground_truth": {
            "vendor": _SUNBEAM,
            "invoice": {"number": "INV-EVAL-011", "date": "2026-11-11", "currency": "INR",
                        "po_reference": "PO-EVAL-011", "payment_terms": "Net 30"},
            "lines": [{"item": "Export Freight Service", "quantity": 1.0, "unit_price": 15000.0,
                       "tax_pct": 0.0, "line_total": 15000.0}],
            "totals": {"subtotal": 15000.0, "tax": 0.0, "grand_total": 15000.0},
        },
    },
    {
        "file": "eval_invoice_12_cross_variance.pdf",
        "voice": "cross_total_variance",
        "difficulty": "hard",
        "arithmetic": {"consistent": False, "variance": 500.0, "variance_field": "grand_total"},
        "printed": [
            "Vendor: Sunbeam Electricals Pvt Ltd",
            "Tax ID: 27AABCS1234F1Z5",
            "Invoice Number: INV-EVAL-012",
            "Date: 2026-11-12",
            "Currency: INR",
            "PO Reference: PO-EVAL-012",
            "Payment Terms: Net 30",
            "Item: Industrial Pump",
            "Quantity: 1",
            "Unit Price: 18500.00",
            "Tax: 18%",
            "Line Total: 21830.00",
            "Subtotal: 18500.00",
            "Tax: 3330.00",
            "Grand Total: 22330.00",
        ],
        "ground_truth": {
            "vendor": _SUNBEAM,
            "invoice": {"number": "INV-EVAL-012", "date": "2026-11-12", "currency": "INR",
                        "po_reference": "PO-EVAL-012", "payment_terms": "Net 30"},
            "lines": [{"item": "Industrial Pump", "quantity": 1.0, "unit_price": 18500.0,
                       "tax_pct": 18.0, "line_total": 21830.0}],
            "totals": {"subtotal": 18500.0, "tax": 3330.0, "grand_total": 22330.0},
        },
    },
]


def _escape_pdf_text(text: str) -> str:
    """Escape a string for a PDF literal text operator."""
    return text.replace("\\", r"\\").replace("(", r"\(").replace(")", r"\)")


def _render_pdf(text_lines: list[str]) -> bytes:
    """Render one minimal one-page PDF 1.4 with an uncompressed content stream."""
    content_ops: list[str] = []
    y = 720
    for line in text_lines:
        content_ops.append(f"BT /F1 10 Tf 72 {y} Td ({_escape_pdf_text(line)}) Tj ET")
        y -= 16
    stream = "\n".join(content_ops)

    objects = [
        "<< /Type /Catalog /Pages 2 0 R >>",
        "<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        "<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
        "/Resources << /Font << /F1 5 0 R >> >> /Contents 4 0 R >>",
        f"<< /Length {len(stream.encode('ascii'))} >>\nstream\n{stream}\nendstream",
        "<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    ]

    out = "%PDF-1.4\n"
    offsets: list[int] = []
    for object_number, body in enumerate(objects, start=1):
        offsets.append(len(out.encode("ascii")))
        out += f"{object_number} 0 obj\n{body}\nendobj\n"

    xref_offset = len(out.encode("ascii"))
    xref = f"xref\n0 {len(objects) + 1}\n0000000000 65535 f \n" + "".join(
        f"{offset:010d} 00000 n \n" for offset in offsets
    )
    out += xref
    out += f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\nstartxref\n{xref_offset}\n%%EOF\n"
    return out.encode("ascii")


def build_corpus() -> dict[str, bytes]:
    """Render every golden PDF in memory: {filename: pdf_bytes}."""
    return {spec["file"]: _render_pdf(spec["printed"]) for spec in _CORPUS_SPEC}


def build_manifest_entries(pdf_bytes_by_name: dict[str, bytes]) -> list[dict]:
    """Build the manifest entries (with sha256/size) for the rendered corpus."""
    entries: list[dict] = []
    for spec in _CORPUS_SPEC:
        pdf_bytes = pdf_bytes_by_name[spec["file"]]
        entries.append({
            "file": spec["file"],
            "voice": spec["voice"],
            "difficulty": spec["difficulty"],
            "sha256": hashlib.sha256(pdf_bytes).hexdigest(),
            "bytes": len(pdf_bytes),
            "arithmetic": spec["arithmetic"],
            "ground_truth": spec["ground_truth"],
        })
    return entries


def build_manifest(pdf_bytes_by_name: dict[str, bytes]) -> dict:
    return {
        "schema_version": "1.0",
        "corpus": "golden_noisy_pdf_eval",
        "generated_by": "sample_data/eval_pdfs/generate_eval_pdfs.py",
        "count": len(_CORPUS_SPEC),
        "entries": build_manifest_entries(pdf_bytes_by_name),
    }


def _write_corpus() -> dict:
    corpus = build_corpus()
    manifest = build_manifest(corpus)
    for filename, pdf_bytes in corpus.items():
        (CORPUS_DIR / filename).write_bytes(pdf_bytes)
    (CORPUS_DIR / "MANIFEST.json").write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    return manifest


def _check() -> int:
    corpus = build_corpus()
    expected_manifest = build_manifest(corpus)
    failures: list[str] = []
    for filename, pdf_bytes in corpus.items():
        on_disk = CORPUS_DIR / filename
        if not on_disk.exists():
            failures.append(f"{filename}: missing")
            continue
        if on_disk.read_bytes() != pdf_bytes:
            failures.append(f"{filename}: bytes differ from deterministic regeneration")
    manifest_path = CORPUS_DIR / "MANIFEST.json"
    if not manifest_path.exists():
        failures.append("MANIFEST.json: missing")
    else:
        on_disk_manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        if on_disk_manifest != expected_manifest:
            failures.append("MANIFEST.json: differs from deterministic regeneration")
    if failures:
        for failure in failures:
            print(f"CHECK FAIL: {failure}", file=sys.stderr)
        return 1
    print(f"CHECK OK: {len(corpus)} PDFs + MANIFEST.json byte-identical to deterministic regeneration")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate the golden noisy-PDF eval corpus.")
    parser.add_argument("--check", action="store_true", help="verify existing corpus without writing")
    args = parser.parse_args()
    if args.check:
        return _check()

    manifest = _write_corpus()
    total_bytes = sum(entry["bytes"] for entry in manifest["entries"])
    print(f"Wrote {manifest['count']} PDFs + MANIFEST.json ({total_bytes} bytes of PDFs) into {CORPUS_DIR}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

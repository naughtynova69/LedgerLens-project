#!/usr/bin/env python3
"""Golden Noisy-PDF eval corpus generator (sample_data/eval_pdfs/).

Deterministically renders 12 one-page invoice PDFs (minimal PDF 1.4, Letter
612x792, Helvetica /F1, uncompressed content stream, one
``BT /F1 10 Tf 72 Y Td (Field: value) Tj ET`` op per printed field, starting at
y=720 and stepping -16) plus MANIFEST.json. Every emitted byte is a pure
function of the fixed spec table below: fixed /Producer and /CreationDate in
the trailer Info dictionary, no randomness, no clock reads, no
locale-dependent formatting -- two consecutive runs are byte-identical.

Usage:
    python sample_data/eval_pdfs/generate_eval_pdfs.py            # write corpus + manifest
    python sample_data/eval_pdfs/generate_eval_pdfs.py --check    # verify without writing (exit 0/1)

--check recomputes every PDF and MANIFEST.json in memory, compares against the
on-disk bytes and prints a DIFF line per mismatch; exit 0 when the corpus is
byte-identical to the recomputation, exit 1 otherwise.

Contract: backend/app/extract/schemas.py (ExtractedInvoicePayload field names).
Stdlib only (argparse, hashlib, json, os, sys). The ground-truth numbers in
the spec table are FIXED golden values and must never be edited.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

CORPUS_DIR = Path(__file__).resolve().parent
MANIFEST_NAME = "MANIFEST.json"

PDF_MAGIC = b"%PDF-1.4"
PRODUCER = "LedgerLens Golden Eval"
CREATION_DATE = "D:20261101000000"
PAGE_WIDTH = 612
PAGE_HEIGHT = 792
TEXT_LEFT_X = 72
TEXT_TOP_Y = 720
TEXT_LINE_STEP = 16

MANIFEST_HEADER = {
    "schema_version": "1.0",
    "corpus": "golden_noisy_pdf_eval",
    "generated_by": "sample_data/eval_pdfs/generate_eval_pdfs.py",
}

_SUNBEAM = {"name": "Sunbeam Electricals Pvt Ltd", "tax_id": "27AABCS1234F1Z5"}
_ACME = {"name": "Acme Industrial Supply Inc", "tax_id": "98-1234567"}
_HELIX = {"name": "Helix Europa GmbH", "tax_id": "DE812345678"}


def _gt(vendor, number, date, currency, po, terms, lines, totals):
    """Build a ground_truth payload with ExtractedInvoicePayload field names."""
    return {
        "vendor": {"name": vendor["name"], "tax_id": vendor["tax_id"]},
        "invoice": {
            "number": number,
            "date": date,
            "currency": currency,
            "po_reference": po,
            "payment_terms": terms,
        },
        "lines": [
            {
                "item": item,
                "quantity": quantity,
                "unit_price": unit_price,
                "tax_pct": tax_pct,
                "line_total": line_total,
            }
            for (item, quantity, unit_price, tax_pct, line_total) in lines
        ],
        "totals": {"subtotal": totals[0], "tax": totals[1], "grand_total": totals[2]},
    }


def _ok():
    return {"consistent": True, "variance": 0.0, "variance_field": None}


ENTRIES = [
    {
        "file": "eval_invoice_01_clean.pdf",
        "voice": "clean_digital",
        "difficulty": "easy",
        "arithmetic": _ok(),
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
        "ground_truth": _gt(
            _SUNBEAM,
            "INV-EVAL-001",
            "2026-11-01",
            "INR",
            "PO-EVAL-001",
            "Net 30",
            [("LED Panel 18W", 10.0, 420.0, 18.0, 4956.0)],
            (4200.0, 756.0, 4956.0),
        ),
    },
    {
        "file": "eval_invoice_02_indian_comma.pdf",
        "voice": "indian_comma_grouping",
        "difficulty": "easy",
        "arithmetic": _ok(),
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
        "ground_truth": _gt(
            _SUNBEAM,
            "INV-EVAL-002",
            "2026-11-02",
            "INR",
            "PO-EVAL-002",
            "Net 15",
            [("Industrial Inverter", 2.0, 123456.0, 18.0, 291356.16)],
            (246912.0, 44444.16, 291356.16),
        ),
    },
    {
        "file": "eval_invoice_03_split_gst.pdf",
        "voice": "split_gst_cgst_sgst",
        "difficulty": "medium",
        "arithmetic": _ok(),
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
        "ground_truth": _gt(
            _SUNBEAM,
            "INV-EVAL-003",
            "2026-11-03",
            "INR",
            "PO-EVAL-003",
            "Net 30",
            [("Solar Cable Kit", 5.0, 1200.0, 18.0, 7080.0)],
            (6000.0, 1080.0, 7080.0),
        ),
    },
    {
        "file": "eval_invoice_04_tds_withheld.pdf",
        "voice": "tds_withheld",
        "difficulty": "medium",
        "arithmetic": _ok(),
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
        "ground_truth": _gt(
            _SUNBEAM,
            "INV-EVAL-004",
            "2026-11-04",
            "INR",
            "PO-EVAL-004",
            "Net 30",
            [("Facility Management Service", 1.0, 50000.0, 18.0, 59000.0)],
            (50000.0, 9000.0, 59000.0),
        ),
    },
    {
        "file": "eval_invoice_05_revision_suffix.pdf",
        "voice": "revision_suffix",
        "difficulty": "medium",
        "arithmetic": _ok(),
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
        "ground_truth": _gt(
            _SUNBEAM,
            "INV-EVAL-005-R2",
            "2026-11-05",
            "INR",
            "PO-EVAL-005",
            "Net 30",
            [("LED Panel 18W", 6.0, 420.0, 18.0, 2973.60)],
            (2520.0, 453.60, 2973.60),
        ),
    },
    {
        "file": "eval_invoice_06_us_format.pdf",
        "voice": "us_format",
        "difficulty": "medium",
        "arithmetic": _ok(),
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
        "ground_truth": _gt(
            _ACME,
            "INV-US-EVAL-006",
            "2026-11-06",
            "USD",
            "PO-US-EVAL-006",
            "Net 30",
            [("Steel Bracket Kit", 3.0, 1200.0, 8.25, 3897.0)],
            (3600.0, 297.0, 3897.0),
        ),
    },
    {
        "file": "eval_invoice_07_ocr_spacing.pdf",
        "voice": "ocr_spacing",
        "difficulty": "hard",
        "arithmetic": _ok(),
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
        "ground_truth": _gt(
            _SUNBEAM,
            "INV-EVAL-007",
            "2026-11-07",
            "INR",
            "PO-EVAL-007",
            "Net 30",
            [("Copper Wire Roll", 4.0, 850.0, 18.0, 4012.0)],
            (3400.0, 612.0, 4012.0),
        ),
    },
    {
        "file": "eval_invoice_08_multiline.pdf",
        "voice": "multiline_items",
        "difficulty": "medium",
        "arithmetic": _ok(),
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
        "ground_truth": _gt(
            _SUNBEAM,
            "INV-EVAL-008",
            "2026-11-08",
            "INR",
            "PO-EVAL-008",
            "Net 30",
            [
                ("A4 Paper Box", 20.0, 240.0, 18.0, 5664.0),
                ("Stapler Pack", 10.0, 150.0, 18.0, 1770.0),
                ("Whiteboard Marker Set", 25.0, 80.0, 18.0, 2360.0),
            ],
            (8300.0, 1494.0, 9794.0),
        ),
    },
    {
        "file": "eval_invoice_09_eur_decimal.pdf",
        "voice": "eur_decimal_comma",
        "difficulty": "hard",
        "arithmetic": _ok(),
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
        "ground_truth": _gt(
            _HELIX,
            "INV-EU-EVAL-009",
            "2026-11-09",
            "EUR",
            "PO-EU-EVAL-009",
            "Net 30",
            [("Precision Bearing Set", 2.0, 1250.0, 0.0, 2500.0)],
            (2500.0, 0.0, 2500.0),
        ),
    },
    {
        "file": "eval_invoice_10_rounding_drift.pdf",
        "voice": "rounding_drift",
        "difficulty": "hard",
        "arithmetic": {
            "consistent": False,
            "variance": 0.02,
            "variance_field": "line_total",
        },
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
        "ground_truth": _gt(
            _SUNBEAM,
            "INV-EVAL-010",
            "2026-11-10",
            "INR",
            "PO-EVAL-010",
            "Net 30",
            [("Safety Gloves Pair", 33.0, 147.33, 18.0, 5737.05)],
            (4861.89, 875.14, 5737.03),
        ),
    },
    {
        "file": "eval_invoice_11_tax_exempt.pdf",
        "voice": "tax_exemption",
        "difficulty": "easy",
        "arithmetic": _ok(),
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
        "ground_truth": _gt(
            _SUNBEAM,
            "INV-EVAL-011",
            "2026-11-11",
            "INR",
            "PO-EVAL-011",
            "Net 30",
            [("Export Freight Service", 1.0, 15000.0, 0.0, 15000.0)],
            (15000.0, 0.0, 15000.0),
        ),
    },
    {
        "file": "eval_invoice_12_cross_variance.pdf",
        "voice": "cross_total_variance",
        "difficulty": "hard",
        "arithmetic": {
            "consistent": False,
            "variance": 500.0,
            "variance_field": "grand_total",
        },
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
        "ground_truth": _gt(
            _SUNBEAM,
            "INV-EVAL-012",
            "2026-11-12",
            "INR",
            "PO-EVAL-012",
            "Net 30",
            [("Industrial Pump", 1.0, 18500.0, 18.0, 21830.0)],
            (18500.0, 3330.0, 22330.0),
        ),
    },
]

# Compatibility view of the corpus spec (same key layout as the original
# draft): printed PDF text lines + ground-truth payload + arithmetic status.
_CORPUS_SPEC = [
    {
        "file": entry["file"],
        "voice": entry["voice"],
        "difficulty": entry["difficulty"],
        "arithmetic": entry["arithmetic"],
        "printed": entry["printed"],
        "ground_truth": entry["ground_truth"],
    }
    for entry in ENTRIES
]


def escape_pdf_string(text: str) -> str:
    """Escape a literal for a PDF string object (backslash and delimiters)."""
    return text.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")


def content_stream_bytes(printed_lines) -> bytes:
    """One ``BT /F1 10 Tf 72 Y Td (Field: value) Tj ET`` op per line, LF-joined."""
    ops = []
    y = TEXT_TOP_Y
    for line in printed_lines:
        ops.append(
            "BT /F1 10 Tf %d %d Td (%s) Tj ET" % (TEXT_LEFT_X, y, escape_pdf_string(line))
        )
        y -= TEXT_LINE_STEP
    return ("\n".join(ops)).encode("ascii")


def build_pdf_bytes(printed_lines) -> bytes:
    """Assemble one deterministic minimal PDF 1.4 with an exact xref table."""
    stream = content_stream_bytes(printed_lines)
    body_parts = []
    body_offsets = []
    body_len = 0

    def emit(obj_bytes: bytes) -> None:
        nonlocal body_len
        body_offsets.append(body_len)
        body_parts.append(obj_bytes)
        body_len += len(obj_bytes)

    emit(b"1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n")
    emit(b"2 0 obj\n<< /Type /Pages /Kids [3 0 R] /Count 1 >>\nendobj\n")
    emit(
        (
            "3 0 obj\n<< /Type /Page /Parent 2 0 R /MediaBox [0 0 %d %d] "
            "/Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>\nendobj\n"
            % (PAGE_WIDTH, PAGE_HEIGHT)
        ).encode("ascii")
    )
    emit(b"4 0 obj\n<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>\nendobj\n")
    emit(
        ("5 0 obj\n<< /Length %d >>\nstream\n" % len(stream)).encode("ascii")
        + stream
        + b"\nendstream\nendobj\n"
    )
    emit(
        (
            "6 0 obj\n<< /Producer (%s) /CreationDate (%s) >>\nendobj\n"
            % (PRODUCER, CREATION_DATE)
        ).encode("ascii")
    )

    header = PDF_MAGIC + b"\n"
    body = b"".join(body_parts)
    xref_offset = len(header) + body_len
    rows = [b"0000000000 65535 f "]
    for off in body_offsets:
        rows.append(("%010d 00000 n " % (len(header) + off)).encode("ascii"))
    xref = b"xref\n0 7\n" + b"\n".join(rows) + b"\n"
    trailer = (
        "trailer\n<< /Size 7 /Root 1 0 R /Info 6 0 R >>\nstartxref\n%d\n%%EOF\n"
        % xref_offset
    ).encode("ascii")
    return header + body + xref + trailer


def _render_pdf(text_lines) -> bytes:
    """Compatibility alias for build_pdf_bytes."""
    return build_pdf_bytes(text_lines)


def verify_pdf_bytes(data: bytes, printed_lines, label: str) -> list:
    """Strict structural checks on a rendered PDF; returns a list of problems."""
    problems = []
    if not data.startswith(PDF_MAGIC):
        problems.append("%s: does not start with %%PDF-1.4 magic" % label)
    if not data.endswith(b"%EOF\n"):
        problems.append("%s: does not end with %%EOF" % label)
    for token, what in [
        (b"/MediaBox [0 0 612 792]", "Letter MediaBox"),
        (b"/BaseFont /Helvetica", "Helvetica base font"),
        (b"/Count 1", "single-page /Count"),
        (b"/Producer (LedgerLens Golden Eval)", "/Producer header"),
        (b"/CreationDate (D:20261101000000)", "/CreationDate header"),
    ]:
        if token not in data:
            problems.append("%s: missing %s" % (label, what))
    marker = data.rfind(b"startxref\n")
    if marker < 0:
        problems.append("%s: no startxref token found" % label)
        return problems
    tail = data[marker + len(b"startxref\n"):].split()
    try:
        xref_off = int(tail[0].decode("ascii"))
    except (IndexError, ValueError, UnicodeDecodeError):
        problems.append("%s: startxref value is not an integer" % label)
        return problems
    if data[xref_off:xref_off + 4] != b"xref":
        problems.append(
            "%s: startxref offset %d does not point at the literal 'xref' token"
            % (label, xref_off)
        )
        return problems
    after_token = data[xref_off + 4:]
    nl = after_token.find(b"\n")
    subsection = after_token[nl + 1:]
    head_end = subsection.find(b"\n")
    head_parts = subsection[:head_end].split()
    if len(head_parts) != 2 or head_parts[0] != b"0":
        problems.append("%s: malformed xref subsection header" % label)
        return problems
    count = int(head_parts[1].decode("ascii"))
    entries_blob = subsection[head_end + 1:]
    for i in range(count):
        raw = entries_blob[i * 20:(i + 1) * 20]
        if len(raw) != 20:
            problems.append("%s: xref entry %d is truncated" % (label, i))
            return problems
        if raw[19:20] != b"\n":
            problems.append("%s: xref entry %d has a malformed end-of-line" % (label, i))
        if i == 0:
            if raw[:18] != b"0000000000 65535 f":
                problems.append("%s: xref entry 0 is not the free head" % label)
            continue
        if (
            raw[10:11] != b" "
            or raw[11:16] != b"00000"
            or raw[16:17] != b" "
            or raw[17:18] != b"n"
        ):
            problems.append("%s: xref entry %d is malformed" % (label, i))
            continue
        off = int(raw[:10].decode("ascii"))
        want = ("%d 0 obj" % i).encode("ascii")
        if data[off:off + len(want)] != want:
            problems.append(
                "%s: xref entry for object %d points at byte %d which is not its "
                "object header" % (label, i, off)
            )
    if count != 7:
        problems.append(
            "%s: xref subsection declares %d entries, expected 7" % (label, count)
        )
    len_idx = data.find(b"<< /Length ")
    if len_idx < 0:
        problems.append("%s: no /Length declaration found" % label)
    else:
        num_start = len_idx + len(b"<< /Length ")
        num_end = data.find(b" >>", num_start)
        declared = int(data[num_start:num_end].decode("ascii"))
        stream_idx = data.find(b"stream\n", num_end)
        payload_start = stream_idx + len(b"stream\n")
        payload_end = data.find(b"\nendstream", payload_start)
        actual = payload_end - payload_start
        if actual != declared:
            problems.append(
                "%s: /Length declares %d bytes but the stream payload is %d bytes"
                % (label, declared, actual)
            )
    if data.count(b"Tj ET") != len(printed_lines):
        problems.append(
            "%s: expected %d text ops, found %d"
            % (label, len(printed_lines), data.count(b"Tj ET"))
        )
    for line in printed_lines:
        token = ("(" + escape_pdf_string(line) + ")").encode("ascii")
        if token not in data:
            problems.append("%s: printed line missing from content stream: %r" % (label, line))
    return problems


def build_corpus() -> dict:
    """Render every golden PDF in memory: {filename: pdf_bytes}."""
    return {spec["file"]: build_pdf_bytes(spec["printed"]) for spec in _CORPUS_SPEC}


def build_manifest_entries(pdf_bytes_by_name) -> list:
    """Build the manifest entries (with sha256/size) for the rendered corpus."""
    entries = []
    for spec in _CORPUS_SPEC:
        pdf_bytes = pdf_bytes_by_name[spec["file"]]
        entries.append(
            {
                "file": spec["file"],
                "voice": spec["voice"],
                "difficulty": spec["difficulty"],
                "sha256": hashlib.sha256(pdf_bytes).hexdigest(),
                "bytes": len(pdf_bytes),
                "arithmetic": {
                    "consistent": spec["arithmetic"]["consistent"],
                    "variance": spec["arithmetic"]["variance"],
                    "variance_field": spec["arithmetic"]["variance_field"],
                },
                "ground_truth": spec["ground_truth"],
            }
        )
    return entries


def build_manifest(pdf_bytes_by_name) -> dict:
    manifest = dict(MANIFEST_HEADER)
    manifest["count"] = len(_CORPUS_SPEC)
    manifest["entries"] = build_manifest_entries(pdf_bytes_by_name)
    return manifest


def manifest_to_bytes(manifest: dict) -> bytes:
    return (json.dumps(manifest, indent=2) + "\n").encode("utf-8")


# Fixed allowlist of writable/readable corpus filenames (spec table + manifest);
# every write/read resolves through _safe_corpus_path and is provably contained
# inside CORPUS_DIR (fail-closed against path traversal).
_ALLOWED_CORPUS_FILES = frozenset(
    entry["file"] for entry in _CORPUS_SPEC
) | {MANIFEST_NAME}


def _safe_corpus_path(name: str) -> Path:
    """Map a corpus filename to a Path strictly inside CORPUS_DIR.

    Fail-closed: the name must be a member of the fixed spec-table allowlist
    and a plain filename (no directory components, no dotfiles), so the
    write/read paths cannot traverse out of this directory.
    """
    if name not in _ALLOWED_CORPUS_FILES:
        raise ValueError("unknown corpus filename: %r" % (name,))
    if Path(name).name != name or name.startswith("."):
        raise ValueError("unsafe corpus filename: %r" % (name,))
    return CORPUS_DIR / name


def _read_disk(name):
    path = _safe_corpus_path(name)
    if not path.is_file():
        return None
    return path.read_bytes()


def _write_corpus() -> dict:
    corpus = build_corpus()
    manifest = build_manifest(corpus)
    for filename, pdf_bytes in corpus.items():
        _safe_corpus_path(filename).write_bytes(pdf_bytes)
    _safe_corpus_path(MANIFEST_NAME).write_bytes(manifest_to_bytes(manifest))
    return manifest


def run_write(pdf_bytes_by_file) -> int:
    print("Writing corpus into %s" % CORPUS_DIR)
    _write_corpus()
    manifest_data = manifest_to_bytes(build_manifest(pdf_bytes_by_file))

    failures = 0
    for spec in _CORPUS_SPEC:
        name = spec["file"]
        on_disk = _read_disk(name)
        problems = verify_pdf_bytes(on_disk, spec["printed"], name)
        if on_disk != pdf_bytes_by_file[name]:
            problems.append("%s: on-disk bytes differ from the built bytes" % name)
        for problem in problems:
            print("ERROR " + problem)
        failures += len(problems)
        print(
            "WROTE %-36s bytes=%-6d sha256=%s"
            % (name, len(on_disk), hashlib.sha256(on_disk).hexdigest())
        )
    on_disk_manifest = _read_disk(MANIFEST_NAME)
    if on_disk_manifest != manifest_data:
        print("ERROR MANIFEST.json: on-disk bytes differ from the built manifest")
        failures += 1
    print(
        "WROTE %-36s bytes=%-6d sha256=%s"
        % (MANIFEST_NAME, len(on_disk_manifest), hashlib.sha256(on_disk_manifest).hexdigest())
    )
    if failures:
        print("GENERATION FAILED: %d problem(s)" % failures)
        return 1
    print(
        "OK: wrote %d PDFs + %s, all structurally verified"
        % (len(pdf_bytes_by_file), MANIFEST_NAME)
    )
    return 0


def run_check(pdf_bytes_by_file) -> int:
    manifest_data = manifest_to_bytes(build_manifest(pdf_bytes_by_file))
    mismatches = 0
    for spec in _CORPUS_SPEC:
        name = spec["file"]
        expected = pdf_bytes_by_file[name]
        on_disk = _read_disk(name)
        if on_disk is None:
            print(
                "DIFF %s: MISSING on disk (expected %d bytes, sha256=%s)"
                % (name, len(expected), hashlib.sha256(expected).hexdigest())
            )
            mismatches += 1
            continue
        if on_disk == expected:
            print(
                "OK   %-36s bytes=%-6d sha256=%s"
                % (name, len(on_disk), hashlib.sha256(on_disk).hexdigest())
            )
            continue
        print("DIFF %s: on-disk bytes differ from recomputed bytes" % name)
        print(
            "     expected bytes=%d sha256=%s"
            % (len(expected), hashlib.sha256(expected).hexdigest())
        )
        print(
            "     on-disk  bytes=%d sha256=%s"
            % (len(on_disk), hashlib.sha256(on_disk).hexdigest())
        )
        for problem in verify_pdf_bytes(on_disk, spec["printed"], name):
            print("     on-disk structural problem: " + problem)
        mismatches += 1

    on_disk_manifest = _read_disk(MANIFEST_NAME)
    if on_disk_manifest is None:
        print(
            "DIFF %s: MISSING on disk (expected %d bytes, sha256=%s)"
            % (MANIFEST_NAME, len(manifest_data), hashlib.sha256(manifest_data).hexdigest())
        )
        mismatches += 1
    elif on_disk_manifest == manifest_data:
        print(
            "OK   %-36s bytes=%-6d sha256=%s"
            % (MANIFEST_NAME, len(on_disk_manifest), hashlib.sha256(on_disk_manifest).hexdigest())
        )
    else:
        print("DIFF MANIFEST.json: on-disk bytes differ from recomputed manifest")
        print(
            "     expected bytes=%d sha256=%s"
            % (len(manifest_data), hashlib.sha256(manifest_data).hexdigest())
        )
        print(
            "     on-disk  bytes=%d sha256=%s"
            % (len(on_disk_manifest), hashlib.sha256(on_disk_manifest).hexdigest())
        )
        try:
            parsed = json.loads(on_disk_manifest.decode("utf-8"))
            recomputed = json.loads(manifest_data.decode("utf-8"))
            if parsed.get("count") != recomputed["count"]:
                print(
                    "     count: on-disk=%r expected=%r"
                    % (parsed.get("count"), recomputed["count"])
                )
            by_file = {}
            for item in parsed.get("entries", []):
                by_file[item.get("file")] = item
            for expected_entry in recomputed["entries"]:
                got = by_file.get(expected_entry["file"])
                if got is None:
                    print("     entries: missing on-disk entry for %s" % expected_entry["file"])
                    continue
                if got.get("sha256") != expected_entry["sha256"]:
                    print(
                        "     %s sha256: on-disk=%s expected=%s"
                        % (expected_entry["file"], got.get("sha256"), expected_entry["sha256"])
                    )
                if got.get("bytes") != expected_entry["bytes"]:
                    print(
                        "     %s bytes: on-disk=%r expected=%r"
                        % (expected_entry["file"], got.get("bytes"), expected_entry["bytes"])
                    )
        except (ValueError, UnicodeDecodeError) as exc:
            print("     on-disk MANIFEST.json is not parseable JSON: %s" % exc)
        mismatches += 1

    corpus_names = set(pdf_bytes_by_file)
    for found in sorted(p.name for p in CORPUS_DIR.iterdir()):
        if found.lower().endswith(".pdf") and found not in corpus_names:
            print("DIFF %s: unexpected PDF not part of the corpus" % found)
            mismatches += 1

    if mismatches:
        print("CHECK FAILED: %d mismatch(es)" % mismatches)
        return 1
    print(
        "CHECK OK: %d PDFs + %s all byte-identical to the deterministic recomputation"
        % (len(corpus_names), MANIFEST_NAME)
    )
    return 0


def _check() -> int:
    corpus = build_corpus()
    return run_check(corpus)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        prog="generate_eval_pdfs.py",
        description=(
            "Deterministically build the golden noisy-PDF eval corpus "
            "(12 one-page invoice PDFs + MANIFEST.json) next to this script."
        ),
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="verify the on-disk corpus against an in-memory recomputation; exit 1 on any mismatch",
    )
    args = parser.parse_args(argv)

    built = build_corpus()
    structural = []
    for spec in _CORPUS_SPEC:
        structural.extend(
            verify_pdf_bytes(built[spec["file"]], spec["printed"], spec["file"] + " [in-memory]")
        )
    for problem in structural:
        print("ERROR " + problem)
    if structural:
        print("ABORTED: generated bytes failed internal structural verification")
        return 1

    if args.check:
        return run_check(built)
    return run_write(built)


if __name__ == "__main__":
    sys.exit(main())

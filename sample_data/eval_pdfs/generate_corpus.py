#!/usr/bin/env python3
"""Golden eval-PDF corpus generator (sample_data/eval_pdfs/).

Deterministically renders 12 locale-diverse one-page invoice PDFs plus
``manifest.json`` using reportlab (invariant mode, uncompressed content
streams, embedded Unicode TTF so the real ``₹`` / ``€`` / ``£`` glyphs land in
the text layer). The corpus covers four buckets required by the eval spec:

  1. 3 Indian GST invoices  — ₹, lakh/crore comma grouping (1,23,456.00),
     DD/MM/YYYY dates, CGST 9% + SGST 9%, revision suffix INV-8821-R2.
  2. 3 US/Canada invoices   — $, C$, MM/DD/YYYY dates, Sales Tax 8.25% and
     GST 5% + QST 9.975% (combined per-line rate 14.975).
  3. 3 EU/UK invoices       — €, £, DD.MM.YYYY, decimal-comma 1.234,56,
     VAT / MwSt. labels.
  4. 3 noisy/tricky cases   — long wrapped multi-line table rows, zero-rated
     Exempt tax (tax_pct 0.0), and an intentional line-total math mismatch
     that must fail closed into needs_review.

Every emitted byte is a pure function of the fixed spec table below: reportlab
``invariant=1`` pins /CreationDate and the document ID, no randomness, no
clock reads, no locale-dependent formatting — two consecutive runs are
byte-identical, which the regeneration-parity eval test relies on.

manifest.json (top-level list, 12 entries) carries, per file: the prompt
schema (``filename`` / ``locale`` / ``expected`` matching the
ExtractedInvoicePayload field names) plus engineering extensions (``voice``,
``difficulty``, ``mime_type``, ``engine``, sha256/``bytes`` pinning,
``expect_needs_review``, declared ``arithmetic`` variance accounting).

Usage:
    python sample_data/eval_pdfs/generate_corpus.py            # write corpus + manifest
    python sample_data/eval_pdfs/generate_corpus.py --check    # verify without writing (exit 0/1)

Contract: backend/app/extract/schemas.py (ExtractedInvoicePayload field names).
reportlab is required to (re)generate; the committed PDFs are the source of
truth for offline/CI test runs. Ground-truth numbers are FIXED golden values.
"""
from __future__ import annotations

import argparse
import hashlib
import io
import json
import sys
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path

CORPUS_DIR = Path(__file__).resolve().parent
MANIFEST_NAME = "manifest.json"

try:
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.utils import simpleSplit
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont, TTFontFile
    from reportlab.pdfgen import canvas as pdfcanvas
except ImportError as exc:  # keep ImportError so the parity eval test can skip cleanly
    raise ImportError(
        "reportlab is required to regenerate the eval corpus "
        "(install with: pip install reportlab). The committed PDFs remain the "
        "source of truth for offline test runs."
    ) from exc

PAGE_W, PAGE_H = A4
MARGIN = 54.0
FONT_NAME = "LedgerEvalSans"
ENGINE_TAG = "reportlab-invariant"

# --------------------------------------------------------------------------
# Font selection: a Unicode TTF covering every glyph the corpus prints.
# --------------------------------------------------------------------------
FONT_CANDIDATES = [
    "C:/Windows/Fonts/nirmala.ttf",    # Nirmala UI (Indic + Latin) — ₹
    "C:/Windows/Fonts/seguisym.ttf",   # Segoe UI Symbol — ₹
    "C:/Windows/Fonts/arial.ttf",
    "C:/Windows/Fonts/calibri.ttf",
    "C:/Windows/Fonts/times.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    "/usr/share/fonts/truetype/noto/NotoSans-Regular.ttf",
    "/Library/Fonts/Arial Unicode.ttf",
]

# ₹ € £ ü é ö ä — (rupee, euro, pound, Münchner, Métrologie, Montréal, Präzisions)
REQUIRED_GLYPHS = (0x20B9, 0x20AC, 0x00A3, 0x00FC, 0x00E9, 0x00F6, 0x00E4)


def _select_font_path() -> str:
    """First candidate TTF whose cmap covers every required glyph."""
    for raw in FONT_CANDIDATES:
        path = Path(raw)
        if not path.is_file():
            continue
        try:
            face = TTFontFile(str(path))
        except Exception:
            continue
        if all(cp in face.charToGlyph for cp in REQUIRED_GLYPHS):
            return str(path)
    raise ImportError(
        "No font covering the corpus glyphs (₹/€/£) was found; install a "
        "Unicode font such as Nirmala UI, Arial, Calibri or DejaVu Sans."
    )


_FONT_REGISTERED = False


def _ensure_font() -> None:
    global _FONT_REGISTERED
    if not _FONT_REGISTERED:
        pdfmetrics.registerFont(TTFont(FONT_NAME, _select_font_path()))
        _FONT_REGISTERED = True


# --------------------------------------------------------------------------
# Money / date formatting helpers (locale-correct, fully deterministic).
# --------------------------------------------------------------------------
def _q2(value: Decimal) -> Decimal:
    return value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def format_indian(value: Decimal) -> str:
    """Indian lakh/crore grouping: 123456.00 -> '1,23,456.00'."""
    q = _q2(value)
    sign = "-" if q < 0 else ""
    digits = format(abs(q), "f")
    int_part, _, frac = digits.partition(".")
    if len(int_part) > 3:
        head, tail = int_part[:-3], int_part[-3:]
        groups = []
        while len(head) > 2:
            groups.insert(0, head[-2:])
            head = head[:-2]
        if head:
            groups.insert(0, head)
        int_part = ",".join(groups + [tail])
    return "%s%s.%s" % (sign, int_part, frac)


def format_grouped(value: Decimal) -> str:
    """US/UK grouping with decimal point: 1234.56 -> '1,234.56'."""
    return format(_q2(value), ",.2f")


def format_eu(value: Decimal) -> str:
    """European decimal-comma: 1234.56 -> '1.234,56'."""
    grouped = format(_q2(value), ",.2f")
    return grouped.replace(",", "\x01").replace(".", ",").replace("\x01", ".")


def _date_str(iso_date: str, locale_code: str) -> str:
    """Print the locale date (IN/FR/UK DD/MM/YYYY, US/CA MM/DD/YYYY, DE DD.MM.YYYY)."""
    year, month, day = iso_date.split("-")
    if locale_code in ("US", "CA"):
        return "%s/%s/%s" % (month, day, year)
    if locale_code == "DE":
        return "%s.%s.%s" % (day, month, year)
    return "%s/%s/%s" % (day, month, year)


LOCALE_STYLES = {
    "IN": {
        "title": "TAX INVOICE",
        "tax_id_label": "GSTIN:",
        "money": lambda d: "\u20b9" + format_indian(d),
        "tax_line_labels": ("CGST 9%:", "SGST 9%:"),
        "currency_label": "Currency: INR",
    },
    "US": {
        "title": "INVOICE",
        "tax_id_label": "EIN:",
        "money": lambda d: "$" + format_grouped(d),
        "tax_line_labels": ("Sales Tax 8.25%:",),
        "currency_label": "Currency: USD",
    },
    "CA": {
        "title": "INVOICE",
        "tax_id_label": "BN:",
        "money": lambda d: "C$" + format_grouped(d),
        "tax_line_labels": ("GST 5% + QST 9.975%:",),
        "currency_label": "Currency: CAD",
    },
    "DE": {
        "title": "RECHNUNG",
        "tax_id_label": "USt-IdNr.:",
        "money": lambda d: format_eu(d) + " \u20ac",
        "tax_line_labels": ("MwSt. 19%:",),
        "currency_label": "W\u00e4hrung: EUR",
    },
    "FR": {
        "title": "FACTURE",
        "tax_id_label": "Num\u00e9ro TVA:",
        "money": lambda d: "\u20ac " + format_eu(d),
        "tax_line_labels": ("TVA 20%:",),
        "currency_label": "Devise: EUR",
    },
    "UK": {
        "title": "VAT INVOICE",
        "tax_id_label": "VAT No.:",
        "money": lambda d: "\u00a3" + format_grouped(d),
        "tax_line_labels": ("VAT 20%:",),
        "currency_label": "Currency: GBP",
    },
}


# --------------------------------------------------------------------------
# Golden spec table: 12 voices, 4 buckets (3 IN / 3 US-CA / 3 EU-UK / 3 noisy).
# Money amounts are computed with Decimal at build time and asserted.
# --------------------------------------------------------------------------
def _ok() -> dict:
    return {"consistent": True, "variance": 0.0, "variance_field": None}


def _line(item, qty, price, pct):
    return {"item": item, "quantity": qty, "unit_price": price, "tax_pct": pct}


def _compute_totals(lines, printed_overrides=None):
    """Decimal-exact totals: per-line gross HALF_UP at 2dp; tax = sum of line taxes."""
    computed = []
    subtotal = Decimal("0")
    gross_sum = Decimal("0")
    for ln in lines:
        qty = Decimal(str(ln["quantity"]))
        price = Decimal(str(ln["unit_price"]))
        pct = Decimal(str(ln["tax_pct"]))
        pre_tax = _q2(qty * price)
        gross = _q2(pre_tax * (Decimal("1") + pct / Decimal("100")))
        subtotal += pre_tax
        gross_sum += gross
        computed.append({"pre_tax": pre_tax, "gross": gross})
    printed = []
    for idx, ln in enumerate(lines):
        if printed_overrides and idx in printed_overrides:
            printed.append(Decimal(str(printed_overrides[idx])))
        else:
            printed.append(computed[idx]["gross"])
    printed_sum = sum(printed, Decimal("0"))
    return {
        "subtotal": _q2(subtotal),
        "tax": _q2(gross_sum - subtotal),
        "grand_total": _q2(gross_sum),
        "printed_line_totals": printed,
        "printed_line_total_sum": _q2(printed_sum),
        "gross_line_totals": [c["gross"] for c in computed],
        "gross_sum": _q2(gross_sum),
    }


VOICE_IN_REVISION_LAKH = "in_gst_revision_lakh"
VOICE_IN_CRORE = "in_gst_crore"
VOICE_IN_MULTILINE = "in_gst_multiline"
VOICE_US_SALES_TAX = "us_sales_tax"
VOICE_CA_GST_QST = "ca_gst_qst"
VOICE_US_MULTILINE = "us_multiline"
VOICE_DE_MWST = "de_mwst_decimal_comma"
VOICE_FR_TVA = "fr_tva_decimal_comma"
VOICE_UK_VAT = "uk_vat"
VOICE_NOISY_WRAPPED = "noisy_wrapped_multiline"
VOICE_NOISY_EXEMPT = "noisy_tax_exempt"
VOICE_NOISY_MISMATCH = "noisy_math_mismatch"

EXPECTED_VOICES = frozenset({
    VOICE_IN_REVISION_LAKH,
    VOICE_IN_CRORE,
    VOICE_IN_MULTILINE,
    VOICE_US_SALES_TAX,
    VOICE_CA_GST_QST,
    VOICE_US_MULTILINE,
    VOICE_DE_MWST,
    VOICE_FR_TVA,
    VOICE_UK_VAT,
    VOICE_NOISY_WRAPPED,
    VOICE_NOISY_EXEMPT,
    VOICE_NOISY_MISMATCH,
})

# Buckets: 1-3 Indian GST, 4-6 US/Canada, 7-9 EU/UK, 10-12 noisy/tricky.
SPECS = [
    {
        "file": "eval_invoice_01_in_gst_revision_lakh.pdf",
        "locale": "IN",
        "voice": VOICE_IN_REVISION_LAKH,
        "difficulty": "medium",
        "line_tax_text": "CGST 9% + SGST 9%",
        "vendor": {"name": "Sunbeam Electricals Pvt Ltd", "tax_id": "27AABCS1234F1Z5"},
        "address": ["Plot 14, MIDC Industrial Area", "Pune, Maharashtra 411019"],
        "number": "INV-8821-R2",
        "date": "2026-11-15",
        "po": "PO-1006",
        "terms": "Net 30",
        "currency": "INR",
        "lines": [_line("Industrial LED Panel", 2, "123456.00", 18)],
        "arithmetic": _ok(),
        "expect_needs_review": False,
    },
    {
        "file": "eval_invoice_02_in_gst_crore.pdf",
        "locale": "IN",
        "voice": VOICE_IN_CRORE,
        "difficulty": "medium",
        "line_tax_text": "CGST 9% + SGST 9%",
        "vendor": {"name": "Bharat Forge Industries Ltd", "tax_id": "29AAECB1234K1Z9"},
        "address": ["Gate 3, Bhosari Industrial Estate", "Pune, Maharashtra 411026"],
        "number": "INV-2026-7741",
        "date": "2026-10-03",
        "po": "PO-4471",
        "terms": "Net 45",
        "currency": "INR",
        "lines": [_line("CNC Machined Flange Assembly", 500, "18500.00", 18)],
        "arithmetic": _ok(),
        "expect_needs_review": False,
    },
    {
        "file": "eval_invoice_03_in_gst_multiline.pdf",
        "locale": "IN",
        "voice": VOICE_IN_MULTILINE,
        "difficulty": "medium",
        "line_tax_text": "CGST 9% + SGST 9%",
        "vendor": {"name": "Chennai Precision Tools Pvt Ltd", "tax_id": "33AAKCC5678M1Z3"},
        "address": ["Unit 7, Guindy Industrial Estate", "Chennai, Tamil Nadu 600032"],
        "number": "INV-TP-9042",
        "date": "2026-11-21",
        "po": "PO-9012",
        "terms": "Net 45",
        "currency": "INR",
        "lines": [
            _line("Carbide Insert Pack TNMG16", 40, "1850.00", 18),
            _line("Digital Caliper 200mm", 6, "4200.00", 18),
            _line("Coolant Concentrate 20L", 12, "2650.00", 18),
        ],
        "arithmetic": _ok(),
        "expect_needs_review": False,
    },
    {
        "file": "eval_invoice_04_us_sales_tax.pdf",
        "locale": "US",
        "voice": VOICE_US_SALES_TAX,
        "difficulty": "easy",
        "line_tax_text": "8.25%",
        "vendor": {"name": "Acme Industrial Supply Inc", "tax_id": "82-1234567"},
        "address": ["2400 Commerce Boulevard", "Cleveland, OH 44114"],
        "number": "INV-US-2026-014",
        "date": "2026-11-15",
        "po": "PO-7788",
        "terms": "Net 30",
        "currency": "USD",
        "lines": [_line("Steel Bracket Kit", 3, "1234.56", "8.25")],
        "arithmetic": _ok(),
        "expect_needs_review": False,
    },
    {
        "file": "eval_invoice_05_ca_gst_qst.pdf",
        "locale": "CA",
        "voice": VOICE_CA_GST_QST,
        "difficulty": "hard",
        "line_tax_text": "GST 5% + QST 9.975%",
        "vendor": {"name": "Laurentien Distribution Inc", "tax_id": "123456789 RT0001"},
        "address": ["4120 Rue Sainte-Catherine Ouest", "Montr\u00e9al, QC H3Z 1P4"],
        "number": "INV-QC-5521",
        "date": "2026-12-01",
        "po": "PO-3310",
        "terms": "Net 30",
        "currency": "CAD",
        "lines": [_line("Wall-Mount Storage Rack", 4, "289.75", "14.975")],
        "arithmetic": _ok(),
        "expect_needs_review": False,
    },
    {
        "file": "eval_invoice_06_us_multiline.pdf",
        "locale": "US",
        "voice": VOICE_US_MULTILINE,
        "difficulty": "medium",
        "line_tax_text": "7.5%",
        "vendor": {"name": "Pacific Ridge Manufacturing LLC", "tax_id": "91-1876543"},
        "address": ["881 Harbor Bay Parkway", "Alameda, CA 94502"],
        "number": "INV-PRM-1187",
        "date": "2026-10-31",
        "po": "PO-8823",
        "terms": "Net 45",
        "currency": "USD",
        "lines": [
            _line("Aluminum Sheet 6061 3mm", 12, "86.40", "7.5"),
            _line("Hex Bolt M10 Pack", 25, "4.85", "7.5"),
            _line("Anodizing Service", 1, "950.00", "7.5"),
        ],
        "arithmetic": _ok(),
        "expect_needs_review": False,
    },
    {
        "file": "eval_invoice_07_de_mwst_decimal_comma.pdf",
        "locale": "DE",
        "voice": VOICE_DE_MWST,
        "difficulty": "medium",
        "line_tax_text": "MwSt. 19%",
        "vendor": {"name": "M\u00fcnchner Maschinenbau GmbH", "tax_id": "DE812345678"},
        "address": ["Landsberger Stra\u00dfe 110", "80339 M\u00fcnchen"],
        "number": "RE-2026-0342",
        "date": "2026-12-02",
        "po": "PO-DE-776",
        "terms": "Net 30",
        "currency": "EUR",
        "lines": [_line("Pr\u00e4zisions-L\u00e4ngsmessger\u00e4t", 2, "1234.56", 19)],
        "arithmetic": _ok(),
        "expect_needs_review": False,
    },
    {
        "file": "eval_invoice_08_fr_tva_decimal_comma.pdf",
        "locale": "FR",
        "voice": VOICE_FR_TVA,
        "difficulty": "medium",
        "line_tax_text": "TVA 20%",
        "vendor": {"name": "Paris M\u00e9trologie SARL", "tax_id": "FR32456789012"},
        "address": ["17 Rue de la R\u00e9publique", "75011 Paris"],
        "number": "FACT-2026-118",
        "date": "2026-11-18",
        "po": "PO-FR-224",
        "terms": "Net 30",
        "currency": "EUR",
        "lines": [_line("Station de mesure dimensionnelle", 3, "745.00", 20)],
        "arithmetic": _ok(),
        "expect_needs_review": False,
    },
    {
        "file": "eval_invoice_09_uk_vat.pdf",
        "locale": "UK",
        "voice": VOICE_UK_VAT,
        "difficulty": "easy",
        "line_tax_text": "20%",
        "vendor": {"name": "Albion Engineering Ltd", "tax_id": "GB123456789"},
        "address": ["Unit 9, Trafford Park Road", "Manchester M17 1AA"],
        "number": "INV-UK-3098",
        "date": "2026-12-07",
        "po": "PO-UK-551",
        "terms": "Net 30",
        "currency": "GBP",
        "lines": [_line("Hydraulic Pressure Gauge", 5, "123.40", 20)],
        "arithmetic": _ok(),
        "expect_needs_review": False,
    },
    {
        "file": "eval_invoice_10_noisy_wrapped_multiline.pdf",
        "locale": "IN",
        "voice": VOICE_NOISY_WRAPPED,
        "difficulty": "hard",
        "line_tax_text": "CGST 9% + SGST 9%",
        "vendor": {"name": "Kolkata Print & Packaging Co", "tax_id": "19AAJCK4321P1ZQ"},
        "address": ["22 Netaji Subhas Road", "Kolkata, West Bengal 700001"],
        "number": "INV-KP-2026-310",
        "date": "2026-11-09",
        "po": "PO-6655",
        "terms": "Net 30",
        "currency": "INR",
        "stamp": "DUPLICATE COPY \u2014 FOR RECIPIENT",
        "footer": "Goods once sold will not be taken back. Subject to Kolkata jurisdiction only.",
        "lines": [
            _line(
                "Laminated Packaging Film Roll 500mm x 1000m Food Grade Moisture Barrier with Heat Seal Coating",
                120, "425.50", 18,
            ),
            _line(
                "Corrugated Box Blank 5-Ply 450x350x250mm Bundle of 50 Sheets Kraft Finish",
                8, "11480.00", 18,
            ),
            _line(
                "Flexible Pouch Printing Ink Set CMYK Low Migration Food Contact Certified",
                35, "1265.25", 18,
            ),
            _line(
                "Rotogravure Cylinder Engraving Service Per Design Set Multi Repeat",
                3, "28900.00", 18,
            ),
        ],
        "arithmetic": _ok(),
        "expect_needs_review": False,
    },
    {
        "file": "eval_invoice_11_noisy_tax_exempt.pdf",
        "locale": "UK",
        "voice": VOICE_NOISY_EXEMPT,
        "difficulty": "hard",
        "line_tax_text": "Exempt",
        "vendor": {"name": "Thames Medical Supplies Ltd", "tax_id": "GB987654321"},
        "address": ["5 Riverside Business Park", "London SW18 4UQ"],
        "number": "INV-TMS-0442",
        "date": "2026-11-14",
        "po": "PO-UK-773",
        "terms": "Net 30",
        "currency": "GBP",
        "exempt": True,
        "lines": [
            _line("Sterile Surgical Gloves Size 8 Box of 100", 6, "340.00", 0),
            _line("Digital Thermometer Non-Contact Medical Grade", 3, "1250.00", 0),
        ],
        "arithmetic": _ok(),
        "expect_needs_review": False,
    },
    {
        # Intentional math mismatch: printed line 2 line_total is +120.00 above
        # the correct qty*price*(1+tax). Subtotal / Tax / Grand Total are printed
        # from the CORRECT math (the classic drifted-line document). Extraction
        # must return the printed values and the deterministic verifier must
        # flag needs_review instead of accepting the bad line.
        "file": "eval_invoice_12_noisy_math_mismatch.pdf",
        "locale": "US",
        "voice": VOICE_NOISY_MISMATCH,
        "difficulty": "hard",
        "line_tax_text": "8.25%",
        "vendor": {"name": "Grandview Office Depot LLC", "tax_id": "47-2233445"},
        "address": ["1420 Grandview Avenue", "Columbus, OH 43212"],
        "number": "INV-GV-2026-091",
        "date": "2026-11-05",
        "po": "PO-9902",
        "terms": "Net 30",
        "currency": "USD",
        "printed_overrides": {1: "899.40"},  # correct 779.40 + 120.00 drift
        "lines": [
            _line("Copy Paper A4 80gsm Box", 10, "45.00", "8.25"),
            _line("Toner Cartridge Black", 6, "120.00", "8.25"),
            _line("Desk Organizer Set", 4, "250.00", "8.25"),
        ],
        "arithmetic": {"consistent": False, "variance": 120.0, "variance_field": "line_total"},
        "expect_needs_review": True,
    },
]


# --------------------------------------------------------------------------
# Ground truth / manifest assembly (ExtractedInvoicePayload field names).
# --------------------------------------------------------------------------
def _ground_truth(spec, totals) -> dict:
    return {
        "vendor": {"name": spec["vendor"]["name"], "tax_id": spec["vendor"]["tax_id"]},
        "invoice": {
            "number": spec["number"],
            "date": spec["date"],
            "currency": spec["currency"],
            "po_reference": spec["po"],
            "payment_terms": spec["terms"],
        },
        "lines": [
            {
                "item": ln["item"],
                "quantity": float(ln["quantity"]),
                "unit_price": float(ln["unit_price"]),
                "tax_pct": float(ln["tax_pct"]),
                "line_total": float(totals["printed_line_totals"][idx]),
            }
            for idx, ln in enumerate(spec["lines"])
        ],
        "totals": {
            "subtotal": float(totals["subtotal"]),
            "tax": float(totals["tax"]),
            "grand_total": float(totals["grand_total"]),
        },
    }


def _expected_view(spec, ground_truth) -> dict:
    """Prompt-schema flat view of the ground truth."""
    return {
        "vendor_name": ground_truth["vendor"]["name"],
        "vendor_tax_id": ground_truth["vendor"]["tax_id"],
        "invoice_number": ground_truth["invoice"]["number"],
        "invoice_date": ground_truth["invoice"]["date"],
        "currency": ground_truth["invoice"]["currency"],
        "po_reference": ground_truth["invoice"]["po_reference"],
        "payment_terms": ground_truth["invoice"]["payment_terms"],
        "subtotal": ground_truth["totals"]["subtotal"],
        "tax": ground_truth["totals"]["tax"],
        "grand_total": ground_truth["totals"]["grand_total"],
        "lines": [
            {
                "item": ln["item"],
                "quantity": ln["quantity"],
                "unit_price": ln["unit_price"],
                "tax_pct": ln["tax_pct"],
                "line_total": ln["line_total"],
            }
            for ln in ground_truth["lines"]
        ],
    }


def _assert_spec_consistency(spec, totals) -> None:
    """Golden numbers must balance exactly unless the spec declares a variance."""
    arithmetic = spec["arithmetic"]
    if arithmetic["consistent"]:
        for idx, ln in enumerate(spec["lines"]):
            correct = totals["gross_line_totals"][idx]
            printed = totals["printed_line_totals"][idx]
            assert abs(printed - correct) <= Decimal("0.01"), (
                "%s: line %d printed %s vs computed %s" % (spec["file"], idx, printed, correct)
            )
        assert totals["grand_total"] == totals["subtotal"] + totals["tax"], spec["file"]
    else:
        variance_field = arithmetic["variance_field"]
        variance = Decimal(str(arithmetic["variance"]))
        assert variance_field == "line_total", spec["file"]
        drift = totals["printed_line_total_sum"] - totals["gross_sum"]
        assert abs(drift) == variance, (
            "%s: declared variance %s, actual %s" % (spec["file"], variance, abs(drift))
        )
        # Undeviated fields still balance exactly.
        assert totals["grand_total"] == totals["subtotal"] + totals["tax"], spec["file"]


# --------------------------------------------------------------------------
# PDF rendering (reportlab, invariant mode, uncompressed streams).
# --------------------------------------------------------------------------
COL_ITEM_X = MARGIN
COL_ITEM_W = 218.0
COL_QTY_X = 306.0
COL_UNIT_X = 382.0
COL_TAX_X = 452.0
COL_TOTAL_X = PAGE_W - MARGIN
LINE_H = 13.0
TABLE_HEADER_Y_GAP = 6.0


def _right(c, text, x, y, size=9.0):
    c.setFont(FONT_NAME, size)
    c.drawRightString(x, y, text)


def _left(c, text, x, y, size=9.0):
    c.setFont(FONT_NAME, size)
    c.drawString(x, y, text)


def render_pdf_bytes(spec, totals) -> bytes:
    """Render one deterministic one-page invoice PDF."""
    _ensure_font()
    style = LOCALE_STYLES[spec["locale"]]
    money = style["money"]

    buf = io.BytesIO()
    c = pdfcanvas.Canvas(buf, pagesize=A4, invariant=1, pageCompression=0)
    c.setTitle("LedgerLens Eval Invoice %s" % spec["number"])
    c.setAuthor(spec["vendor"]["name"])
    c.setProducer("LedgerLens Golden Eval")

    y = PAGE_H - 58.0
    if spec.get("stamp"):
        c.setFont(FONT_NAME, 9)
        c.setFillColorRGB(0.55, 0.0, 0.0)
        c.drawCentredString(PAGE_W / 2.0, y, spec["stamp"])
        c.setFillColorRGB(0.0, 0.0, 0.0)
        y -= LINE_H + 4.0

    # Vendor block (left) + document title (right).
    _left(c, spec["vendor"]["name"], MARGIN, y, 12.5)
    _right(c, style["title"], COL_TOTAL_X, y, 14)
    y -= LINE_H
    for addr_line in spec["address"]:
        _left(c, addr_line, MARGIN, y, 8.5)
        y -= LINE_H - 2.0
    _left(c, "%s %s" % (style["tax_id_label"], spec["vendor"]["tax_id"]), MARGIN, y, 8.5)
    y -= LINE_H + 8.0

    # Invoice meta block.
    meta = [
        ("Invoice No: %s" % spec["number"], 10),
        ("Invoice Date: %s" % _date_str(spec["date"], spec["locale"]), 9),
        ("PO Reference: %s" % spec["po"], 9),
        ("Payment Terms: %s" % spec["terms"], 9),
        (style["currency_label"], 9),
    ]
    for text, size in meta:
        _left(c, text, MARGIN, y, size)
        y -= LINE_H + (2.0 if size >= 10 else 0.0)
    y -= 6.0

    # Table header.
    _left(c, "Item", COL_ITEM_X, y, 9)
    _right(c, "Qty", COL_QTY_X, y)
    _right(c, "Unit Price", COL_UNIT_X, y)
    _right(c, "Tax", COL_TAX_X, y)
    _right(c, "Line Total", COL_TOTAL_X, y)
    y -= TABLE_HEADER_Y_GAP
    c.line(MARGIN, y, COL_TOTAL_X, y)
    y -= LINE_H

    for idx, ln in enumerate(spec["lines"]):
        wrapped = simpleSplit(ln["item"], FONT_NAME, 8.5, COL_ITEM_W)
        row_top = y
        for piece in wrapped:
            _left(c, piece, COL_ITEM_X, y, 8.5)
            y -= LINE_H - 1.0
        _right(c, format(ln["quantity"], "g"), COL_QTY_X, row_top)
        _right(c, money(Decimal(str(ln["unit_price"]))), COL_UNIT_X, row_top)
        _right(c, spec["line_tax_text"], COL_TAX_X, row_top)
        _right(c, money(totals["printed_line_totals"][idx]), COL_TOTAL_X, row_top)
        y -= 3.0

    c.line(MARGIN, y + 6.0, COL_TOTAL_X, y + 6.0)
    y -= 10.0

    # Totals block (printed from the spec's declared golden math).
    _right(c, "Subtotal:", COL_UNIT_X, y)
    _right(c, money(totals["subtotal"]), COL_TOTAL_X, y)
    y -= LINE_H
    labels = style["tax_line_labels"]
    if spec.get("exempt"):
        _right(c, "VAT (Exempt \u2014 Zero-rated):", COL_UNIT_X, y)
        _right(c, money(Decimal("0")), COL_TOTAL_X, y)
        y -= LINE_H
    elif len(labels) == 2:  # IN split GST
        tax = totals["tax"]
        cgst = _q2(tax / Decimal("2"))
        sgst = tax - cgst
        _right(c, labels[0], COL_UNIT_X, y)
        _right(c, money(cgst), COL_TOTAL_X, y)
        y -= LINE_H
        _right(c, labels[1], COL_UNIT_X, y)
        _right(c, money(sgst), COL_TOTAL_X, y)
        y -= LINE_H
    else:
        _right(c, labels[0], COL_UNIT_X, y)
        _right(c, money(totals["tax"]), COL_TOTAL_X, y)
        y -= LINE_H

    c.setLineWidth(0.9)
    c.line(COL_UNIT_X - 80.0, y + 4.0, COL_TOTAL_X, y + 4.0)
    _right(c, "Grand Total:", COL_UNIT_X, y - 2.0, 10)
    _right(c, money(totals["grand_total"]), COL_TOTAL_X, y - 2.0, 10)
    y -= LINE_H + 14.0

    if spec.get("footer"):
        _left(c, spec["footer"], MARGIN, y, 7.5)

    c.showPage()
    c.save()
    return buf.getvalue()


# --------------------------------------------------------------------------
# Corpus / manifest builders (stable API used by the regeneration-parity test).
# --------------------------------------------------------------------------
def _totals_for(spec) -> dict:
    overrides = None
    if "printed_overrides" in spec:
        overrides = {k: Decimal(str(v)) for k, v in spec["printed_overrides"].items()}
    return _compute_totals(spec["lines"], overrides)


def build_corpus() -> dict:
    """Render every golden PDF in memory: {filename: pdf_bytes}."""
    corpus = {}
    for spec in SPECS:
        totals = _totals_for(spec)
        _assert_spec_consistency(spec, totals)
        corpus[spec["file"]] = render_pdf_bytes(spec, totals)
    return corpus


def build_manifest_entries(pdf_bytes_by_name) -> list:
    """Build manifest entries (prompt schema + engineering extensions)."""
    entries = []
    for spec in SPECS:
        totals = _totals_for(spec)
        pdf_bytes = pdf_bytes_by_name[spec["file"]]
        ground_truth = _ground_truth(spec, totals)
        entries.append(
            {
                "filename": spec["file"],
                "locale": spec["locale"],
                "voice": spec["voice"],
                "difficulty": spec["difficulty"],
                "mime_type": "application/pdf",
                "engine": ENGINE_TAG,
                "sha256": hashlib.sha256(pdf_bytes).hexdigest(),
                "bytes": len(pdf_bytes),
                "expect_needs_review": spec["expect_needs_review"],
                "arithmetic": {
                    "consistent": spec["arithmetic"]["consistent"],
                    "variance": spec["arithmetic"]["variance"],
                    "variance_field": spec["arithmetic"]["variance_field"],
                },
                "expected": _expected_view(spec, ground_truth),
            }
        )
    return entries


def build_manifest(pdf_bytes_by_name) -> list:
    """manifest.json content: a top-level LIST of 12 entries (prompt schema)."""
    return build_manifest_entries(pdf_bytes_by_name)


def manifest_to_bytes(manifest: list) -> bytes:
    return (json.dumps(manifest, indent=2) + "\n").encode("utf-8")


# Fixed allowlist of writable/readable corpus filenames; every write/read
# resolves through _safe_corpus_path and is provably contained inside
# CORPUS_DIR (fail-closed against path traversal).
_ALLOWED_CORPUS_FILES = frozenset(spec["file"] for spec in SPECS) | {MANIFEST_NAME}


def _safe_corpus_path(name: str) -> Path:
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


def verify_pdf_bytes(data: bytes, label: str) -> list:
    """Strict structural checks; returns a list of problems (empty == valid)."""
    problems = []
    if not data.startswith(b"%PDF-"):
        problems.append("%s: does not start with %%PDF- magic" % label)
    # A conformant PDF ends with the %%EOF marker (pypdf refuses otherwise).
    if not data.rstrip(b"\r\n").endswith(b"%%EOF"):
        problems.append("%s: does not end with %%EOF" % label)
    if len(data) <= 500:
        problems.append("%s: suspiciously small (%d bytes)" % (label, len(data)))
    if b"startxref" not in data:
        problems.append("%s: no startxref token" % label)
    if b"FontFile2" not in data:
        problems.append("%s: embedded Unicode TTF subset (FontFile2) missing" % label)
    return problems


def _pypdf_text(pdf_bytes: bytes) -> str:
    try:
        from pypdf import PdfReader
    except ImportError:
        return ""
    reader = PdfReader(io.BytesIO(pdf_bytes))
    return "\n".join((page.extract_text() or "") for page in reader.pages)


def _verify_text_layers(corpus) -> int:
    """pypdf round-trip: vendor name + invoice number + locale glyphs must survive extraction."""
    if not corpus:
        return 0
    try:
        import pypdf  # noqa: F401
    except ImportError:
        print("SKIP pypdf not installed; text-layer round-trip not verified")
        return 0
    failures = 0
    for spec in SPECS:
        text = _pypdf_text(corpus[spec["file"]])
        problems = []
        if text == "":
            problems.append("pypdf could not parse/extract text")
        else:
            if spec["vendor"]["name"] not in text:
                problems.append("vendor name missing from extracted text")
            if spec["number"] not in text:
                problems.append("invoice number missing from extracted text")
            if spec["locale"] == "IN" and "\u20b9" not in text:
                problems.append("rupee glyph missing from extracted text")
            if spec["locale"] in ("DE", "FR") and "\u20ac" not in text:
                problems.append("euro glyph missing from extracted text")
            if spec["locale"] == "UK" and "\u00a3" not in text:
                problems.append("pound glyph missing from extracted text")
        for problem in problems:
            print("ERROR %s: %s" % (spec["file"], problem))
        failures += len(problems)
        print("TEXT %-44s chars=%-5d ok=%s" % (spec["file"], len(text), not problems))
    return failures


def _write_corpus() -> int:
    corpus = build_corpus()
    manifest = build_manifest(corpus)
    failures = 0
    for spec in SPECS:
        name = spec["file"]
        pdf_bytes = corpus[name]
        problems = verify_pdf_bytes(pdf_bytes, name)
        _safe_corpus_path(name).write_bytes(pdf_bytes)
        on_disk = _read_disk(name)
        if on_disk != pdf_bytes:
            problems.append("on-disk bytes differ from built bytes")
        for problem in problems:
            print("ERROR " + problem)
        failures += len(problems)
        print("WROTE %-44s bytes=%-6d sha256=%s" % (name, len(pdf_bytes), hashlib.sha256(pdf_bytes).hexdigest()))
    manifest_data = manifest_to_bytes(manifest)
    _safe_corpus_path(MANIFEST_NAME).write_bytes(manifest_data)
    print("WROTE %-44s bytes=%-6d" % (MANIFEST_NAME, len(manifest_data)))

    failures += _verify_text_layers(corpus)
    if failures:
        print("GENERATION FAILED: %d problem(s)" % failures)
        return 1
    print("OK: wrote %d PDFs + %s (all structurally verified, text layers round-trip)" % (len(corpus), MANIFEST_NAME))
    return 0


def _check() -> int:
    corpus = build_corpus()
    manifest_data = manifest_to_bytes(build_manifest(corpus))
    mismatches = 0
    for spec in SPECS:
        name = spec["file"]
        expected = corpus[name]
        on_disk = _read_disk(name)
        if on_disk is None:
            print("DIFF %s: MISSING on disk" % name)
            mismatches += 1
        elif on_disk == expected:
            print("OK   %-44s bytes=%-6d sha256=%s" % (name, len(on_disk), hashlib.sha256(on_disk).hexdigest()))
        else:
            print("DIFF %s: on-disk bytes differ from recomputed bytes" % name)
            mismatches += 1
    on_disk_manifest = _read_disk(MANIFEST_NAME)
    if on_disk_manifest is None:
        print("DIFF %s: MISSING on disk" % MANIFEST_NAME)
        mismatches += 1
    elif on_disk_manifest != manifest_data:
        print("DIFF %s: on-disk bytes differ from recomputed manifest" % MANIFEST_NAME)
        mismatches += 1
    else:
        print("OK   %-44s bytes=%-6d" % (MANIFEST_NAME, len(on_disk_manifest)))
    if mismatches:
        print("CHECK FAILED: %d mismatch(es)" % mismatches)
        return 1
    print("CHECK OK: %d PDFs + %s byte-identical to the deterministic recomputation" % (len(corpus), MANIFEST_NAME))
    return 0


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        prog="generate_corpus.py",
        description=(
            "Deterministically build the golden locale-diverse eval corpus "
            "(12 invoice PDFs + manifest.json) next to this script."
        ),
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="verify the on-disk corpus against an in-memory recomputation; exit 1 on any mismatch",
    )
    args = parser.parse_args(argv)
    return _check() if args.check else _write_corpus()


if __name__ == "__main__":
    sys.exit(main())

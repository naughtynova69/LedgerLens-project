"""Deterministic data cleanup — the layer between Gemini extraction and detection.

Rules (docs/02):
- Same input ALWAYS produces the same output (no LLM here).
- Vendor names collapse to a comparable canonical form.
- Invoice numbers canonicalize to alphanumeric keys for fuzzy matching.
- Dates normalize to ISO-8601 (YYYY-MM-DD).
- Currency symbols/codes map to ISO-4217; amounts become floats.
"""
from __future__ import annotations

from datetime import datetime
import re

# Tokens stripped from the END of vendor names so "Sunbeam Electricals Pvt Ltd"
# and "SUNBEAM ELECTRICALS PVT. LTD." normalize to the same key.
LEGAL_SUFFIXES = {
    "PVT", "PRIVATE", "LTD", "LIMITED", "LLP", "INC", "LLC",
    "CO", "COMPANY", "CORP", "CORPORATION", "ENTERPRISES", "TRADERS",
}

SYMBOL_TO_ISO = {
    "₹": "INR", "RS": "INR", "RS.": "INR", "INR.": "INR",
    "$": "USD", "US$": "USD", "USD$": "USD",
    "€": "EUR", "£": "GBP",
}

# Demo reference FX rates (2026-11) for the R4 fx-error check.
# PRODUCTION: replace with a rates API — do not hardcode live rates.
REFERENCE_FX_RATES = {
    "INR": 1.0,
    "USD": 88.0,
    "EUR": 95.0,
    "GBP": 112.0,
}

_DATE_FORMATS = (
    "%Y-%m-%d",
    "%Y/%m/%d",
    "%d/%m/%Y",
    "%d-%m-%Y",
    "%d %b %Y",
    "%d %B %Y",
    "%b %d, %Y",
    "%B %d, %Y",
    "%m/%d/%Y",
)


def normalize_vendor_name(raw: str) -> str:
    """'SUNBEAM ELECTRICALS PVT. LTD.' -> 'SUNBEAM ELECTRICALS'."""
    cleaned = re.sub(r"[^\w\s]", " ", str(raw or "")).upper()
    tokens = [t for t in cleaned.split() if t and t not in LEGAL_SUFFIXES]
    return " ".join(tokens)


def canonical_vendor_key(raw: str) -> str:
    """'Sunbeam Electricals Pvt. Ltd.' -> 'sunbeam electricals' (lowercase canonical key)."""
    return normalize_vendor_name(raw).lower()


def normalize_invoice_number(raw: str) -> str:
    """'INV-8821-R2' / 'inv 8821 / r2' -> 'INV8821R2'."""
    return re.sub(r"[^A-Z0-9]", "", str(raw or "").upper())


def normalize_date(raw: str) -> str:
    """Parse common invoice date formats into ISO-8601 'YYYY-MM-DD'."""
    text = str(raw or "").strip()
    if not text:
        return ""
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", text):
        return text
    for fmt in _DATE_FORMATS:
        try:
            return datetime.strptime(text, fmt).strftime("%Y-%m-%d")
        except ValueError:
            continue
    return text


def normalize_currency(raw: str) -> str:
    """'₹' / 'Rs.' / 'INR' -> 'INR'; unknown codes pass through uppercased."""
    token = str(raw or "").strip().upper()
    return SYMBOL_TO_ISO.get(token, token)


def normalize_amount(raw: str | float | int) -> float:
    """'Rs. 4,956.00' -> 4956.0; unparseable input -> 0.0 (never raise)."""
    if isinstance(raw, (int, float)):
        return round(float(raw), 2)
    match = re.search(r"-?\d[\d,]*(?:\.\d+)?", str(raw or ""))
    if not match:
        return 0.0
    return round(float(match.group().replace(",", "")), 2)


def normalize_invoice_row(row: dict) -> dict:
    """Return a clean copy of an invoice line row with normalized fields."""
    out = dict(row)
    if "currency" in out and out["currency"] is not None:
        out["currency"] = normalize_currency(str(out["currency"]))
    if "invoice_date" in out and out["invoice_date"] is not None:
        out["invoice_date"] = normalize_date(str(out["invoice_date"]))
    for num_col in ("quantity", "unit_price", "tax_pct", "line_total"):
        if num_col in out and out[num_col] not in (None, ""):
            out[num_col] = normalize_amount(out[num_col])
    return out

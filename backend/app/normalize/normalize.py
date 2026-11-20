"""Deterministic data cleanup — the layer between Gemini extraction and detection.

Rules (docs/02):
- Same input ALWAYS produces the same output (no LLM here).
- Vendor names collapse to a comparable canonical form.
- Currency symbols/codes map to ISO-4217; amounts become floats.
"""
from __future__ import annotations

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


def normalize_vendor_name(raw: str) -> str:
    """'SUNBEAM ELECTRICALS PVT. LTD.' -> 'SUNBEAM ELECTRICALS'."""
    cleaned = re.sub(r"[^\w\s]", " ", str(raw or "")).upper()
    tokens = [t for t in cleaned.split() if t and t not in LEGAL_SUFFIXES]
    return " ".join(tokens)


def normalize_currency(raw: str) -> str:
    """'₹' / 'Rs.' / 'INR' -> 'INR'; unknown codes pass through uppercased."""
    token = str(raw or "").strip().upper()
    return SYMBOL_TO_ISO.get(token, token)


def normalize_amount(raw: str) -> float:
    """'Rs. 4,956.00' -> 4956.0; unparseable input -> 0.0 (never raise)."""
    match = re.search(r"-?\d[\d,]*(?:\.\d+)?", str(raw or ""))
    if not match:
        return 0.0
    return round(float(match.group().replace(",", "")), 2)

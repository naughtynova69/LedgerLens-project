"""Gemini extraction (docs/06 §3). Structured output, temperature 0, fail closed.

The `google-genai` package is imported lazily so the rest of the app (and the
test suite) runs without it installed.
"""
from __future__ import annotations

import json

from .. import config
from .schemas import CONTRACT_SCHEMA, INVOICE_SCHEMA

EXTRACTION_SYSTEM_PROMPT = """\
You are a data-entry engine for an accounts-payable audit system.
Extract fields from the provided invoice/contract document.
Return ONLY what is literally present in the document — never guess,
never infer missing values (leave them null).
Follow the provided JSON schema exactly.
Currency codes are ISO-4217 (e.g. INR, USD, EUR). Dates are YYYY-MM-DD.
If the document is a scan, read it; if a field is unreadable, return null.
"""


def _client():
    if not config.GEMINI_API_KEY:
        raise RuntimeError(
            "GEMINI_API_KEY is not set. Copy backend/.env.example to backend/.env "
            "and add your key from https://aistudio.google.com/apikey "
            "(docs/06_GEMINI_INTEGRATION.md)."
        )
    from google import genai  # lazy import

    return genai.Client(api_key=config.GEMINI_API_KEY)


def _generate(file_bytes: bytes, mime_type: str, schema: dict) -> dict:
    from google.genai import types  # lazy import

    response = _client().models.generate_content(
        model=config.GEMINI_MODEL,
        contents=[types.Part.from_bytes(data=file_bytes, mime_type=mime_type)],
        config=types.GenerateContentConfig(
            system_instruction=EXTRACTION_SYSTEM_PROMPT,
            temperature=0,
            response_mime_type="application/json",
            response_schema=schema,
        ),
    )
    parsed = json.loads(response.text)
    # Fail closed: log raw alongside parsed so the audit trail can reconstruct
    # exactly what the model returned (docs/02 §6).
    return parsed


def extract_invoice(pdf_bytes: bytes, mime_type: str = "application/pdf") -> dict:
    """Invoice PDF/scan -> canonical invoice JSON (INVOICE_SCHEMA)."""
    return _generate(pdf_bytes, mime_type, INVOICE_SCHEMA)


def extract_contract(pdf_bytes: bytes, mime_type: str = "application/pdf") -> dict:
    """Contract PDF/scan -> canonical contract JSON (CONTRACT_SCHEMA)."""
    return _generate(pdf_bytes, mime_type, CONTRACT_SCHEMA)

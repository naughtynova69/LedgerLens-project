"""Gemini explanation generator (docs/06 §4).

The rule decided WHAT happened, HOW MUCH is at risk, and HOW confident it is.
Gemini only packages it: narrator, not judge. Structured output enforces the
card shape so the dashboard can render every finding the same way.
"""
from __future__ import annotations

import json

from .. import config

EXPLANATION_SYSTEM_PROMPT = """\
You write findings for a corporate finance team. Input is a JSON finding
produced by a deterministic audit rule, with evidence references.
Rules:
- Explain in plain language a CFO can forward to procurement.
- Cite evidence fields exactly as given (record IDs, amounts). NEVER invent
  or recompute amounts, dates, or IDs — you are the narrator, not the judge.
- Structure: headline (max 12 words), explanation (3-6 sentences referencing
  the rule and evidence), recommended_action (1-2 sentences), limitations
  (what a human must confirm).
- Tone: precise, neutral, no scare words like "fraud" — say "duplicate risk".
"""

EXPLANATION_SCHEMA = {
    "type": "object",
    "properties": {
        "headline": {"type": "string"},
        "explanation": {"type": "string"},
        "recommended_action": {"type": "string"},
        "limitations": {"type": "string"},
        "confidence_label": {"type": "string"},
    },
}


def _client():
    if not config.GEMINI_API_KEY:
        raise RuntimeError(
            "GEMINI_API_KEY is not set — see docs/06_GEMINI_INTEGRATION.md. "
            "Use fallback_without_gemini() when no key is configured."
        )
    from google import genai

    return genai.Client(api_key=config.GEMINI_API_KEY)


def explain_finding(finding: dict) -> dict:
    """Finding dict (Finding.as_dict()) -> {headline, explanation, recommended_action,
    limitations, confidence_label}. Raises RuntimeError without an API key."""
    from google.genai import types

    response = _client().models.generate_content(
        model=config.GEMINI_MODEL,
        contents=[json.dumps(finding, ensure_ascii=False)],
        config=types.GenerateContentConfig(
            system_instruction=EXPLANATION_SYSTEM_PROMPT,
            temperature=0.2,
            response_mime_type="application/json",
            response_schema=EXPLANATION_SCHEMA,
        ),
    )
    return json.loads(response.text)


def fallback_without_gemini(finding: dict) -> dict:
    """No-key fallback (docs/06 §8): the deterministic summary becomes the card.
    The dashboard works and every number stays rule-sourced."""
    return {
        "headline": finding.get("title", "Finding"),
        "explanation": finding.get("summary", ""),
        "recommended_action": "Review evidence and confirm with the vendor.",
        "limitations": "Generated without Gemini (no API key configured).",
        "confidence_label": f"{finding.get('confidence', 0):.0%} (rule-computed)",
        "generated_without_gemini": True,
    }

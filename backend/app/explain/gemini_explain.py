"""Gemini explanation generator (docs/06 §4).

The rule decided WHAT happened, HOW MUCH is at risk, and HOW confident it is.
Gemini only narrates from the deterministic proof_trail JSON: narrator, not judge.
"""
from __future__ import annotations

import json

from .. import config

EXPLANATION_SYSTEM_PROMPT = """\
You write findings for a corporate finance team. Input is a JSON finding and its
deterministic proof_trail produced by a Python audit rule, with evidence references.
Rules:
- Explain in plain language a CFO can forward to procurement.
- Cite evidence fields and proof_trail.math values exactly as given (record IDs,
  amounts, currencies). NEVER invent or recompute amounts, dates, or IDs — you
  are the narrator, not the judge.
- Structure: headline (max 12 words), explanation (3-6 sentences referencing
  the rule and evidence), recommended_action (1-2 sentences), limitations
  (what a human must confirm).
- Tone: precise, neutral, no scare words like "fraud" — say "duplicate risk" or "billing variance".
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
    "required": ["headline", "explanation", "recommended_action", "limitations", "confidence_label"],
}

_ACTION_TEXT = {
    "HOLD_PAYMENT": "Hold disbursement immediately and verify supporting invoice, PO, and contract records before releasing funds.",
    "REQUEST_CREDIT_NOTE": "Freeze further payouts and request an immediate vendor credit note or clawback recovery for the settled overcharge.",
    "DISPUTE_VENDOR": "Place invoice on dispute hold and issue an itemized variance notice to vendor billing and procurement.",
    "CANCEL_AUTOPAY": "Cancel recurring autopay/subscription billing immediately and raise a recovery claim for post-termination charges.",
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
    """Finding dict (with proof_trail) -> CFO-ready narrative card."""
    from google.genai import types

    rule_id = finding.get("rule_id", "R?")
    payload = {
        "finding_id": finding.get("finding_id"),
        "rule_id": rule_id,
        "title": finding.get("title"),
        "severity": finding.get("severity"),
        "amount_at_risk": finding.get("amount_at_risk"),
        "currency": finding.get("currency"),
        "confidence": finding.get("confidence"),
        "recommended_action": finding.get("recommended_action"),
        "summary": finding.get("summary"),
        "proof_trail": finding.get("proof_trail") or {
            "entity_refs": finding.get("entity_refs", {}),
            "evidence": finding.get("evidence", []),
        },
    }

    response = _client().models.generate_content(
        model=config.GEMINI_PRIMARY_MODEL,
        contents=[json.dumps(payload, ensure_ascii=False)],
        config=types.GenerateContentConfig(
            system_instruction=EXPLANATION_SYSTEM_PROMPT,
            temperature=0.2,
            response_mime_type="application/json",
            response_schema=EXPLANATION_SCHEMA,
        ),
    )
    parsed = json.loads(response.text)
    parsed["model_used"] = config.GEMINI_PRIMARY_MODEL
    parsed["decision_engine"] = f"Deterministic Rule {rule_id}"
    parsed["generated_without_gemini"] = False
    return parsed


def fallback_without_gemini(finding: dict) -> dict:
    """No-key deterministic fallback grounded strictly in proof_trail."""
    rule_id = str(finding.get("rule_id") or "R?")
    proof = finding.get("proof_trail") or {}
    action_code = str(proof.get("recommended_action") or finding.get("recommended_action") or "HOLD_PAYMENT")
    action_text = _ACTION_TEXT.get(action_code, "Review evidence and confirm with the vendor.")

    evidence = proof.get("evidence") or finding.get("evidence") or []
    cited = ", ".join(
        f"{ev.get('source')}:{ev.get('record_id')} ({ev.get('field')}={ev.get('value')})"
        for ev in evidence[:4]
    )
    base_summary = finding.get("summary") or ""
    explanation_text = (
        f"{base_summary} Cited evidence: {cited}."
        if cited and base_summary
        else (base_summary or f"Rule {rule_id} flagged {finding.get('amount_at_risk', 0):,.2f} {finding.get('currency', 'INR')} at risk.")
    )

    return {
        "headline": finding.get("title", "Finding"),
        "explanation": explanation_text,
        "recommended_action": f"[{action_code}] {action_text}",
        "limitations": "Deterministic proof-trail fallback used (GEMINI_API_KEY not configured); verify vendor correspondence before clawback.",
        "confidence_label": f"{finding.get('confidence', 0):.0%} (rule-computed)",
        "model_used": config.GEMINI_PRIMARY_MODEL,
        "decision_engine": f"Deterministic Rule {rule_id}",
        "generated_without_gemini": True,
    }

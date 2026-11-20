"""Gemini explanation stage — rule output -> CFO-ready finding card (docs/06 §4)."""
from .gemini_explain import EXPLANATION_SYSTEM_PROMPT, EXPLANATION_SCHEMA, explain_finding

__all__ = ["explain_finding", "EXPLANATION_SYSTEM_PROMPT", "EXPLANATION_SCHEMA"]

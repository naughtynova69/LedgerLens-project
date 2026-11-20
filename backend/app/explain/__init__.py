"""Gemini explanation stage — rule output -> CFO-ready finding card (docs/06 §4)."""
from .gemini_explain import (
    EXPLANATION_SCHEMA,
    EXPLANATION_SYSTEM_PROMPT,
    explain_finding,
    fallback_without_gemini,
)

__all__ = [
    "explain_finding",
    "fallback_without_gemini",
    "EXPLANATION_SYSTEM_PROMPT",
    "EXPLANATION_SCHEMA",
]

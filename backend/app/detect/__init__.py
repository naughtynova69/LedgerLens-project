"""Detection engine — the explainable core of LedgerLens.

Rules are pure, deterministic functions over normalized records.
No DB access, no network, no Gemini here — that is what makes every
finding auditable and unit-testable.
"""
from .registry import DetectionContext, register, run_all

# Importing the rules package registers every rule module (side effect by design).
from . import rules  # noqa: F401

__all__ = ["DetectionContext", "register", "run_all"]

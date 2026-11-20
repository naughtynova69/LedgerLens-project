"""Core types for the detection engine (stdlib only — see docs/04 §0)."""
from __future__ import annotations

from dataclasses import dataclass, field

VALID_RECOMMENDED_ACTIONS = (
    "HOLD_PAYMENT",
    "REQUEST_CREDIT_NOTE",
    "DISPUTE_VENDOR",
    "CANCEL_AUTOPAY",
)


@dataclass
class EvidenceRef:
    """A pointer to one source field: e.g. invoices / INV-8821 / line_total = 4956.00 INR."""

    source: str          # table name, e.g. "invoices", "payments", "contracts"
    record_id: str       # stable text ID, e.g. "INV-8821", "PO-1001"
    field: str = ""      # field name, e.g. "line_total"
    value: str = ""      # stringified value, e.g. "4956.00 INR"

    def as_dict(self) -> dict:
        return {
            "source": self.source,
            "record_id": self.record_id,
            "field": self.field,
            "value": self.value,
        }


@dataclass
class Finding:
    """One audit finding, produced ONLY by a deterministic rule.

    Gemini may narrate this (explain stage) but never changes the numbers.
    """

    rule_id: str                       # "R1".."R5" (docs/04_DETECTION_RULES.md)
    title: str                         # finance-readable one-liner
    severity: str                      # critical | high | medium | low
    amount_at_risk: float              # overbilled delta, or full duplicate amount
    currency: str                      # ISO-4217
    entity_refs: dict = field(default_factory=dict)   # {"invoice_numbers": [...], ...}
    evidence: list[EvidenceRef] = field(default_factory=list)
    summary: str = ""                  # deterministic one-liner; feeds the explain stage
    confidence: float = 0.0            # 0..1, from the RULE — never from the LLM
    recommended_action: str = "HOLD_PAYMENT"
    proof_trail: dict = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.recommended_action not in VALID_RECOMMENDED_ACTIONS:
            self.recommended_action = "HOLD_PAYMENT"
        math_payload = dict(self.proof_trail.get("math", {})) if isinstance(self.proof_trail, dict) else {}
        self.proof_trail = {
            "rule_id": self.rule_id,
            "severity": self.severity,
            "amount_at_risk": self.amount_at_risk,
            "currency": self.currency,
            "confidence": self.confidence,
            "entity_refs": dict(self.entity_refs),
            "evidence": [e.as_dict() for e in self.evidence],
            "math": math_payload,
            "recommended_action": self.recommended_action,
        }

    def as_dict(self) -> dict:
        return {
            "rule_id": self.rule_id,
            "title": self.title,
            "severity": self.severity,
            "amount_at_risk": self.amount_at_risk,
            "currency": self.currency,
            "entity_refs": self.entity_refs,
            "evidence": [e.as_dict() for e in self.evidence],
            "summary": self.summary,
            "confidence": self.confidence,
            "recommended_action": self.recommended_action,
            "proof_trail": self.proof_trail,
        }

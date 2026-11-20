"""Pydantic models for the API layer (docs/05_API_SPEC.md).

Only the API boundary uses pydantic — the detection core uses plain dataclasses
(`app/detect/types.py`) so it stays dependency-free.
"""
from __future__ import annotations

from pydantic import BaseModel, Field


class DecisionIn(BaseModel):
    action: str = Field(..., description="approve | reject | request_docs | recovery")
    reviewer: str
    note: str = ""


class EvidenceOut(BaseModel):
    source: str
    record_id: str
    field: str = ""
    value: str = ""


class FindingOut(BaseModel):
    finding_id: str
    rule_id: str
    title: str
    severity: str
    amount_at_risk: float
    currency: str
    status: str
    confidence: float
    entity_refs: dict = {}
    evidence: list[EvidenceOut] = []
    summary: str = ""
    explanation: dict | None = None
    recommended_action: str = ""
    proof_trail: dict = {}

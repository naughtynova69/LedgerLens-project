"""Rule registry: rules self-register via @register("Rx") and run_all executes them all."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable

from .types import Finding


@dataclass
class DetectionContext:
    """Normalized records handed to every rule. Rows are plain dicts whose keys
    match the column dictionaries in docs/03_DATA_MODEL.md.

    ``graph_evidence`` carries pre-fetched deterministic Cypher match results
    (plain dicts from app.graph.queries) for the graph rules R6-R8. It stays a
    plain dict so this module keeps its stdlib-only contract; rules ignore it
    when empty, which preserves the exact R1-R5 behavior for every pre-existing
    suite and dataset.
    """

    invoices: list = field(default_factory=list)        # one dict per invoice LINE
    payments: list = field(default_factory=list)
    purchase_orders: list = field(default_factory=list)
    contracts: list = field(default_factory=list)
    vendors: list = field(default_factory=list)
    graph_evidence: dict = field(default_factory=dict)


DETECTORS: dict[str, Callable[[DetectionContext], list[Finding]]] = {}


def register(rule_id: str) -> Callable:
    """Class decorator registering a detector under its rule ID (R1..R5)."""

    def decorator(fn: Callable[[DetectionContext], list[Finding]]):
        DETECTORS[rule_id] = fn
        return fn

    return decorator


def run_all(ctx: DetectionContext) -> list[Finding]:
    """Run every registered rule in stable order and merge findings."""
    findings: list[Finding] = []
    for rule_id in sorted(DETECTORS):
        findings.extend(DETECTORS[rule_id](ctx))
    return findings

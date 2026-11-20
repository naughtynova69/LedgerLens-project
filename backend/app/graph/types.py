"""Graph-side data container passed to the deterministic rules R6-R8.

The Cypher layer (``queries.py``) fetches candidate matches; rules stay pure
stdlib Python and never import the graph engine themselves (neuro-symbolic
invariant: ``backend/app/detect/`` has zero graph/LLM/network dependencies).
"""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class GraphEvidence:
    """Deterministic Cypher match results for one detection run.

    Each row is a plain dict whose keys are produced by ``queries.py``; rules
    compute final amounts/dates from these numbers and attach the serialized
    ``proof_subgraph`` exactly as delivered here.
    """

    cross_entity_duplicates: list[dict] = field(default_factory=list)
    split_invoices: list[dict] = field(default_factory=list)
    collusion: list[dict] = field(default_factory=list)
    superseded_rates: list[dict] = field(default_factory=list)
    unapplied_credits: list[dict] = field(default_factory=list)

    def is_empty(self) -> bool:
        return not (
            self.cross_entity_duplicates
            or self.split_invoices
            or self.collusion
            or self.superseded_rates
            or self.unapplied_credits
        )

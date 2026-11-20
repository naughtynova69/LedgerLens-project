"""LedgerLens embedded financial knowledge graph (LadybugDB).

The graph is a deterministic, rebuildable projection & multi-hop reasoning
engine synced from the normalized relational records. SQLite/AlloyDB remains
the system of record; every graph-based finding (R6-R8) is produced by 100%
deterministic Cypher queries — the LLM is never the judge.
"""
from .client import GraphClient, get_graph_client, get_shared_graph_client
from .projector import ensure_graph_projected, project_batch_to_graph, rebuild_graph_from_db
from .queries import (
    ENTITY_PRIMARY_KEYS,
    GRAPH_STATS_QUERIES,
    R8_CROSS_ENTITY_DUPLICATE_QUERY,
    R8_CROSS_ENTITY_DUPLICATE_TAX_QUERY,
    R8_SPLIT_INVOICES_QUERY,
    R8_SPLIT_INVOICES_TAX_QUERY,
    R9_COLLUSION_SHARED_ADDRESS_QUERY,
    R9_COLLUSION_SHARED_BANK_QUERY,
    R9_COLLUSION_SHARED_PHONE_QUERY,
    R10_SUPERSEDED_RATE_QUERY,
    R10_UNAPPLIED_CREDITS_QUERY,
    fetch_entity_neighborhood,
    fetch_graph_evidence,
    fetch_graph_stats,
)
from .subgraph import build_subgraph, evidence_ids_from_refs
from .types import GraphEvidence

__all__ = [
    "GraphClient",
    "GraphEvidence",
    "get_graph_client",
    "get_shared_graph_client",
    "ensure_graph_projected",
    "project_batch_to_graph",
    "rebuild_graph_from_db",
    "R8_CROSS_ENTITY_DUPLICATE_QUERY",
    "R8_CROSS_ENTITY_DUPLICATE_TAX_QUERY",
    "R8_SPLIT_INVOICES_QUERY",
    "R8_SPLIT_INVOICES_TAX_QUERY",
    "R9_COLLUSION_SHARED_ADDRESS_QUERY",
    "R9_COLLUSION_SHARED_BANK_QUERY",
    "R9_COLLUSION_SHARED_PHONE_QUERY",
    "R10_SUPERSEDED_RATE_QUERY",
    "R10_UNAPPLIED_CREDITS_QUERY",
    "ENTITY_PRIMARY_KEYS",
    "GRAPH_STATS_QUERIES",
    "fetch_entity_neighborhood",
    "fetch_graph_evidence",
    "fetch_graph_stats",
    "build_subgraph",
    "evidence_ids_from_refs",
]

"""Frontend-ready evidence-subgraph serialization (master-prompt §5.1).

Converts Cypher match results into the JSON graph contract consumed by
``EvidenceGraphCanvas.jsx``::

    {"nodes": [{"id", "label", "type", "properties", "highlight"}],
     "edges": [{"source", "target", "type", "properties"}]}

Pure deterministic JSON shaping — no LLM involvement anywhere.
"""
from __future__ import annotations

from typing import Any

_NODE_TYPES = {
    "Vendor": "Vendor",
    "BankAccount": "BankAccount",
    "TaxIdentifier": "TaxIdentifier",
    "Address": "Address",
    "Approver": "Approver",
    "Contract": "Contract",
    "PurchaseOrder": "PurchaseOrder",
    "Invoice": "Invoice",
    "InvoiceLine": "InvoiceLine",
    "Payment": "Payment",
    "CreditNote": "CreditNote",
}


def make_node(node_id: str, node_type: str, label: str, properties: dict | None = None,
              highlight: bool = False) -> dict:
    """Build one frontend node record with deterministic field order."""
    if node_type not in _NODE_TYPES:
        raise ValueError(f"unknown node type: {node_type}")
    return {
        "id": str(node_id),
        "label": str(label),
        "type": node_type,
        "properties": _clean_properties(properties or {}),
        "highlight": bool(highlight),
    }


def make_edge(source_id: str, target_id: str, edge_type: str,
              properties: dict | None = None) -> dict:
    return {
        "source": str(source_id),
        "target": str(target_id),
        "type": str(edge_type),
        "properties": _clean_properties(properties or {}),
    }


def build_subgraph(nodes: list[dict], edges: list[dict], cypher_rule: str = "",
                   summary: str = "") -> dict:
    """Assemble the serialized evidence subgraph payload.

    Deduplicates nodes/edges by identity (id / source+target+type) so multiple
    Cypher matches can feed one subgraph without duplicates.
    """
    node_by_id: dict[str, dict] = {}
    for node in nodes:
        node_id = node["id"]
        if node_id in node_by_id:
            existing = node_by_id[node_id]
            if node.get("highlight"):
                existing["highlight"] = True
            existing["properties"].update(node.get("properties") or {})
        else:
            node_by_id[node_id] = node

    seen_edges: set[tuple[str, str, str]] = set()
    edge_list: list[dict] = []
    for edge in edges:
        key = (edge["source"], edge["target"], edge["type"])
        if key in seen_edges:
            continue
        seen_edges.add(key)
        edge_list.append(edge)

    return {
        "nodes": list(node_by_id.values()),
        "edges": edge_list,
        "cypher_rule": cypher_rule,
        "summary": summary,
    }


def evidence_ids_from_refs(entity_refs: dict) -> list[str]:
    """Collect the record IDs a finding references (subgraph highlight input)."""
    ids: list[str] = []
    for value in (entity_refs or {}).values():
        if isinstance(value, str):
            if value:
                ids.append(value)
        elif isinstance(value, (list, tuple)):
            ids.extend(str(item) for item in value if item)
    return [str(item) for item in dict.fromkeys(ids)]


def _clean_properties(properties: dict) -> dict[str, Any]:
    """Keep JSON-safe scalars only (frontend renders properties verbatim)."""
    cleaned: dict[str, Any] = {}
    for key, value in properties.items():
        if value is None or isinstance(value, (str, int, float, bool)):
            cleaned[str(key)] = value
    return cleaned

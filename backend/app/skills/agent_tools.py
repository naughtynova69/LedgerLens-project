"""Google Agent Skills & Gemini function-calling wrappers for AP audit workflows."""
from __future__ import annotations

import sqlite3
from typing import Any

from ..services import build_memo_structured, record_decision

GEMINI_TOOL_DECLARATIONS: list[dict[str, Any]] = [
    {
        "name": "fetch_payment_records",
        "description": "Retrieve settled and pending payment ledger rows filtered by vendor_id or invoice_number.",
        "parameters": {
            "type": "object",
            "properties": {
                "vendor_id": {"type": "string", "description": "Optional vendor ID (e.g. V001)"},
                "invoice_number": {"type": "string", "description": "Optional invoice number (e.g. INV-8821)"},
            },
        },
    },
    {
        "name": "generate_audit_memo",
        "description": "Generate the deterministic CFO Audit Memo (Markdown + structured KPI breakdown).",
        "parameters": {
            "type": "object",
            "properties": {
                "batch_id": {"type": "string", "description": "Optional batch ID context for the memo"},
            },
        },
    },
    {
        "name": "route_recovery_task",
        "description": "Route an open finding into recovery workflow, assign owner, and write an immutable audit_log entry.",
        "parameters": {
            "type": "object",
            "properties": {
                "finding_id": {"type": "string", "description": "Finding ID (e.g. F-0001)"},
                "assignee": {"type": "string", "description": "AP analyst or procurement owner"},
                "note": {"type": "string", "description": "Audit justification / recovery instruction"},
            },
            "required": ["finding_id", "assignee"],
        },
    },
    {
        "name": "inspect_entity_graph",
        "description": (
            "Read-only multi-hop neighborhood from the embedded LadybugDB knowledge graph "
            "around any Vendor, BankAccount, Approver, Contract, or Invoice. Strictly "
            "parameterized and whitelisted — never accepts raw Cypher."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "entity_type": {
                    "type": "string",
                    "description": "Node label: Vendor | BankAccount | Approver | Contract | Invoice",
                },
                "entity_id": {"type": "string", "description": "Primary key, e.g. V001 or INV-8821"},
                "hops": {"type": "integer", "description": "1-3 (default 2)"},
            },
            "required": ["entity_type", "entity_id"],
        },
    },
]


def fetch_payment_records(
    conn: sqlite3.Connection,
    vendor_id: str | None = None,
    invoice_number: str | None = None,
) -> dict:
    """Fetch payment records joined with invoice vendor metadata."""
    query = (
        "SELECT p.*, i.vendor_id, i.po_id, i.item, i.status AS invoice_status "
        "FROM payments p LEFT JOIN invoices i ON p.invoice_number = i.invoice_number "
        "WHERE 1=1"
    )
    params: list[Any] = []
    if vendor_id:
        query += " AND i.vendor_id = ?"
        params.append(vendor_id)
    if invoice_number:
        query += " AND p.invoice_number = ?"
        params.append(invoice_number)
    query += " ORDER BY p.payment_date DESC"

    rows = [dict(r) for r in conn.execute(query, params).fetchall()]
    return {
        "skill": "fetch_payment_records",
        "count": len(rows),
        "records": rows,
    }


def generate_audit_memo(conn: sqlite3.Connection, batch_id: str | None = None) -> dict:
    """Return structured CFO audit memo (Markdown + JSON summary)."""
    memo = build_memo_structured(conn)
    memo["skill"] = "generate_audit_memo"
    if batch_id:
        memo["batch_id"] = batch_id
    return memo


def route_recovery_task(
    conn: sqlite3.Connection,
    finding_id: str,
    assignee: str,
    note: str = "",
    actor: str = "agent_skill",
) -> dict:
    """Route a finding to recovery status with immutable decision + audit_log trail."""
    full_note = f"Routed to {assignee}" + (f": {note}" if note else "")
    res = record_decision(conn, finding_id, "recovery", reviewer=assignee or actor, note=full_note)
    return {
        "skill": "route_recovery_task",
        "finding_id": finding_id,
        "assignee": assignee,
        "status": res["status"],
        "note": full_note,
    }


def inspect_entity_graph(
    conn: sqlite3.Connection,
    entity_type: str,
    entity_id: str,
    hops: int = 2,
) -> dict:
    """Read-only k-hop neighborhood from the embedded LadybugDB graph.

    Uses only whitelisted node labels and bound parameters — arbitrary Cypher
    from untrusted input is impossible by construction.
    """
    from ..graph import ensure_graph_projected, fetch_entity_neighborhood, get_shared_graph_client

    client = get_shared_graph_client()
    ensure_graph_projected(conn, client)
    result = fetch_entity_neighborhood(client, str(entity_type), str(entity_id), hops=hops)
    if len(result["nodes"]) <= 1 and not result["edges"]:
        raise LookupError(f"entity not found in graph: {entity_type}:{entity_id}")
    return {
        "skill": "inspect_entity_graph",
        "engine": "ladybug",
        **result,
    }


def execute_skill(conn: sqlite3.Connection, tool_name: str, arguments: dict | None = None) -> dict:
    """Dispatch a Gemini function-calling skill invocation deterministically."""
    args = arguments or {}
    if tool_name == "fetch_payment_records":
        return fetch_payment_records(
            conn,
            vendor_id=args.get("vendor_id"),
            invoice_number=args.get("invoice_number"),
        )
    if tool_name == "generate_audit_memo":
        return generate_audit_memo(conn, batch_id=args.get("batch_id"))
    if tool_name == "route_recovery_task":
        finding_id = args.get("finding_id")
        assignee = args.get("assignee")
        if not finding_id or not assignee:
            raise ValueError("route_recovery_task requires 'finding_id' and 'assignee'")
        return route_recovery_task(
            conn,
            finding_id=str(finding_id),
            assignee=str(assignee),
            note=str(args.get("note") or ""),
        )
    if tool_name == "inspect_entity_graph":
        entity_type = str(args.get("entity_type") or "")
        entity_id = str(args.get("entity_id") or "")
        if not entity_type or not entity_id:
            raise ValueError("inspect_entity_graph requires 'entity_type' and 'entity_id'")
        hops_raw = args.get("hops", 2)
        try:
            hops = max(1, min(3, int(hops_raw)))
        except (TypeError, ValueError):
            hops = 2
        return inspect_entity_graph(conn, entity_type=entity_type, entity_id=entity_id, hops=hops)
    raise LookupError(f"unknown skill: {tool_name}")

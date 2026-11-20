"""Stage 2 gate: relational-to-graph projector & sample data enrichment."""

from __future__ import annotations
import pytest

from graph_support import NATIVE_GRAPH_AVAILABLE, SKIP_REASON

pytestmark = pytest.mark.skipif(
    not NATIVE_GRAPH_AVAILABLE,
    reason=SKIP_REASON,
)


from pathlib import Path

import pytest

from app.db import get_connection, init_schema
from app.graph import GraphClient
from app.graph.projector import rebuild_graph_from_db
from app.services import ingest_csv_file_to_table

SAMPLE_DATA_DIR = Path(__file__).resolve().parent.parent.parent / "sample_data"

# Deterministic counts implied by sample_data/ (11 original + 5 enriched rows).
EXPECTED_NODE_COUNTS = {
    "Vendor": 9,
    "BankAccount": 3,       # HDFC shared by V007+V008, ICIC (A-001), SBIN (V009)
    "TaxIdentifier": 9,
    "Address": 3,           # V009 and A-001 share the "12 MG Road, Bengaluru, IN" hash
    "Approver": 1,
    "Contract": 7,
    "PurchaseOrder": 8,
    "Invoice": 16,
    "InvoiceLine": 16,
    "Payment": 5,
    "CreditNote": 1,
}

EXPECTED_RELATIONSHIP_COUNTS = {
    "USES_BANK": 3,          # V007+V008 -> shared HDFC, V009 -> SBIN
    "HAS_TAX_ID": 9,
    "LOCATED_AT": 3,
    "APPROVER_USES_BANK": 1,
    "APPROVER_LOCATED_AT": 1,
    "AMENDS": 1,             # C-007 amends C-006
    "ISSUED_BY": 16,
    "HAS_LINE": 16,
    "BILLED_UNDER_PO": 10,
    "GOVERNED_BY": 10,       # invoice -> same (vendor, item, date-window) contracts
    "SETTLED_BY": 5,
    "PAID_TO_ACCOUNT": 0,
    "ISSUED_CREDIT": 1,
    "APPLIED_TO_INVOICE": 0,  # CN-9001 is still OPEN
    "APPROVED_INVOICE": 1,    # A-001 -> INV-9801
}


@pytest.fixture()
def seeded_conn():
    conn = get_connection(":memory:")
    init_schema(conn)
    for table in ["vendors", "approvers", "contracts", "purchase_orders",
                  "invoices", "payments", "credit_notes"]:
        csv_path = SAMPLE_DATA_DIR / f"{table}.csv"
        if csv_path.exists():
            ingest_csv_file_to_table(conn, csv_path, table)
    yield conn
    conn.close()


@pytest.fixture()
def graph_client():
    client = GraphClient(":memory:")
    yield client
    client.close()


def _stats(client: GraphClient) -> tuple[dict, dict]:
    from app.graph.queries import fetch_graph_stats

    result = fetch_graph_stats(client)
    return result["nodes"], result["relationships"]


def test_projection_creates_exact_node_and_edge_counts(seeded_conn, graph_client):
    rebuild_graph_from_db(seeded_conn, graph_client)
    nodes, relationships = _stats(graph_client)

    for label, expected in EXPECTED_NODE_COUNTS.items():
        assert nodes.get(label) == expected, (
            f"node {label}: expected {expected}, got {nodes.get(label)}"
        )
    for rel_type, expected in EXPECTED_RELATIONSHIP_COUNTS.items():
        assert relationships.get(rel_type) == expected, (
            f"rel {rel_type}: expected {expected}, got {relationships.get(rel_type)}"
        )


def test_double_projection_is_idempotent(seeded_conn, graph_client):
    rebuild_graph_from_db(seeded_conn, graph_client)
    nodes_first, rels_first = _stats(graph_client)
    rebuild_graph_from_db(seeded_conn, graph_client)
    nodes_second, rels_second = _stats(graph_client)

    assert nodes_first == nodes_second
    assert rels_first == rels_second
    assert sum(nodes_second.values()) == sum(EXPECTED_NODE_COUNTS.values())
    assert sum(rels_second.values()) == sum(EXPECTED_RELATIONSHIP_COUNTS.values())


def test_shared_bank_account_is_one_graph_node(seeded_conn, graph_client):
    """R6 structural fact: sister vendors converge on the same BankAccount node."""
    rebuild_graph_from_db(seeded_conn, graph_client)
    rows = graph_client.execute_read(
        "MATCH (v:Vendor)-[:USES_BANK]->(b:BankAccount) "
        "WHERE b.account_key = $account_key "
        "RETURN v.vendor_id AS vendor_id ORDER BY vendor_id",
        {"account_key": "HDFC50100234567841"},
    )
    assert [row["vendor_id"] for row in rows] == ["V007", "V008"]


def test_shared_address_is_one_graph_node(seeded_conn, graph_client):
    """R7 structural fact: approver A-001 and vendor V009 share one Address node."""
    rebuild_graph_from_db(seeded_conn, graph_client)
    rows = graph_client.execute_read(
        "MATCH (a:Approver)-[:APPROVER_LOCATED_AT]->(addr:Address) "
        "<-[:LOCATED_AT]-(v:Vendor) "
        "RETURN a.approver_id AS approver_id, v.vendor_id AS vendor_id"
    )
    assert [(row["approver_id"], row["vendor_id"]) for row in rows] == [("A-001", "V009")]


def test_amendment_lineage_is_traversable(seeded_conn, graph_client):
    """R8 structural fact: C-007 --AMENDS--> C-006 with a lowered unit rate."""
    rebuild_graph_from_db(seeded_conn, graph_client)
    rows = graph_client.execute_read(
        "MATCH (c_new:Contract)-[am:AMENDS]->(c_old:Contract) "
        "RETURN c_new.contract_id AS new_id, c_old.contract_id AS old_id, "
        "c_new.unit_rate AS new_rate, c_old.unit_rate AS old_rate, am.rate_delta AS rate_delta"
    )
    assert len(rows) == 1
    assert rows[0]["new_id"] == "C-007"
    assert rows[0]["old_id"] == "C-006"
    assert rows[0]["new_rate"] < rows[0]["old_rate"]
    assert rows[0]["rate_delta"] == pytest.approx(-500.0)


def test_project_batch_returns_counts_and_duration(seeded_conn):
    from app.graph import project_batch_to_graph

    client = GraphClient(":memory:")
    result = project_batch_to_graph(seeded_conn, client, batch_id=None)
    client.close()
    assert result["rebuilt"] is True
    assert result["total_nodes"] == sum(EXPECTED_NODE_COUNTS.values())
    assert result["total_relationships"] == sum(EXPECTED_RELATIONSHIP_COUNTS.values())
    assert result["duration_ms"] >= 0
    assert result["engine"]["ok"] is True

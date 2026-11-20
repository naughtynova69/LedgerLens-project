"""Stage 1 gate: LadybugDB client, typed schema DDL, and subgraph serializer."""
from __future__ import annotations

import threading

import pytest

from app.graph import GraphClient
from app.graph.schema import ALL_DDL, initialize_schema
from app.graph.subgraph import build_subgraph, evidence_ids_from_refs, make_edge, make_node


@pytest.fixture()
def client() -> GraphClient:
    graph = GraphClient(":memory:")
    yield graph
    graph.close()


def test_ddl_creation_is_idempotent(client: GraphClient):
    initialize_schema(client)
    initialize_schema(client)  # second run must not raise or duplicate tables

    stats = client.execute_read(
        "MATCH (n:Vendor) RETURN count(n) AS n;"
    )
    assert stats[0]["n"] == 0
    rel_count = client.execute_read(
        "MATCH ()-[r:ISSUED_BY]->() RETURN count(r) AS n;"
    )
    assert rel_count[0]["n"] == 0


def test_ddl_statements_are_complete_and_static():
    joined = "\n".join(ALL_DDL)
    for table in ("Vendor", "BankAccount", "TaxIdentifier", "Address", "Approver",
                  "Contract", "PurchaseOrder", "Invoice", "InvoiceLine", "Payment",
                  "CreditNote"):
        assert f"CREATE NODE TABLE IF NOT EXISTS {table}(" in joined
    for rel in ("USES_BANK", "HAS_TAX_ID", "LOCATED_AT", "ISSUED_BY", "HAS_LINE",
                "BILLED_UNDER_PO", "GOVERNED_BY", "AMENDS", "SETTLED_BY",
                "PAID_TO_ACCOUNT", "ISSUED_CREDIT", "APPLIED_TO_INVOICE",
                "APPROVED_INVOICE", "APPROVER_USES_BANK", "APPROVER_LOCATED_AT"):
        assert f"CREATE REL TABLE IF NOT EXISTS {rel}(" in joined
    for ddl in ALL_DDL:
        assert "IF NOT EXISTS" in ddl


def test_parameterized_write_and_read(client: GraphClient):
    initialize_schema(client)
    client.execute_write(
        "CREATE (:Vendor {vendor_id: $vendor_id, name: $name, normalized_name: $normalized_name, "
        "email_domain: $email_domain, phone_normalized: $phone_normalized, status: $status})",
        {"vendor_id": "V001", "name": "Sunbeam Electricals Pvt Ltd",
         "normalized_name": "SUNBEAM ELECTRICALS", "email_domain": "",
         "phone_normalized": "9845012345", "status": "active"},
    )
    rows = client.execute_read(
        "MATCH (v:Vendor) WHERE v.vendor_id = $vendor_id "
        "RETURN v.vendor_id AS vendor_id, v.name AS name, v.phone_normalized AS phone",
        {"vendor_id": "V001"},
    )
    assert len(rows) == 1
    assert rows[0]["vendor_id"] == "V001"
    assert rows[0]["phone"] == "9845012345"


def test_memory_databases_are_isolated():
    initialize_schema(GraphClient(":memory:"))
    first = GraphClient(":memory:")
    second = GraphClient(":memory:")
    initialize_schema(first)
    initialize_schema(second)
    first.execute_write(
        "CREATE (:Vendor {vendor_id: $v, name: $n, normalized_name: $n2, "
        "email_domain: $e, phone_normalized: $p, status: $s})",
        {"v": "V100", "n": "Isolated Vendor", "n2": "ISOLATED VENDOR", "e": "", "p": "", "s": "active"},
    )
    assert first.execute_read("MATCH (v:Vendor) RETURN count(v) AS n")[0]["n"] == 1
    assert second.execute_read("MATCH (v:Vendor) RETURN count(v) AS n")[0]["n"] == 0
    first.close()
    second.close()


def test_concurrent_reads_are_safe_during_locked_writes(client: GraphClient):
    initialize_schema(client)
    errors: list[Exception] = []

    def writer() -> None:
        try:
            for i in range(20):
                client.execute_write(
                    "CREATE (:Vendor {vendor_id: $v, name: $n, normalized_name: $n2, "
                    "email_domain: $e, phone_normalized: $p, status: $s})",
                    {"v": f"VW-{i:03d}", "n": f"Writer {i}", "n2": f"WRITER {i}",
                     "e": "", "p": "", "s": "active"},
                )
        except Exception as exc:  # pragma: no cover - surfaced by assertion below
            errors.append(exc)

    def reader() -> None:
        try:
            for _ in range(40):
                rows = client.execute_read("MATCH (v:Vendor) RETURN count(v) AS n")
                assert rows[0]["n"] >= 0
        except Exception as exc:  # pragma: no cover - surfaced by assertion below
            errors.append(exc)

    threads = [threading.Thread(target=writer)] + [
        threading.Thread(target=reader) for _ in range(6)
    ]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=30)

    assert errors == []
    assert client.execute_read("MATCH (v:Vendor) RETURN count(v) AS n")[0]["n"] == 20


def test_health_check_reports_engine_status(client: GraphClient):
    health = client.health_check()
    assert health["ok"] is True
    assert health["engine"] == "ladybug"
    assert health["mode"] == "memory"


def test_subgraph_serializer_shape():
    nodes = [
        make_node("Invoice:INV-1", "Invoice", "INV-1", {"grand_total": 100.0}, highlight=True),
        make_node("Vendor:V001", "Vendor", "Sunbeam", {"vendor_id": "V001"}),
        make_node("Vendor:V001", "Vendor", "Sunbeam", {"extra": 1}),  # duplicate id merges
        make_node("BankAccount:B-1", "BankAccount", "••••8841", {}, highlight=True),
    ]
    edges = [
        make_edge("Invoice:INV-1", "Vendor:V001", "ISSUED_BY"),
        make_edge("Invoice:INV-1", "Vendor:V001", "ISSUED_BY"),  # duplicate edge dedupes
        make_edge("Vendor:V001", "BankAccount:B-1", "USES_BANK"),
    ]
    subgraph = build_subgraph(nodes, edges, cypher_rule="TEST", summary="shape test")
    assert subgraph["cypher_rule"] == "TEST"
    assert len(subgraph["nodes"]) == 3
    assert len(subgraph["edges"]) == 2
    vendor = next(n for n in subgraph["nodes"] if n["id"] == "Vendor:V001")
    assert vendor["properties"]["extra"] == 1
    assert all(set(node) == {"id", "label", "type", "properties", "highlight"} for node in subgraph["nodes"])
    assert all(set(edge) == {"source", "target", "type", "properties"} for edge in subgraph["edges"])


def test_evidence_ids_from_refs_collects_highlight_targets():
    refs = {
        "invoice_numbers": ["INV-1", "INV-2"],
        "vendor_id": "V001",
        "po_id": "",
        "payment_ids": ["PAY-1"],
    }
    assert evidence_ids_from_refs(refs) == ["INV-1", "INV-2", "V001", "PAY-1"]


def test_unknown_node_type_is_rejected():
    with pytest.raises(ValueError):
        make_node("X:1", "NotAType", "x")

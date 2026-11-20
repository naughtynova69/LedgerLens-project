"""Stage 3 gate: deterministic graph rules R8-R10 fire on the planted anomalies
with exact amounts, non-empty proof subgraphs, and zero false positives on the
clean controls — and stay silent when the graph layer is disabled."""

from __future__ import annotations
import pytest

from graph_support import NATIVE_GRAPH_AVAILABLE, SKIP_REASON

pytestmark = pytest.mark.skipif(
    not NATIVE_GRAPH_AVAILABLE,
    reason=SKIP_REASON,
)


import json
from pathlib import Path

import pytest

from app.db import get_connection, init_schema
from app.detect.registry import DetectionContext, run_all
from app.graph import GraphClient
from app.graph.projector import rebuild_graph_from_db
from app.services import ingest_csv_file_to_table, run_detection

SAMPLE_DATA_DIR = Path(__file__).resolve().parent.parent.parent / "sample_data"

CONTROL_INVOICES = {"INV-9001", "INV-9010", "INV-9400", "INV-9500"}


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


def _findings_by_rule(conn) -> dict[str, list[dict]]:
    rows = conn.execute("SELECT * FROM findings").fetchall()
    by_rule: dict[str, list[dict]] = {}
    for row in rows:
        finding = dict(row)
        finding["entity_refs"] = json.loads(finding["entity_refs"] or "{}")
        finding["proof_trail"] = json.loads(finding["proof_trail"] or "{}")
        by_rule.setdefault(finding["rule_id"], []).append(finding)
    return by_rule


def test_graph_rules_fire_on_planted_anomalies_with_exact_amounts(seeded_conn, graph_client):
    result = run_detection(seeded_conn, graph_client=graph_client)
    assert result["findings_created"] == 10  # 7 tabular-eligible (R1-R5 fire) + 4 graph (R8, R9, R10 x2)

    by_rule = _findings_by_rule(seeded_conn)

    # Tabular acceptance invariant is untouched by the graph layer.
    assert len(by_rule["R1"]) == 1
    assert len(by_rule["R2"]) == 1
    assert len(by_rule["R3"]) == 1
    assert len(by_rule["R4"]) == 2
    assert len(by_rule["R5"]) == 1

    # R8 — cross-entity duplicate via shared bank account.
    r8 = by_rule["R8"]
    r8_dups = [f for f in r8 if f["entity_refs"].get("shared_via") == "bank"
               and "approval_limit" not in f["entity_refs"]]
    assert len(r8_dups) == 1
    dup = r8_dups[0]
    assert dup["amount_at_risk"] == pytest.approx(12000.00)
    assert dup["entity_refs"]["vendor_ids"] == ["V007", "V008"]
    assert sorted(dup["entity_refs"]["invoice_numbers"]) == ["INV-9701", "INV-9702"]
    assert dup["entity_refs"]["shared_ref"] == "HDFC50100234567841"
    assert dup["proof_trail"]["proof_subgraph"]["cypher_rule"] == "R8_CROSS_ENTITY_DUPLICATE"
    assert dup["proof_trail"]["proof_subgraph"]["nodes"], "proof subgraph must not be empty"
    assert dup["confidence"] == 0.92

    # R9 — approver-vendor collusion via shared registered address.
    assert len(by_rule["R9"]) == 1
    collusion = by_rule["R9"][0]
    assert collusion["amount_at_risk"] == pytest.approx(8500.00)
    assert collusion["severity"] == "critical"
    assert collusion["entity_refs"]["approver_id"] == "A-001"
    assert collusion["entity_refs"]["vendor_id"] == "V009"
    assert collusion["entity_refs"]["shared_via"] == "address"
    assert collusion["recommended_action"] == "HOLD_PAYMENT_AND_ESCALATE_INTERNAL_AUDIT"
    assert collusion["proof_trail"]["proof_subgraph"]["nodes"], "proof subgraph must not be empty"

    # R10 — superseded amendment rate + open unapplied credit note.
    assert len(by_rule["R10"]) == 2
    r10_amounts = sorted(f["amount_at_risk"] for f in by_rule["R10"])
    assert r10_amounts == pytest.approx([944.00, 1000.00])

    lineage = next(f for f in by_rule["R10"]
                   if f["entity_refs"].get("superseded_contract_id") == "C-006")
    assert lineage["amount_at_risk"] == pytest.approx(1000.00)  # (5000-4500) * 2
    assert lineage["entity_refs"]["invoice_numbers"] == ["INV-9601"]
    assert lineage["entity_refs"]["contract_id"] == "C-007"
    assert lineage["proof_trail"]["math"]["superseded_rate"] == 5000.0
    assert lineage["proof_trail"]["math"]["amended_rate"] == 4500.0
    assert lineage["proof_trail"]["proof_subgraph"]["cypher_rule"] == "R10_SUPERSEDED_RATE"

    credit = next(f for f in by_rule["R10"] if f["entity_refs"].get("credit_note_id"))
    assert credit["amount_at_risk"] == pytest.approx(944.00)
    assert credit["entity_refs"]["credit_note_id"] == "CN-9001"
    assert credit["entity_refs"]["vendor_id"] == "V006"
    assert credit["recommended_action"] == "APPLY_CREDIT_NOTE"
    assert credit["proof_trail"]["proof_subgraph"]["cypher_rule"] == "R10_UNAPPLIED_CREDITS"


def test_zero_false_positives_on_clean_controls(seeded_conn, graph_client):
    run_detection(seeded_conn, graph_client=graph_client)
    by_rule = _findings_by_rule(seeded_conn)

    graph_rules = ["R8", "R9", "R10"]
    for rule_id in graph_rules:
        for finding in by_rule.get(rule_id, []):
            referenced = json.dumps(finding["entity_refs"])
            for control in CONTROL_INVOICES:
                assert control not in referenced, (
                    f"clean control {control} flagged by {rule_id}"
                )


def test_graph_rules_stay_silent_without_graph_evidence(seeded_conn):
    """Pure-stdlib behavior: no graph evidence -> R8-R10 emit nothing (pre-existing
    suites and datasets are untouched)."""
    invoices = [dict(r) for r in seeded_conn.execute("SELECT * FROM invoices").fetchall()]
    payments = [dict(r) for r in seeded_conn.execute("SELECT * FROM payments").fetchall()]
    pos = [dict(r) for r in seeded_conn.execute("SELECT * FROM purchase_orders").fetchall()]
    contracts = [dict(r) for r in seeded_conn.execute("SELECT * FROM contracts").fetchall()]
    vendors = [dict(r) for r in seeded_conn.execute("SELECT * FROM vendors").fetchall()]

    findings = run_all(DetectionContext(
        invoices=invoices, payments=payments, purchase_orders=pos,
        contracts=contracts, vendors=vendors, graph_evidence={},
    ))
    assert all(f.rule_id in {"R1", "R2", "R3", "R4", "R5"} for f in findings)
    assert len(findings) == 6


def test_detection_output_is_deterministic(seeded_conn):
    """Same input twice -> identical finding output (rule-computed confidences)."""
    client_a = GraphClient(":memory:")
    client_b = GraphClient(":memory:")
    try:
        run_detection(seeded_conn, graph_client=client_a)
        first = _findings_by_rule(seeded_conn)
        seeded_conn.execute("DELETE FROM findings")
        seeded_conn.commit()
        run_detection(seeded_conn, graph_client=client_b)
        second = _findings_by_rule(seeded_conn)
    finally:
        client_a.close()
        client_b.close()

    def signatures(by_rule: dict[str, list[dict]]) -> list[tuple]:
        out = []
        for rule_id, rows in by_rule.items():
            for row in rows:
                out.append((
                    rule_id, row["title"], row["amount_at_risk"], row["confidence"],
                    json.dumps(row["entity_refs"], sort_keys=True),
                ))
        return sorted(out)

    assert signatures(first) == signatures(second)


def test_explanation_cites_graph_evidence(seeded_conn, graph_client):
    run_detection(seeded_conn, graph_client=graph_client)
    rows = seeded_conn.execute(
        "SELECT rule_id, explanation FROM findings WHERE rule_id IN ('R8','R9','R10')"
    ).fetchall()
    assert rows, "graph findings must exist"
    cited = 0
    for row in rows:
        explanation = json.loads(row["explanation"] or "{}")
        assert explanation.get("generated_without_gemini") is True
        if "Multi-hop graph evidence" in str(explanation.get("explanation", "")):
            cited += 1
    assert cited == len(rows), "every graph finding narrative must cite its subgraph"

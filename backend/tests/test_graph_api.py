"""Stage 4 gate: graph API endpoints & the read-only inspect_entity_graph skill."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app import config
from app.main import app


@pytest.fixture(autouse=True)
def isolated_env(monkeypatch: pytest.MonkeyPatch, tmp_path):
    """Isolated relational DB + empty shared graph per test."""
    import app.graph.client as graph_client_module

    monkeypatch.setattr(config, "DB_PATH", str(tmp_path / "graph_api.db"))
    monkeypatch.setattr(config, "UPLOAD_DIR", str(tmp_path / "uploads"))
    previous = graph_client_module._SHARED_CLIENT
    graph_client_module._SHARED_CLIENT = None
    yield
    if previous is not None:
        graph_client_module._SHARED_CLIENT = previous


@pytest.fixture()
def seeded_client():
    with TestClient(app) as client:
        seed = client.post("/api/seed/sample_data")
        assert seed.status_code == 200
        yield client


def test_graph_rebuild_returns_counts_and_duration(seeded_client):
    resp = seeded_client.post("/api/graph/rebuild")
    assert resp.status_code == 200
    data = resp.json()
    assert data["rebuilt"] is True
    assert data["total_nodes"] == 78
    assert data["total_relationships"] == 77
    assert data["duration_ms"] >= 0
    assert data["engine"]["ok"] is True


def test_graph_stats_reports_counts_by_label(seeded_client):
    resp = seeded_client.get("/api/graph/stats")
    assert resp.status_code == 200
    data = resp.json()
    assert data["nodes"]["Vendor"] == 9
    assert data["nodes"]["BankAccount"] == 3
    assert data["nodes"]["Invoice"] == 16
    assert data["relationships"]["USES_BANK"] == 3
    assert data["relationships"]["AMENDS"] == 1
    assert data["engine"]["engine"] == "ladybug"


def test_stored_subgraph_for_graph_rule_finding(seeded_client, monkeypatch: pytest.MonkeyPatch):
    """Seed with the graph enabled (monkeypatched like production .env) -> R6-R8
    findings are stored with proof subgraphs; the endpoint serves them back."""
    monkeypatch.setattr(config, "GRAPH_ENABLED", True)
    reseed = seeded_client.post("/api/seed/sample_data")
    assert reseed.status_code == 200
    assert reseed.json()["findings_created"] == 10  # 6 tabular + 4 graph findings

    r6_findings = seeded_client.get("/api/findings?rule_id=R6").json()
    assert r6_findings, "R6 finding must exist after graph-enabled detection"
    finding_id = r6_findings[0]["finding_id"]

    resp = seeded_client.get(f"/api/graph/findings/{finding_id}/subgraph")
    assert resp.status_code == 200
    data = resp.json()
    assert data["source"] == "stored"
    assert data["cypher_rule"] == "R6_CROSS_ENTITY_DUPLICATE"
    assert data["nodes"], "stored subgraph must contain nodes"
    node_types = {node["type"] for node in data["nodes"]}
    assert {"Invoice", "Vendor", "BankAccount"} <= node_types


def test_derived_subgraph_for_tabular_finding(seeded_client):
    """R1-R5 findings have no stored subgraph; the endpoint derives one."""
    findings = seeded_client.get("/api/findings").json()
    r1 = next(f for f in findings if f["rule_id"] == "R1")
    resp = seeded_client.get(f"/api/graph/findings/{r1['finding_id']}/subgraph")
    assert resp.status_code == 200
    data = resp.json()
    assert data["source"] == "derived"
    assert data["nodes"], "derived subgraph must contain nodes"
    node_types = {node["type"] for node in data["nodes"]}
    assert "Invoice" in node_types
    assert "Vendor" in node_types


def test_entity_neighborhood_endpoint(seeded_client):
    resp = seeded_client.get("/api/graph/entity/Vendor/V007?hops=2")
    assert resp.status_code == 200
    data = resp.json()
    assert data["entity_type"] == "Vendor"
    assert data["hops"] == 2
    node_types = {node["type"] for node in data["nodes"]}
    assert "Vendor" in node_types
    assert "BankAccount" in node_types
    assert "Invoice" in node_types

    missing = seeded_client.get("/api/graph/entity/Vendor/NOPE-999")
    assert missing.status_code == 404

    bad_type = seeded_client.get("/api/graph/entity/NotAType/V001")
    assert bad_type.status_code == 400

    clamped = seeded_client.get("/api/graph/entity/Vendor/V007?hops=99")
    assert clamped.status_code == 200
    assert clamped.json()["hops"] == 3


def test_inspect_entity_graph_skill(seeded_client):
    resp = seeded_client.post(
        "/api/skills/inspect_entity_graph",
        json={"entity_type": "Vendor", "entity_id": "V009", "hops": 2},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["skill"] == "inspect_entity_graph"
    assert data["engine"] == "ladybug"
    node_types = {node["type"] for node in data["nodes"]}
    assert {"Vendor", "Approver"} <= node_types  # A-001 shares the address

    missing = seeded_client.post(
        "/api/skills/inspect_entity_graph",
        json={"entity_type": "Vendor", "entity_id": "V999"},
    )
    assert missing.status_code == 404

    skills = seeded_client.get("/api/skills").json()
    tool_names = {tool["name"] for tool in skills["tools"]}
    assert "inspect_entity_graph" in tool_names


def test_graph_endpoints_preserve_existing_api(seeded_client):
    """The pre-existing endpoints still respond after the graph layer landed."""
    assert seeded_client.get("/health").json()["status"] == "ok"
    assert seeded_client.get("/api/stats").json()["total_findings"] == 6
    assert seeded_client.get("/api/memo").status_code == 200
    assert seeded_client.get("/api/audit-log").status_code == 200
    assert len(seeded_client.get("/api/findings").json()) == 6

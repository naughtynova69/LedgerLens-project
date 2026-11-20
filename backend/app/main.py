"""LedgerLens API — routes follow docs/05_API_SPEC.md.

Endpoints:
  [done] GET  /health
  [done] GET  /api/stats                    — KPI analytics for the dashboard
  [done] GET  /api/batches                  — list all ingested document batches
  [done] POST /api/ingest/upload            — stores file, validates CSV, ingests rows into DB
  [done] POST /api/seed/sample_data         — 1-click load demo dataset & run detection
  [done] POST /api/run/{batch_id}/extract   — Gemini/CSV extraction + math verification
  [done] POST /api/run/{batch_id}/detect    — normalize + R1..R5 over the DB
  [done] GET  /api/findings                 — exception queue with filters
  [done] GET  /api/findings/{id}            — finding + joined evidence source records
  [done] POST /api/findings/{id}/decision   — approve/reject/request_docs/recovery
  [done] GET  /api/memo                     — deterministic audit memo (Markdown + JSON)
  [done] GET  /api/audit-log                — immutable decision history
  [done] GET  /api/skills                   — Google Agent Skills declarations
  [done] POST /api/skills/{tool_name}       — execute Agent Skill function call
"""
from __future__ import annotations

import json
import os
from contextlib import asynccontextmanager
from pathlib import Path
import sqlite3
from typing import Annotated, Any

from fastapi import Body, FastAPI, File, Form, Header, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from . import config
from .audit_chain import ensure_audit_chain_table, verify_audit_chain
from .copilot import ask_copilot
from .db import get_connection, init_schema
from .finance.dispute_packets import generate_dispute_packet
from .finance.exports import export_findings_csv
from .finance.policy import apply_bulk_decision, get_policy, update_policy
from .gcp.alloydb import check_alloydb_connection
from .gcp.bigquery import compute_executive_analytics, sync_to_bigquery
from .gcp.config_gcp import get_gcp_readiness_status
from .gcp.storage import store_evidence_object
from .graph import (
    ENTITY_PRIMARY_KEYS,
    fetch_entity_neighborhood,
    fetch_graph_stats,
    get_shared_graph_client,
    project_batch_to_graph,
)
from .graph.client import GraphClient
from .graph.subgraph import build_subgraph
from .ingest.router import VALID_KINDS, save_stream_to_upload, validate_csv
from .models import DecisionIn
from .normalize.fx_service import get_fx_rates
from .services import (
    build_memo_structured,
    get_finding_with_sources,
    get_stats,
    ingest_csv_file_to_table,
    make_workspace_view_conn,
    record_decision,
    run_detection,
    run_extraction_for_batch,
    seed_sample_dataset,
)
from .skills import GEMINI_TOOL_DECLARATIONS, execute_skill
from .workspaces import _DEFAULT_ROLE_POLICY, create_workspace, list_workspaces, require_role

_ROLE_POLICY_MAP: dict[str, list[str]] = json.loads(_DEFAULT_ROLE_POLICY)


def _resolve_workspace_id(
    workspace_id: str | None = None,
    x_workspace_id: str | None = None,
) -> str:
    ws = (workspace_id or x_workspace_id or "default").strip()
    return ws or "default"


def _enforce_rbac(x_user_role: str | None, permission: str) -> None:
    """Enforce RBAC via workspaces.require_role when X-User-Role header is provided."""
    if x_user_role is None:
        return
    allowed_roles = [
        role for role, perms in _ROLE_POLICY_MAP.items() if permission in perms
    ]
    try:
        require_role(x_user_role, allowed_roles)
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc


class BulkDecisionIn(BaseModel):
    finding_ids: list[str]
    action: str
    reviewer: str
    note: str = ""


class PolicyUpdateIn(BaseModel):
    r1_max_amount_drift_pct: float | None = None
    r1_max_date_gap_days: int | None = None
    r4_max_fx_drift_pct: float | None = None
    auto_hold_threshold_inr: float | None = None


class BatchRecordsUpdateIn(BaseModel):
    records: list[dict[str, Any]]


class WorkspaceCreateIn(BaseModel):
    name: str
    client_code: str = ""


class CopilotAskIn(BaseModel):
    question: str
    workspace_id: str = "default"


def _get_ready_conn() -> sqlite3.Connection:
    """Open configured SQLite connection with schema guaranteed up to date.

    ``init_schema`` is fully idempotent (CREATE IF NOT EXISTS + guarded ALTERs),
    so it runs on every connection — this upgrades databases created before the
    knowledge-graph columns and tables existed.
    """
    conn = get_connection()
    init_schema(conn)
    return conn


def _ensure_graph_projected() -> GraphClient:
    """Shared graph client with a guaranteed non-empty projection.

    Rebuilds deterministically from the relational system of record when the
    process just started (Cloud Run cold start) or the graph is empty.
    """
    from .graph import ensure_graph_projected as _ensure_projected

    client = get_shared_graph_client()
    conn = _get_ready_conn()
    try:
        _ensure_projected(conn, client)
    finally:
        conn.close()
    return client


def _derive_finding_subgraph(client, entity_refs: dict) -> dict:
    """Build a context subgraph for tabular findings (R1-R5) from entity_refs."""
    nodes: list[dict] = []
    edges: list[dict] = []

    def collect(entity_type: str, entity_id: str, hops: int) -> None:
        if entity_type not in ENTITY_PRIMARY_KEYS or not entity_id:
            return
        try:
            neighborhood = fetch_entity_neighborhood(client, entity_type, entity_id, hops=hops)
        except Exception:
            return
        nodes.extend(neighborhood["nodes"])
        edges.extend(neighborhood["edges"])

    for invoice_number in (entity_refs.get("invoice_numbers") or []):
        collect("Invoice", str(invoice_number), hops=2)
    for key in ("vendor_id", "vendor_ids"):
        values = entity_refs.get(key) or []
        if isinstance(values, str):
            values = [values]
        for vendor_id in values:
            collect("Vendor", str(vendor_id), hops=1)
    contract_id = entity_refs.get("contract_id") or entity_refs.get("superseded_contract_id")
    if contract_id:
        collect("Contract", str(contract_id), hops=1)
    for credit_note_id in (entity_refs.get("credit_note_ids") or []):
        collect("CreditNote", str(credit_note_id), hops=1)

    return build_subgraph(
        nodes, edges,
        cypher_rule="FINDING_CONTEXT",
        summary="Deterministic neighborhood of the referenced records.",
    )


@asynccontextmanager
async def lifespan(_: FastAPI):
    conn = _get_ready_conn()
    try:
        auto_seed = os.getenv("AUTO_SEED_DEMO", "true").strip().lower() in ("1", "true", "yes")
        if auto_seed:
            batch_count = conn.execute("SELECT COUNT(*) FROM batches").fetchone()[0]
            if batch_count == 0:
                try:
                    seed_sample_dataset(conn)
                except Exception:
                    pass
    finally:
        conn.close()
    yield


app = FastAPI(
    title="LedgerLens API",
    version=config.APP_VERSION,
    description="Explainable AI money-leak auditor. Gemini extracts and explains; "
                "the rules engine decides; the workflow logs.",
    lifespan=lifespan,
)

app.add_middleware(GZipMiddleware, minimum_size=500)

# Enable CORS for local development and preview environments
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.post("/api/graph/rebuild")
def graph_rebuild(batch_id: str | None = None) -> dict:
    """Rebuild/sync the LadybugDB projection from the relational DB."""
    conn = _get_ready_conn()
    try:
        result = project_batch_to_graph(conn, get_shared_graph_client(), batch_id=batch_id)
        conn.execute(
            """INSERT INTO audit_log (actor, action, object_type, object_id, detail)
               VALUES ('graph_api', 'rebuild', 'graph', 'ledgerlens', ?)""",
            (f"Rebuilt graph projection: {result['total_nodes']} nodes, "
             f"{result['total_relationships']} relationships in {result['duration_ms']} ms",),
        )
        conn.commit()
        return result
    finally:
        conn.close()


@app.get("/api/graph/stats")
def graph_stats() -> dict:
    """Node/relationship counts plus graph engine status."""
    client = _ensure_graph_projected()
    stats = fetch_graph_stats(client)
    conn = _get_ready_conn()
    try:
        row = conn.execute(
            "SELECT COUNT(*) AS n FROM findings WHERE rule_id IN ('R8', 'R9', 'R10')"
        ).fetchone()
        stats["multi_hop_risks"] = int(row["n"]) if row else 0
    finally:
        conn.close()
    return stats


@app.get("/api/graph/findings/{finding_id}/subgraph")
def finding_subgraph(finding_id: str) -> dict:
    """Evidence subgraph for any finding (stored R8-R10 subgraphs, or a derived
    deterministic neighborhood for tabular R1-R5 findings)."""
    conn = _get_ready_conn()
    try:
        row = conn.execute(
            "SELECT finding_id, rule_id, entity_refs, proof_trail FROM findings "
            "WHERE finding_id = ?",
            (finding_id,),
        ).fetchone()
        if row is None:
            raise HTTPException(status_code=404, detail=f"finding not found: {finding_id}")

        entity_refs = json.loads(row["entity_refs"] or "{}")
        proof_trail = json.loads(row["proof_trail"] or "{}")
        stored = (proof_trail or {}).get("proof_subgraph") or {}

        if stored.get("nodes"):
            return {
                "finding_id": row["finding_id"],
                "rule_id": row["rule_id"],
                "source": "stored",
                "nodes": stored.get("nodes", []),
                "edges": stored.get("edges", []),
                "cypher_rule": stored.get("cypher_rule", ""),
                "summary": stored.get("summary", ""),
            }

        client = _ensure_graph_projected()
        derived = _derive_finding_subgraph(client, entity_refs)
        return {
            "finding_id": row["finding_id"],
            "rule_id": row["rule_id"],
            "source": "derived",
            "nodes": derived["nodes"],
            "edges": derived["edges"],
            "cypher_rule": derived["cypher_rule"],
            "summary": derived["summary"],
        }
    finally:
        conn.close()


@app.get("/api/graph/entity/{entity_type}/{entity_id}")
def entity_neighborhood(entity_type: str, entity_id: str, hops: int = 2) -> dict:
    """k-hop neighborhood (hops clamped to 1..3) around a whitelisted node type."""
    if entity_type not in ENTITY_PRIMARY_KEYS:
        raise HTTPException(status_code=400, detail=f"unknown entity type: {entity_type}")
    hops = max(1, min(3, int(hops)))
    client = _ensure_graph_projected()
    result = fetch_entity_neighborhood(client, entity_type, entity_id, hops=hops)
    if len(result["nodes"]) <= 1 and not result["edges"]:
        raise HTTPException(status_code=404, detail=f"entity not found in graph: {entity_type}:{entity_id}")
    return result


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "version": config.APP_VERSION}


@app.get("/api/stats")
def stats(
    workspace_id: str | None = None,
    x_workspace_id: Annotated[str | None, Header(alias="X-Workspace-Id")] = None,
    x_user_role: Annotated[str | None, Header(alias="X-User-Role")] = None,
) -> dict:
    """Return dashboard analytics and spend exposure KPIs."""
    _enforce_rbac(x_user_role, "read")
    ws_id = _resolve_workspace_id(workspace_id, x_workspace_id)
    conn = _get_ready_conn()
    try:
        return get_stats(conn, workspace_id=ws_id)
    finally:
        conn.close()


@app.get("/api/batches")
def list_batches(
    workspace_id: str | None = None,
    x_workspace_id: Annotated[str | None, Header(alias="X-Workspace-Id")] = None,
    x_user_role: Annotated[str | None, Header(alias="X-User-Role")] = None,
) -> list[dict]:
    """List all ingested document batches."""
    _enforce_rbac(x_user_role, "read")
    ws_id = _resolve_workspace_id(workspace_id, x_workspace_id)
    conn = _get_ready_conn()
    try:
        rows = conn.execute(
            "SELECT * FROM batches WHERE workspace_id = ? ORDER BY created_at DESC",
            (ws_id,),
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


@app.get("/api/batches/{batch_id}")
def get_batch(
    batch_id: str,
    x_user_role: Annotated[str | None, Header(alias="X-User-Role")] = None,
) -> dict:
    _enforce_rbac(x_user_role, "read")
    conn = _get_ready_conn()
    try:
        row = conn.execute(
            "SELECT * FROM batches WHERE batch_id = ?", (batch_id,)
        ).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Batch not found")
        return dict(row)
    finally:
        conn.close()


@app.post("/api/seed/sample_data")
def seed_demo_data(
    workspace_id: str | None = None,
    x_workspace_id: Annotated[str | None, Header(alias="X-Workspace-Id")] = None,
    x_user_role: Annotated[str | None, Header(alias="X-User-Role")] = None,
) -> dict:
    """1-click populate the database with the official demo sample dataset."""
    _enforce_rbac(x_user_role, "upload")
    ws_id = _resolve_workspace_id(workspace_id, x_workspace_id)
    conn = _get_ready_conn()
    try:
        sample_dir = Path(__file__).resolve().parent.parent.parent / "sample_data"
        if not sample_dir.exists():
            raise HTTPException(status_code=404, detail="sample_data directory not found")
        return seed_sample_dataset(conn, sample_dir, workspace_id=ws_id)
    finally:
        conn.close()


@app.post("/api/ingest/upload")
async def upload(
    kind: str = Form(...),
    file: UploadFile = File(...),
    workspace_id: str | None = None,
    x_workspace_id: Annotated[str | None, Header(alias="X-Workspace-Id")] = None,
    x_user_role: Annotated[str | None, Header(alias="X-User-Role")] = None,
) -> dict:
    """Store an uploaded CSV/PDF, validate CSV headers, register a batch, and ingest rows (docs/05)."""
    _enforce_rbac(x_user_role, "upload")
    ws_id = _resolve_workspace_id(workspace_id, x_workspace_id)
    if kind not in VALID_KINDS:
        raise HTTPException(status_code=400, detail=f"unknown kind: {kind}")

    conn = _get_ready_conn()
    try:
        cur = conn.execute("SELECT COUNT(*) AS n FROM batches")
        batch_id = f"B-{cur.fetchone()['n'] + 1:04d}"
        dest = save_stream_to_upload(file.file, file.filename or "upload", batch_id)

        problems: list[str] = []
        rows_detected = 0
        if dest.suffix.lower() == ".csv":
            problems = validate_csv(dest, kind)
            if not problems:
                rows_detected = ingest_csv_file_to_table(
                    conn, dest, kind, workspace_id=ws_id
                )
            else:
                with dest.open("r", encoding="utf-8", errors="replace") as fh:
                    rows_detected = max(sum(1 for _ in fh) - 1, 0)

        state = "uploaded" if (problems or dest.suffix.lower() != ".csv") else "ready"
        conn.execute(
            "INSERT INTO batches (batch_id, kind, stored_path, rows_detected, state, workspace_id) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (batch_id, kind, str(dest), rows_detected, state, ws_id),
        )
        conn.execute(
            """INSERT INTO audit_log (actor, action, object_type, object_id, detail, workspace_id)
               VALUES ('ingest_api', 'ingest', 'batch', ?, ?, ?)""",
            (batch_id, f"Uploaded {dest.name} ({kind}, {rows_detected} rows)", ws_id),
        )
        conn.commit()
        evidence_obj = store_evidence_object(dest, batch_id, file.filename or "upload")
        return {
            "batch_id": batch_id,
            "kind": kind,
            "stored": str(dest),
            "rows_detected": rows_detected,
            "problems": problems,
            "sha256": evidence_obj["sha256"],
            "storage_uri": evidence_obj["uri"],
            "workspace_id": ws_id,
        }
    finally:
        conn.close()


@app.post("/api/run/{batch_id}/extract")
def run_extract(
    batch_id: str,
    workspace_id: str | None = None,
    x_workspace_id: Annotated[str | None, Header(alias="X-Workspace-Id")] = None,
    x_user_role: Annotated[str | None, Header(alias="X-User-Role")] = None,
) -> dict:
    """Extract CSV or PDF/scan batch into normalized structured records (docs/06)."""
    _enforce_rbac(x_user_role, "upload")
    ws_id = _resolve_workspace_id(workspace_id, x_workspace_id)
    conn = _get_ready_conn()
    try:
        return run_extraction_for_batch(conn, batch_id, workspace_id=ws_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    finally:
        conn.close()


@app.post("/api/run/{batch_id}/detect")
def run_detect(
    batch_id: str,
    workspace_id: str | None = None,
    x_workspace_id: Annotated[str | None, Header(alias="X-Workspace-Id")] = None,
    x_user_role: Annotated[str | None, Header(alias="X-User-Role")] = None,
) -> dict:
    _enforce_rbac(x_user_role, "run_detection")
    ws_id = _resolve_workspace_id(workspace_id, x_workspace_id)
    conn = _get_ready_conn()
    try:
        result = run_detection(conn, batch_id=batch_id, workspace_id=ws_id)
        conn.execute(
            "UPDATE batches SET state = 'detected' WHERE batch_id = ? AND workspace_id = ?",
            (batch_id, ws_id),
        )
        conn.commit()
        result["batch_id"] = batch_id
        return result
    finally:
        conn.close()


@app.post("/api/run-detection")
def run_global_detect(
    workspace_id: str | None = None,
    x_workspace_id: Annotated[str | None, Header(alias="X-Workspace-Id")] = None,
    x_user_role: Annotated[str | None, Header(alias="X-User-Role")] = None,
) -> dict:
    """Trigger full detection across all current tables."""
    _enforce_rbac(x_user_role, "run_detection")
    ws_id = _resolve_workspace_id(workspace_id, x_workspace_id)
    conn = _get_ready_conn()
    try:
        return run_detection(conn, workspace_id=ws_id)
    finally:
        conn.close()


@app.get("/api/findings")
def list_findings(
    status: str | None = None,
    severity: str | None = None,
    rule_id: str | None = None,
    workspace_id: str | None = None,
    x_workspace_id: Annotated[str | None, Header(alias="X-Workspace-Id")] = None,
    x_user_role: Annotated[str | None, Header(alias="X-User-Role")] = None,
) -> list[dict]:
    _enforce_rbac(x_user_role, "read")
    ws_id = _resolve_workspace_id(workspace_id, x_workspace_id)
    query = "SELECT * FROM findings WHERE workspace_id = ?"
    params: list = [ws_id]
    if status and status != "all":
        query += " AND status = ?"
        params.append(status)
    if severity and severity != "all":
        query += " AND severity = ?"
        params.append(severity)
    if rule_id and rule_id != "all":
        query += " AND rule_id = ?"
        params.append(rule_id)
    query += " ORDER BY amount_at_risk DESC"

    conn = _get_ready_conn()
    try:
        rows = [dict(r) for r in conn.execute(query, params).fetchall()]
    finally:
        conn.close()
    for row in rows:
        row["entity_refs"] = json.loads(row.get("entity_refs") or "{}")
        row["evidence"] = json.loads(row.get("evidence") or "[]")
        row["proof_trail"] = json.loads(row.get("proof_trail") or "{}")
        if row.get("explanation"):
            try:
                row["explanation"] = json.loads(row["explanation"])
            except Exception:
                pass
    return rows


@app.get("/api/findings/{finding_id}")
def get_finding(
    finding_id: str,
    x_user_role: Annotated[str | None, Header(alias="X-User-Role")] = None,
) -> dict:
    _enforce_rbac(x_user_role, "read")
    conn = _get_ready_conn()
    try:
        finding = get_finding_with_sources(conn, finding_id)
        if finding is None:
            raise HTTPException(status_code=404, detail=f"finding not found: {finding_id}")
        return finding
    finally:
        conn.close()


@app.post("/api/findings/{finding_id}/decision")
def decide(
    finding_id: str,
    body: DecisionIn,
    x_user_role: Annotated[str | None, Header(alias="X-User-Role")] = None,
) -> dict:
    _enforce_rbac(x_user_role, "decide")
    conn = _get_ready_conn()
    try:
        return record_decision(conn, finding_id, body.action, body.reviewer, body.note)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    finally:
        conn.close()


@app.get("/api/memo")
def memo(
    batch_id: str | None = None,
    workspace_id: str | None = None,
    x_workspace_id: Annotated[str | None, Header(alias="X-Workspace-Id")] = None,
    x_user_role: Annotated[str | None, Header(alias="X-User-Role")] = None,
) -> dict:
    _enforce_rbac(x_user_role, "read")
    ws_id = _resolve_workspace_id(workspace_id, x_workspace_id)
    conn = _get_ready_conn()
    try:
        return build_memo_structured(conn, batch_id=batch_id, workspace_id=ws_id)
    finally:
        conn.close()


@app.get("/api/audit-log")
def audit_log(
    workspace_id: str | None = None,
    x_workspace_id: Annotated[str | None, Header(alias="X-Workspace-Id")] = None,
    x_user_role: Annotated[str | None, Header(alias="X-User-Role")] = None,
) -> list[dict]:
    _enforce_rbac(x_user_role, "read")
    ws_id = _resolve_workspace_id(workspace_id, x_workspace_id)
    conn = _get_ready_conn()
    try:
        rows = conn.execute(
            "SELECT * FROM audit_log WHERE workspace_id = ? ORDER BY id DESC LIMIT 100",
            (ws_id,),
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


@app.get("/api/skills")
def list_skills() -> dict:
    """List Google Agent Skills / Gemini function-calling declarations."""
    return {"tools": GEMINI_TOOL_DECLARATIONS}


@app.post("/api/skills/{tool_name}")
def invoke_skill(tool_name: str, payload: dict[str, Any] = Body(default_factory=dict)) -> dict:
    """Invoke a Google Agent Skill tool deterministically against the audit DB."""
    conn = _get_ready_conn()
    try:
        return execute_skill(conn, tool_name, payload)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    finally:
        conn.close()


@app.get("/api/gcp/status")
def gcp_status() -> dict:
    """Return per-service GCP readiness status and AlloyDB connectivity."""
    status = get_gcp_readiness_status()
    status["alloydb_connection"] = check_alloydb_connection()
    return status


@app.post("/api/gcp/bigquery/sync")
def bigquery_sync() -> dict:
    """Sync SQLite audit tables into BigQuery (or local simulation fallback)."""
    conn = _get_ready_conn()
    try:
        return sync_to_bigquery(conn)
    finally:
        conn.close()


@app.get("/api/analytics/executive")
def executive_analytics(
    workspace_id: str | None = None,
    x_workspace_id: Annotated[str | None, Header(alias="X-Workspace-Id")] = None,
    x_user_role: Annotated[str | None, Header(alias="X-User-Role")] = None,
) -> dict:
    """Return FX-normalized INR KPIs, vendor exposure ranking, and R1-R5 breakdown."""
    _enforce_rbac(x_user_role, "read")
    ws_id = _resolve_workspace_id(workspace_id, x_workspace_id)
    conn = _get_ready_conn()
    scoped_conn = None
    try:
        scoped_conn = make_workspace_view_conn(conn, workspace_id=ws_id)
        return compute_executive_analytics(scoped_conn)
    finally:
        if scoped_conn is not None:
            scoped_conn.close()
        conn.close()


@app.get("/api/findings/{finding_id}/dispute-packet")
def finding_dispute_packet(
    finding_id: str,
    x_user_role: Annotated[str | None, Header(alias="X-User-Role")] = None,
) -> dict:
    """Generate a formal vendor dispute notice packet for a finding."""
    _enforce_rbac(x_user_role, "export")
    conn = _get_ready_conn()
    try:
        finding = get_finding_with_sources(conn, finding_id)
        if finding is None:
            raise HTTPException(status_code=404, detail=f"finding not found: {finding_id}")
        return generate_dispute_packet(finding)
    finally:
        conn.close()


@app.post("/api/findings/bulk-decision")
def bulk_decide(
    body: BulkDecisionIn,
    x_user_role: Annotated[str | None, Header(alias="X-User-Role")] = None,
) -> dict:
    """Apply a reviewer decision across multiple findings."""
    _enforce_rbac(x_user_role, "decide")
    conn = _get_ready_conn()
    try:
        return apply_bulk_decision(
            conn, body.finding_ids, body.action, body.reviewer, body.note
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    finally:
        conn.close()


@app.get("/api/export/findings.csv")
def export_findings(
    status: str | None = None,
    rule_id: str | None = None,
    workspace_id: str | None = None,
    x_workspace_id: Annotated[str | None, Header(alias="X-Workspace-Id")] = None,
    x_user_role: Annotated[str | None, Header(alias="X-User-Role")] = None,
) -> Response:
    """Export findings as an RFC-4180 CSV download."""
    _enforce_rbac(x_user_role, "export")
    ws_id = _resolve_workspace_id(workspace_id, x_workspace_id)
    conn = _get_ready_conn()
    scoped_conn = None
    try:
        scoped_conn = make_workspace_view_conn(conn, workspace_id=ws_id)
        csv_content = export_findings_csv(scoped_conn, status=status, rule_id=rule_id)
        return Response(
            content=csv_content,
            media_type="text/csv",
            headers={"Content-Disposition": "attachment; filename=ledgerlens-exceptions.csv"},
        )
    finally:
        if scoped_conn is not None:
            scoped_conn.close()
        conn.close()


@app.get("/api/policy")
def read_policy(
    x_user_role: Annotated[str | None, Header(alias="X-User-Role")] = None,
) -> dict:
    """Return current deterministic audit policy thresholds."""
    _enforce_rbac(x_user_role, "read")
    conn = _get_ready_conn()
    try:
        return get_policy(conn)
    finally:
        conn.close()


@app.put("/api/policy")
def write_policy(
    body: PolicyUpdateIn,
    x_user_role: Annotated[str | None, Header(alias="X-User-Role")] = None,
) -> dict:
    """Validate and update deterministic audit policy thresholds."""
    _enforce_rbac(x_user_role, "manage_workspaces")
    conn = _get_ready_conn()
    try:
        return update_policy(conn, body.model_dump(exclude_none=True))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    finally:
        conn.close()


_EDITABLE_INVOICE_FIELDS = (
    "item",
    "quantity",
    "unit_price",
    "tax_pct",
    "line_total",
    "currency",
    "status",
)


@app.patch("/api/batches/{batch_id}/records")
def update_batch_records(batch_id: str, body: BatchRecordsUpdateIn) -> dict:
    """Update quarantined needs_review invoice lines and mark batch ready for re-detection."""
    conn = _get_ready_conn()
    try:
        batch = conn.execute(
            "SELECT batch_id FROM batches WHERE batch_id = ?", (batch_id,)
        ).fetchone()
        if not batch:
            raise HTTPException(status_code=404, detail="Batch not found")

        updated = 0
        for rec in body.records:
            inv_num = rec.get("invoice_number")
            line_no = rec.get("line_no", 1)
            if not inv_num:
                continue
            updates = {k: rec[k] for k in _EDITABLE_INVOICE_FIELDS if k in rec}
            if not updates:
                continue
            set_clause = ", ".join(f"{col} = ?" for col in updates)
            params = [*updates.values(), inv_num, line_no]
            cur = conn.execute(
                f"UPDATE invoices SET {set_clause} WHERE invoice_number = ? AND line_no = ?",
                params,
            )
            updated += cur.rowcount

        conn.execute(
            "UPDATE batches SET state = 'extracted' WHERE batch_id = ?",
            (batch_id,),
        )
        conn.commit()
        return {"batch_id": batch_id, "updated": updated, "state": "extracted"}
    finally:
        conn.close()


@app.get("/api/batches/{batch_id}/file")
def get_batch_file(batch_id: str):
    """Serve an uploaded batch PDF or image file safely from inside UPLOAD_DIR."""
    conn = _get_ready_conn()
    try:
        row = conn.execute(
            "SELECT stored_path FROM batches WHERE batch_id = ?", (batch_id,)
        ).fetchone()
        if not row or not row["stored_path"]:
            raise HTTPException(status_code=404, detail="Batch file not found")

        upload_root = Path(config.UPLOAD_DIR).resolve()
        candidate = Path(row["stored_path"]).resolve()
        if not candidate.is_relative_to(upload_root) or not candidate.is_file():
            raise HTTPException(status_code=404, detail="Batch file not found")
        return FileResponse(str(candidate))
    finally:
        conn.close()


@app.get("/api/fx/rates")
def read_fx_rates() -> dict[str, float]:
    """Return cached or reference FX rates (base INR=1.0)."""
    conn = _get_ready_conn()
    try:
        return get_fx_rates(conn, fetch_live=False)
    finally:
        conn.close()


@app.get("/api/audit-log/verify")
def verify_audit_log(
    x_user_role: Annotated[str | None, Header(alias="X-User-Role")] = None,
) -> dict:
    """Verify cryptographic hash-chain integrity across audit_chain rows."""
    _enforce_rbac(x_user_role, "verify_audit")
    conn = _get_ready_conn()
    try:
        ensure_audit_chain_table(conn)
        rows = conn.execute("SELECT * FROM audit_chain ORDER BY id ASC").fetchall()
        return verify_audit_chain(rows)
    finally:
        conn.close()


@app.get("/api/workspaces")
def get_workspaces(
    x_user_role: Annotated[str | None, Header(alias="X-User-Role")] = None,
) -> list[dict]:
    """List tenant workspaces (auto-seeding default if empty)."""
    _enforce_rbac(x_user_role, "read")
    conn = _get_ready_conn()
    try:
        return list_workspaces(conn)
    finally:
        conn.close()


@app.post("/api/workspaces")
def post_workspace(
    body: WorkspaceCreateIn,
    x_user_role: Annotated[str | None, Header(alias="X-User-Role")] = None,
) -> dict:
    """Create a new multi-tenant workspace."""
    _enforce_rbac(x_user_role, "manage_workspaces")
    conn = _get_ready_conn()
    try:
        return create_workspace(conn, body.name, client_code=body.client_code)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    finally:
        conn.close()


@app.post("/api/copilot/ask")
def post_copilot_ask(
    body: CopilotAskIn,
    x_user_role: Annotated[str | None, Header(alias="X-User-Role")] = None,
) -> dict:
    """Answer a CFO question grounded in findings and proof_trail math."""
    _enforce_rbac(x_user_role, "read")
    conn = _get_ready_conn()
    try:
        return ask_copilot(conn, body.question, workspace_id=body.workspace_id)
    finally:
        conn.close()


_FRONTEND_DIST = Path(
    os.getenv(
        "FRONTEND_DIST",
        str(Path(__file__).resolve().parent.parent.parent / "frontend" / "dist"),
    )
).resolve()

if (_FRONTEND_DIST / "index.html").is_file():
    _assets_dir = _FRONTEND_DIST / "assets"
    if _assets_dir.is_dir():
        app.mount("/assets", StaticFiles(directory=str(_assets_dir)), name="assets")

    @app.get("/{full_path:path}", include_in_schema=False)
    def serve_spa(full_path: str):
        """Serve built React SPA for Cloud Run unified deployment without masking API 404s."""
        if full_path.startswith("api/") or full_path == "api":
            raise HTTPException(status_code=404, detail="API route not found")
        candidate = (_FRONTEND_DIST / full_path).resolve()
        if full_path and candidate.is_file() and candidate.is_relative_to(_FRONTEND_DIST):
            return FileResponse(str(candidate))
        return FileResponse(str(_FRONTEND_DIST / "index.html"))

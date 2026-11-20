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
    """Open configured SQLite connection and lazily initialize schema if absent."""
    conn = get_connection()
    has_batches = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name='batches'"
    ).fetchone()
    if has_batches is None:
        init_schema(conn)
    else:
        b_cols = {r["name"] for r in conn.execute("PRAGMA table_info(batches)").fetchall()}
        if "workspace_id" not in b_cols:
            init_schema(conn)
    return conn


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

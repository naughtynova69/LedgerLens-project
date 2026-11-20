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
  [done] GET  /api/memo                     — deterministic audit memo
  [done] GET  /api/audit-log                — immutable decision history
"""
from __future__ import annotations

import json
from contextlib import asynccontextmanager
from pathlib import Path
import sqlite3

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware

from . import config
from .db import get_connection, init_schema
from .ingest.router import VALID_KINDS, save_stream_to_upload, validate_csv
from .models import DecisionIn
from .services import (
    build_memo,
    get_finding_with_sources,
    get_stats,
    ingest_csv_file_to_table,
    record_decision,
    run_detection,
    run_extraction_for_batch,
    seed_sample_dataset,
)


def _get_ready_conn() -> sqlite3.Connection:
    """Open configured SQLite connection and lazily initialize schema if absent."""
    conn = get_connection()
    has_batches = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name='batches'"
    ).fetchone()
    if has_batches is None:
        init_schema(conn)
    return conn


@asynccontextmanager
async def lifespan(_: FastAPI):
    conn = _get_ready_conn()
    conn.close()
    yield


app = FastAPI(
    title="LedgerLens API",
    version=config.APP_VERSION,
    description="Explainable AI money-leak auditor. Gemini extracts and explains; "
                "the rules engine decides; the workflow logs.",
    lifespan=lifespan,
)

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
def stats() -> dict:
    """Return dashboard analytics and spend exposure KPIs."""
    conn = _get_ready_conn()
    try:
        return get_stats(conn)
    finally:
        conn.close()


@app.get("/api/batches")
def list_batches() -> list[dict]:
    """List all ingested document batches."""
    conn = _get_ready_conn()
    try:
        rows = conn.execute(
            "SELECT * FROM batches ORDER BY created_at DESC"
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


@app.get("/api/batches/{batch_id}")
def get_batch(batch_id: str) -> dict:
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
def seed_demo_data() -> dict:
    """1-click populate the database with the official demo sample dataset."""
    conn = _get_ready_conn()
    try:
        sample_dir = Path(__file__).resolve().parent.parent.parent / "sample_data"
        if not sample_dir.exists():
            raise HTTPException(status_code=404, detail="sample_data directory not found")
        return seed_sample_dataset(conn, sample_dir)
    finally:
        conn.close()


@app.post("/api/ingest/upload")
async def upload(kind: str = Form(...), file: UploadFile = File(...)) -> dict:
    """Store an uploaded CSV/PDF, validate CSV headers, register a batch, and ingest rows (docs/05)."""
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
                rows_detected = ingest_csv_file_to_table(conn, dest, kind)
            else:
                with dest.open("r", encoding="utf-8", errors="replace") as fh:
                    rows_detected = max(sum(1 for _ in fh) - 1, 0)

        state = "uploaded" if (problems or dest.suffix.lower() != ".csv") else "ready"
        conn.execute(
            "INSERT INTO batches (batch_id, kind, stored_path, rows_detected, state) "
            "VALUES (?, ?, ?, ?, ?)",
            (batch_id, kind, str(dest), rows_detected, state),
        )
        conn.execute(
            """INSERT INTO audit_log (actor, action, object_type, object_id, detail)
               VALUES ('ingest_api', 'ingest', 'batch', ?, ?)""",
            (batch_id, f"Uploaded {dest.name} ({kind}, {rows_detected} rows)"),
        )
        conn.commit()
        return {
            "batch_id": batch_id,
            "kind": kind,
            "stored": str(dest),
            "rows_detected": rows_detected,
            "problems": problems,
        }
    finally:
        conn.close()


@app.post("/api/run/{batch_id}/extract")
def run_extract(batch_id: str) -> dict:
    """Extract CSV or PDF/scan batch into normalized structured records (docs/06)."""
    conn = _get_ready_conn()
    try:
        return run_extraction_for_batch(conn, batch_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    finally:
        conn.close()


@app.post("/api/run/{batch_id}/detect")
def run_detect(batch_id: str) -> dict:
    conn = _get_ready_conn()
    try:
        result = run_detection(conn)
        conn.execute("UPDATE batches SET state = 'detected' WHERE batch_id = ?", (batch_id,))
        conn.commit()
        result["batch_id"] = batch_id
        return result
    finally:
        conn.close()


@app.post("/api/run-detection")
def run_global_detect() -> dict:
    """Trigger full detection across all current tables."""
    conn = _get_ready_conn()
    try:
        return run_detection(conn)
    finally:
        conn.close()


@app.get("/api/findings")
def list_findings(status: str | None = None, severity: str | None = None,
                  rule_id: str | None = None) -> list[dict]:
    query = "SELECT * FROM findings WHERE 1=1"
    params: list = []
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
def get_finding(finding_id: str) -> dict:
    conn = _get_ready_conn()
    try:
        finding = get_finding_with_sources(conn, finding_id)
        if finding is None:
            raise HTTPException(status_code=404, detail=f"finding not found: {finding_id}")
        return finding
    finally:
        conn.close()


@app.post("/api/findings/{finding_id}/decision")
def decide(finding_id: str, body: DecisionIn) -> dict:
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
def memo() -> dict:
    conn = _get_ready_conn()
    try:
        return {"memo_markdown": build_memo(conn)}
    finally:
        conn.close()


@app.get("/api/audit-log")
def audit_log() -> list[dict]:
    conn = _get_ready_conn()
    try:
        rows = conn.execute("SELECT * FROM audit_log ORDER BY id DESC LIMIT 100").fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()

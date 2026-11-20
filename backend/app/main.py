"""LedgerLens API — routes follow docs/05_API_SPEC.md.

Endpoints:
  [done] GET  /health
  [done] GET  /api/stats                    — KPI analytics for the dashboard
  [done] GET  /api/batches                  — list all ingested document batches
  [done] POST /api/ingest/upload            — stores file, validates CSV, ingests rows into DB
  [done] POST /api/seed/sample_data         — 1-click load demo dataset & run detection
  [done] POST /api/run/{batch_id}/detect    — normalize + R1..R5 over the DB
  [done] GET  /api/findings                 — exception queue with filters
  [done] GET  /api/findings/{id}            — finding + joined evidence source records
  [done] POST /api/findings/{id}/decision   — approve/reject/request_docs/recovery
  [done] GET  /api/memo                     — deterministic audit memo
  [done] GET  /api/audit-log                — immutable decision history
  [todo] POST /api/run/{batch_id}/extract   — Gemini extraction for raw scans
"""
from __future__ import annotations

import json
from contextlib import asynccontextmanager
from pathlib import Path

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
    seed_sample_dataset,
)


@asynccontextmanager
async def lifespan(_: FastAPI):
    init_schema(get_connection())
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
    conn = get_connection()
    try:
        return get_stats(conn)
    finally:
        conn.close()


@app.get("/api/batches")
def list_batches() -> list[dict]:
    """List all ingested document batches."""
    conn = get_connection()
    try:
        rows = conn.execute(
            "SELECT * FROM batches ORDER BY created_at DESC"
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


@app.get("/api/batches/{batch_id}")
def get_batch(batch_id: str) -> dict:
    conn = get_connection()
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
    conn = get_connection()
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

    conn = get_connection()
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

        conn.execute(
            "INSERT INTO batches (batch_id, kind, stored_path, rows_detected, state) "
            "VALUES (?, ?, ?, ?, ?)",
            (batch_id, kind, str(dest), rows_detected, "uploaded" if problems else "ready"),
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
    # Gemini extraction endpoint for scanned PDFs (docs/06)
    raise HTTPException(
        status_code=501,
        detail="Gemini PDF extraction endpoint — CSV path is already ingested and ready for detection.",
    )


@app.post("/api/run/{batch_id}/detect")
def run_detect(batch_id: str) -> dict:
    conn = get_connection()
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
    conn = get_connection()
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

    conn = get_connection()
    try:
        rows = [dict(r) for r in conn.execute(query, params).fetchall()]
    finally:
        conn.close()
    for row in rows:
        row["entity_refs"] = json.loads(row.get("entity_refs") or "{}")
        row["evidence"] = json.loads(row.get("evidence") or "[]")
        if row.get("explanation"):
            try:
                row["explanation"] = json.loads(row["explanation"])
            except Exception:
                pass
    return rows


@app.get("/api/findings/{finding_id}")
def get_finding(finding_id: str) -> dict:
    conn = get_connection()
    try:
        finding = get_finding_with_sources(conn, finding_id)
        if finding is None:
            raise HTTPException(status_code=404, detail=f"finding not found: {finding_id}")
        return finding
    finally:
        conn.close()


@app.post("/api/findings/{finding_id}/decision")
def decide(finding_id: str, body: DecisionIn) -> dict:
    conn = get_connection()
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
    conn = get_connection()
    try:
        return {"memo_markdown": build_memo(conn)}
    finally:
        conn.close()


@app.get("/api/audit-log")
def audit_log() -> list[dict]:
    conn = get_connection()
    try:
        rows = conn.execute("SELECT * FROM audit_log ORDER BY id DESC LIMIT 100").fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()

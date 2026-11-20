"""Service layer between the API routes and the deterministic core.

Everything in this module is framework-free (stdlib + app.detect/extract/explain only)
so the full pipeline is unit-testable without installing FastAPI.
"""
from __future__ import annotations

import csv
from datetime import datetime, timezone
import json
from pathlib import Path
import sqlite3

from . import config
from .audit_chain import append_chained_audit_event
from .detect import DetectionContext
from .detect.registry import run_all_rules
from .explain.gemini_explain import fallback_without_gemini
from .extract import extract_document
from .finance.policy import get_policy
from .gcp.pubsub import publish_recovery_event
from .gcp.vertex_ai import has_live_ai_credentials
from .normalize.fx_service import get_fx_rates

_ALLOWED_COLUMNS = {
    "vendors": {
        "vendor_id", "vendor_name", "tax_id", "default_currency", "status",
        "bank_account", "email", "phone", "address",
    },
    "contracts": {
        "contract_id", "vendor_id", "item", "contracted_unit_price", "currency",
        "discount_pct", "payment_terms", "tax_pct", "start_date", "end_date", "status",
        "amends_contract_id", "version",
    },
    "purchase_orders": {
        "po_id", "po_line", "vendor_id", "item", "quantity", "unit_price",
        "currency", "order_date", "expected_delivery", "status",
    },
    "invoices": {
        "invoice_number", "vendor_id", "invoice_date", "po_id", "line_no", "item",
        "quantity", "unit_price", "currency", "tax_pct", "line_total", "source_file", "status",
        "approver_id",
    },
    "payments": {
        "payment_id", "invoice_number", "amount", "currency", "fx_rate_to_inr",
        "payment_date", "status", "account_key",
    },
    "approvers": {
        "approver_id", "name", "email", "phone", "address", "bank_account", "approval_limit",
    },
    "credit_notes": {
        "credit_note_id", "vendor_id", "issue_date", "amount", "currency", "applied_status",
    },
}


def _rows(conn: sqlite3.Connection, table: str, workspace_id: str = "default") -> list[dict]:
    """Fetch all rows from a table (scoped by workspace_id where applicable) using static SQL."""
    if table == "vendors":
        return [dict(row) for row in conn.execute('SELECT * FROM "vendors"').fetchall()]

    match table:
        case "contracts":
            sql = 'SELECT * FROM "contracts" WHERE workspace_id = ?'
        case "purchase_orders":
            sql = 'SELECT * FROM "purchase_orders" WHERE workspace_id = ?'
        case "invoices":
            sql = 'SELECT * FROM "invoices" WHERE workspace_id = ?'
        case "payments":
            sql = 'SELECT * FROM "payments" WHERE workspace_id = ?'
        case _:
            raise ValueError(f"unknown table: {table}")
    return [dict(row) for row in conn.execute(sql, (workspace_id,)).fetchall()]


def _ensure_vendor_exists(
    conn: sqlite3.Connection,
    vendor_id: str,
    vendor_name: str | None = None,
    currency: str = "INR",
) -> None:
    if not vendor_id:
        return
    exists = conn.execute(
        "SELECT 1 FROM vendors WHERE vendor_id = ?", (vendor_id,)
    ).fetchone()
    if exists is None:
        conn.execute(
            "INSERT INTO vendors (vendor_id, vendor_name, default_currency, status) "
            "VALUES (?, ?, ?, 'active')",
            (vendor_id, vendor_name or vendor_id, currency or "INR"),
        )


def _insert_table_rows(
    conn: sqlite3.Connection,
    table_name: str,
    records: list[dict],
    workspace_id: str = "default",
) -> int:
    allowed = _ALLOWED_COLUMNS[table_name]
    inserted = 0
    for row in records:
        if table_name in ("contracts", "purchase_orders", "invoices"):
            _ensure_vendor_exists(
                conn,
                str(row.get("vendor_id") or ""),
                row.get("vendor_name"),
                str(row.get("currency") or "INR"),
            )
        filtered = {k: v for k, v in row.items() if k in allowed}
        if not filtered:
            continue
        if table_name in ("contracts", "purchase_orders", "invoices", "payments"):
            filtered["workspace_id"] = workspace_id
        cols = list(filtered.keys())
        placeholders = ",".join(["?"] * len(cols))
        conn.execute(
            f"INSERT OR REPLACE INTO {table_name} ({','.join(cols)}) VALUES ({placeholders})",
            list(filtered.values()),
        )
        inserted += 1
    return inserted


def _log_audit_event(
    conn: sqlite3.Connection,
    actor: str,
    action: str,
    object_type: str,
    object_id: str,
    detail: str = "",
    workspace_id: str = "default",
) -> None:
    """Insert an audit_log row and append the corresponding hash-chained entry."""
    conn.execute(
        """INSERT INTO audit_log (actor, action, object_type, object_id, detail, workspace_id)
           VALUES (?, ?, ?, ?, ?, ?)""",
        (actor, action, object_type, object_id, detail, workspace_id),
    )
    append_chained_audit_event(
        conn,
        actor=actor,
        action=action,
        object_type=object_type,
        object_id=object_id,
        detail=detail,
    )


def generate_explanation_for_finding(finding_dict: dict) -> dict:
    """Generate explanation via Gemini/Vertex AI if configured, else use deterministic fallback."""
    if config.GEMINI_API_KEY or has_live_ai_credentials():
        try:
            from .explain.gemini_explain import explain_finding
            return explain_finding(finding_dict)
        except Exception:
            pass
    return fallback_without_gemini(finding_dict)


def run_extraction_for_batch(
    conn: sqlite3.Connection,
    batch_id: str,
    workspace_id: str = "default",
) -> dict:
    """Extract CSV or PDF/scan for a registered batch and persist normalized rows."""
    batch = conn.execute(
        "SELECT * FROM batches WHERE batch_id = ? AND workspace_id = ?",
        (batch_id, workspace_id),
    ).fetchone()
    if batch is None:
        raise LookupError(f"batch not found: {batch_id}")

    kind = batch["kind"]
    stored_path = Path(batch["stored_path"])
    if not stored_path.exists():
        raise FileNotFoundError(f"uploaded file missing for batch {batch_id}: {stored_path}")

    table_name = "payments" if kind == "payment_ledger" else kind
    if table_name not in _ALLOWED_COLUMNS:
        raise ValueError(f"unsupported batch kind: {kind}")

    result = extract_document(stored_path, kind=kind)
    records = result.get("records") or []
    rows_persisted = _insert_table_rows(conn, table_name, records, workspace_id=workspace_id)

    new_state = "needs_review" if result.get("needs_review") else "extracted"
    conn.execute(
        "UPDATE batches SET state = ?, rows_detected = ? WHERE batch_id = ? AND workspace_id = ?",
        (new_state, rows_persisted, batch_id, workspace_id),
    )
    _log_audit_event(
        conn,
        actor="extract_pipeline",
        action="extract",
        object_type="batch",
        object_id=batch_id,
        detail=json.dumps({
            "kind": kind,
            "mode": result.get("mode"),
            "model": result.get("model"),
            "rows_extracted": rows_persisted,
            "warnings": len(result.get("verification_warnings") or []),
        }),
        workspace_id=workspace_id,
    )

    return {
        "batch_id": batch_id,
        "kind": kind,
        "state": new_state,
        "mode": result.get("mode"),
        "model": result.get("model"),
        "rows_extracted": rows_persisted,
        table_name: rows_persisted,
        "verification_warnings": result.get("verification_warnings") or [],
        "needs_review": bool(result.get("needs_review")),
    }


def _next_finding_number(conn: sqlite3.Connection) -> int:
    max_num = 0
    for row in conn.execute("SELECT finding_id FROM findings").fetchall():
        fid = str(row["finding_id"] or "")
        if fid.startswith("F-") and fid[2:].isdigit():
            max_num = max(max_num, int(fid[2:]))
    return max_num + 1


def _collect_graph_evidence(conn: sqlite3.Connection, graph_client, batch_id: str | None) -> dict:
    """Project the relational DB into LadybugDB and fetch deterministic evidence.

    Only active when the graph layer is enabled (config or explicit client).
    Degradation is deliberate and silent: if the optional graph engine cannot
    run, tabular R1-R5 detection proceeds exactly as before.
    """
    if graph_client is None and not config.GRAPH_ENABLED:
        return {}
    owned = graph_client is None
    if owned:
        from .graph import get_graph_client

        graph_client = get_graph_client()
    try:
        from .graph import fetch_graph_evidence, project_batch_to_graph

        project_batch_to_graph(conn, graph_client, batch_id=batch_id)
        evidence = fetch_graph_evidence(graph_client)
    except Exception:
        return {}
    finally:
        if owned:
            graph_client.close()
    return {
        "cross_entity_duplicates": evidence.cross_entity_duplicates,
        "split_invoices": evidence.split_invoices,
        "collusion": evidence.collusion,
        "superseded_rates": evidence.superseded_rates,
        "unapplied_credits": evidence.unapplied_credits,
    }


def run_detection(
    conn: sqlite3.Connection,
    batch_id: str | None = None,
    graph_client=None,
    workspace_id: str = "default",
) -> dict:
    """Load normalized tables, run every registered rule, persist findings.

    When the graph layer is enabled (or a graph client is injected), the batch
    is first projected into LadybugDB and deterministic Cypher evidence for
    rules R8-R10 is attached to the detection context.

    Returns {"findings_created": int, "finding_ids": [...]}.
    """
    policy = dict(get_policy(conn))
    policy["fx_rates"] = get_fx_rates(conn, fetch_live=False)
    ctx = DetectionContext(
        invoices=_rows(conn, "invoices", workspace_id=workspace_id),
        payments=_rows(conn, "payments", workspace_id=workspace_id),
        purchase_orders=_rows(conn, "purchase_orders", workspace_id=workspace_id),
        contracts=_rows(conn, "contracts", workspace_id=workspace_id),
        vendors=_rows(conn, "vendors", workspace_id=workspace_id),
        policy=policy,
        graph_evidence=_collect_graph_evidence(conn, graph_client, batch_id),
    )
    findings = run_all_rules(ctx, policy=policy)

    existing_rows = conn.execute(
        "SELECT finding_id, rule_id, entity_refs, status FROM findings WHERE workspace_id = ?",
        (workspace_id,),
    ).fetchall()
    existing_by_key: dict[tuple[str, str], dict] = {}
    for er in existing_rows:
        try:
            canon_refs = json.dumps(json.loads(er["entity_refs"] or "{}"), sort_keys=True)
        except Exception:
            canon_refs = str(er["entity_refs"] or "{}")
        existing_by_key[(er["rule_id"], canon_refs)] = dict(er)

    next_num = _next_finding_number(conn)
    created: list[str] = []
    for finding in findings:
        canon_key = (finding.rule_id, json.dumps(finding.entity_refs, sort_keys=True))
        matched = existing_by_key.get(canon_key)
        if matched is not None:
            finding_id = matched["finding_id"]
            status = matched["status"]
        else:
            finding_id = f"F-{next_num:04d}"
            next_num += 1
            status = "open"

        f_dict = finding.as_dict()
        f_dict["finding_id"] = finding_id
        explanation = generate_explanation_for_finding(f_dict)

        if matched is not None:
            conn.execute(
                """UPDATE findings
                   SET rule_id = ?, title = ?, severity = ?, amount_at_risk = ?,
                       currency = ?, entity_refs = ?, evidence = ?, confidence = ?,
                       summary = ?, explanation = ?, recommended_action = ?, proof_trail = ?
                   WHERE finding_id = ? AND workspace_id = ?""",
                (
                    finding.rule_id,
                    finding.title,
                    finding.severity,
                    finding.amount_at_risk,
                    finding.currency,
                    json.dumps(finding.entity_refs),
                    json.dumps([e.as_dict() for e in finding.evidence]),
                    finding.confidence,
                    finding.summary,
                    json.dumps(explanation),
                    finding.recommended_action,
                    json.dumps(finding.proof_trail),
                    finding_id,
                    workspace_id,
                ),
            )
        else:
            conn.execute(
                """INSERT INTO findings
                   (finding_id, rule_id, title, severity, amount_at_risk, currency,
                    status, entity_refs, evidence, confidence, summary, explanation,
                    recommended_action, proof_trail, workspace_id)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    finding_id,
                    finding.rule_id,
                    finding.title,
                    finding.severity,
                    finding.amount_at_risk,
                    finding.currency,
                    status,
                    json.dumps(finding.entity_refs),
                    json.dumps([e.as_dict() for e in finding.evidence]),
                    finding.confidence,
                    finding.summary,
                    json.dumps(explanation),
                    finding.recommended_action,
                    json.dumps(finding.proof_trail),
                    workspace_id,
                ),
            )
        created.append(finding_id)

    _log_audit_event(
        conn,
        actor="rules_engine",
        action="detect",
        object_type="batch",
        object_id=batch_id or "global",
        detail=(
            f"Evaluated {'R1-R10 with graph evidence' if ctx.graph_evidence else 'R1-R7'} "
            f"across {len(ctx.invoices)} invoice line(s); emitted {len(created)} finding(s)."
        ),
        workspace_id=workspace_id,
    )
    return {"findings_created": len(created), "finding_ids": created}


def record_decision(conn: sqlite3.Connection, finding_id: str, action: str,
                    reviewer: str, note: str = "") -> dict:
    """Apply a reviewer decision, update the finding status, append to audit_log."""
    status_by_action = {
        "approve": "approved",
        "reject": "rejected",
        "request_docs": "open",
        "recovery": "recovery",
        "recover": "recovery",
    }
    if action not in status_by_action:
        raise ValueError(f"unknown action: {action}")

    row = conn.execute("SELECT finding_id, workspace_id FROM findings WHERE finding_id = ?",
                       (finding_id,)).fetchone()
    if row is None:
        raise LookupError(f"finding not found: {finding_id}")

    ws_id = row["workspace_id"] or "default"
    target_status = status_by_action[action]
    conn.execute("UPDATE findings SET status = ? WHERE finding_id = ?",
                 (target_status, finding_id))
    conn.execute(
        "INSERT INTO decisions (finding_id, action, reviewer, note) VALUES (?, ?, ?, ?)",
        (finding_id, action, reviewer, note),
    )
    _log_audit_event(
        conn,
        actor=reviewer,
        action=action,
        object_type="finding",
        object_id=finding_id,
        detail=note,
        workspace_id=ws_id,
    )
    if target_status in ("recovery", "rejected"):
        try:
            publish_recovery_event(
                "finding.decision",
                {
                    "finding_id": finding_id,
                    "status": target_status,
                    "reviewer": reviewer,
                    "note": note,
                },
            )
        except Exception:
            pass
    return {"finding_id": finding_id, "status": target_status}


def get_finding_with_sources(conn: sqlite3.Connection, finding_id: str) -> dict | None:
    """Return finding detail including joined source records for the evidence panel."""
    row = conn.execute("SELECT * FROM findings WHERE finding_id = ?", (finding_id,)).fetchone()
    if row is None:
        return None

    finding = dict(row)
    finding["entity_refs"] = json.loads(finding.get("entity_refs") or "{}")
    finding["evidence"] = json.loads(finding.get("evidence") or "[]")
    finding["proof_trail"] = json.loads(finding.get("proof_trail") or "{}")
    if finding.get("explanation"):
        try:
            finding["explanation"] = json.loads(finding["explanation"])
        except Exception:
            pass

    source_records = {
        "invoices": [],
        "purchase_orders": [],
        "contracts": [],
        "payments": [],
        "vendors": [],
    }

    refs = finding["entity_refs"]
    inv_nums = refs.get("invoice_numbers") or []
    if isinstance(inv_nums, str):
        inv_nums = [inv_nums]
    if inv_nums:
        placeholders = ",".join(["?"] * len(inv_nums))
        source_records["invoices"] = [
            dict(r) for r in conn.execute(
                f"SELECT * FROM invoices WHERE invoice_number IN ({placeholders})", inv_nums
            ).fetchall()
        ]

    po_id = refs.get("po_id")
    if po_id:
        source_records["purchase_orders"] = [
            dict(r) for r in conn.execute(
                "SELECT * FROM purchase_orders WHERE po_id = ?", (po_id,)
            ).fetchall()
        ]

    contract_id = refs.get("contract_id")
    if contract_id:
        source_records["contracts"] = [
            dict(r) for r in conn.execute(
                "SELECT * FROM contracts WHERE contract_id = ?", (contract_id,)
            ).fetchall()
        ]

    payment_ids = refs.get("payment_ids") or []
    if isinstance(payment_ids, str):
        payment_ids = [payment_ids]
    if payment_ids:
        placeholders = ",".join(["?"] * len(payment_ids))
        source_records["payments"] = [
            dict(r) for r in conn.execute(
                f"SELECT * FROM payments WHERE payment_id IN ({placeholders})", payment_ids
            ).fetchall()
        ]
    elif inv_nums:
        placeholders = ",".join(["?"] * len(inv_nums))
        source_records["payments"] = [
            dict(r) for r in conn.execute(
                f"SELECT * FROM payments WHERE invoice_number IN ({placeholders})", inv_nums
            ).fetchall()
        ]

    vendor_id = refs.get("vendor_id")
    if vendor_id:
        source_records["vendors"] = [
            dict(r) for r in conn.execute(
                "SELECT * FROM vendors WHERE vendor_id = ?", (vendor_id,)
            ).fetchall()
        ]

    decisions = [
        dict(r) for r in conn.execute(
            "SELECT * FROM decisions WHERE finding_id = ? ORDER BY id ASC", (finding_id,)
        ).fetchall()
    ]

    finding["source_records"] = source_records
    finding["decisions"] = decisions
    return finding


def get_stats(conn: sqlite3.Connection, workspace_id: str = "default") -> dict:
    """Return dashboard analytics and spend exposure KPIs."""
    findings = [
        dict(r)
        for r in conn.execute(
            "SELECT * FROM findings WHERE workspace_id = ?", (workspace_id,)
        ).fetchall()
    ]
    batches_count = conn.execute(
        "SELECT COUNT(*) AS n FROM batches WHERE workspace_id = ?", (workspace_id,)
    ).fetchone()["n"]

    total_at_risk = sum(f["amount_at_risk"] for f in findings)
    open_at_risk = sum(f["amount_at_risk"] for f in findings if f["status"] == "open")
    recovered_amount = sum(f["amount_at_risk"] for f in findings if f["status"] in ("rejected", "recovery"))

    by_severity = {"critical": 0, "high": 0, "medium": 0, "low": 0}
    by_rule = {}
    by_status = {"open": 0, "approved": 0, "rejected": 0, "recovery": 0}

    for f in findings:
        sev = f["severity"].lower()
        by_severity[sev] = by_severity.get(sev, 0) + 1

        r = f["rule_id"]
        by_rule[r] = by_rule.get(r, 0) + 1

        st = f["status"].lower()
        by_status[st] = by_status.get(st, 0) + 1

    total_audited_spend = 0.0
    try:
        spend_row = conn.execute(
            "SELECT SUM(line_total) AS s FROM invoices WHERE workspace_id = ?",
            (workspace_id,),
        ).fetchone()
        if spend_row and spend_row["s"] is not None:
            total_audited_spend = round(float(spend_row["s"]), 2)
    except Exception:
        pass

    return {
        "total_findings": len(findings),
        "total_at_risk": round(total_at_risk, 2),
        "open_at_risk": round(open_at_risk, 2),
        "recovered_amount": round(recovered_amount, 2),
        "total_audited_spend": total_audited_spend,
        "by_severity": by_severity,
        "by_rule": by_rule,
        "by_status": by_status,
        "batches_count": batches_count,
    }


def ingest_csv_file_to_table(
    conn: sqlite3.Connection,
    path: Path,
    kind: str,
    workspace_id: str = "default",
) -> int:
    """Insert rows from a CSV file into the corresponding SQLite table."""
    table_name = "payments" if kind == "payment_ledger" else kind
    if table_name not in _ALLOWED_COLUMNS:
        raise ValueError(f"unsupported table kind: {kind}")

    records: list[dict] = []
    with path.open("r", encoding="utf-8", errors="replace") as f:
        reader = csv.DictReader(f)
        for row in reader:
            cleaned_row = {
                k.strip(): (v.strip() if isinstance(v, str) else v)
                for k, v in row.items()
                if k is not None
            }
            for num_col in ("quantity", "unit_price", "tax_pct", "line_total", "amount",
                            "contracted_unit_price", "discount_pct", "fx_rate_to_inr",
                            "approval_limit"):
                if num_col in cleaned_row and cleaned_row[num_col]:
                    try:
                        cleaned_row[num_col] = float(cleaned_row[num_col])
                    except (ValueError, TypeError):
                        pass
            records.append(cleaned_row)

    rows_inserted = _insert_table_rows(conn, table_name, records, workspace_id=workspace_id)
    conn.commit()
    return rows_inserted


def seed_sample_dataset(
    conn: sqlite3.Connection,
    sample_dir: Path,
    workspace_id: str = "default",
) -> dict:
    """Populate database from sample_data CSVs and run detection."""
    conn.execute(
        "DELETE FROM decisions WHERE finding_id IN (SELECT finding_id FROM findings WHERE workspace_id = ?)",
        (workspace_id,),
    )
    conn.execute("DELETE FROM findings WHERE workspace_id = ?", (workspace_id,))
    conn.execute("DELETE FROM audit_log WHERE workspace_id = ?", (workspace_id,))
    if workspace_id == "default" and conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name='audit_chain'"
    ).fetchone():
        conn.execute("DELETE FROM audit_chain")
    conn.execute(
        "DELETE FROM batches WHERE kind = 'sample_data_demo' AND workspace_id = ?",
        (workspace_id,),
    )
    conn.commit()

    counts = {}
    for kind in ["vendors", "approvers", "contracts", "purchase_orders",
                 "invoices", "payments", "credit_notes"]:
        csv_file = sample_dir / f"{kind}.csv"
        if csv_file.exists():
            counts[kind] = ingest_csv_file_to_table(
                conn, csv_file, kind, workspace_id=workspace_id
            )

    cur = conn.execute("SELECT COUNT(*) AS n FROM batches")
    batch_id = f"DEMO-{cur.fetchone()['n'] + 1:04d}"
    conn.execute(
        "INSERT INTO batches (batch_id, kind, stored_path, rows_detected, state, workspace_id) "
        "VALUES (?, 'sample_data_demo', 'sample_data/', ?, 'detected', ?)",
        (batch_id, sum(counts.values()), workspace_id),
    )
    _log_audit_event(
        conn,
        actor="demo_seed",
        action="ingest",
        object_type="batch",
        object_id=batch_id,
        detail=f"Seeded sample_data CSVs ({sum(counts.values())} rows)",
        workspace_id=workspace_id,
    )

    detection_res = run_detection(conn, batch_id=batch_id, workspace_id=workspace_id)
    stats = get_stats(conn, workspace_id=workspace_id)

    return {
        "batch_id": batch_id,
        "rows_loaded": counts,
        "findings_created": detection_res["findings_created"],
        "total_at_risk": stats["total_at_risk"],
        "stats": stats,
    }


def build_memo(conn: sqlite3.Connection, workspace_id: str = "default") -> str:
    """Deterministic one-page audit memo (markdown)."""
    findings = [
        dict(r)
        for r in conn.execute(
            "SELECT * FROM findings WHERE workspace_id = ? ORDER BY amount_at_risk DESC",
            (workspace_id,),
        ).fetchall()
    ]

    total_exposure = sum(f["amount_at_risk"] for f in findings)
    total_open_at_risk = sum(f["amount_at_risk"] for f in findings if f["status"] == "open")
    by_rule: dict[str, float] = {}
    for f in findings:
        by_rule[f["rule_id"]] = by_rule.get(f["rule_id"], 0.0) + f["amount_at_risk"]

    lines = [
        "# LedgerLens Audit Memo",
        "",
        "**Executive Spend Exposure Summary**",
        f"- **Total identified exposure:** ₹{total_exposure:,.2f} across {len(findings)} finding(s).",
        f"- **Outstanding / active at risk:** ₹{total_open_at_risk:,.2f}.",
        "- **Pipeline status:** Automated audit verification completed.",
        "",
        "## Exposure by Rule",
    ]
    rule_names = {
        "R1": "Duplicate & Near-Duplicate Invoices",
        "R2": "Contract Price Leakage",
        "R3": "Purchase Order Overbilling",
        "R4": "Currency & Tax Errors",
        "R5": "Cancelled Service Leakage",
        "R6": "Cross-Entity Duplicate & Threshold-Splitting",
        "R7": "Approver-Vendor Collusion",
        "R8": "Contract Lineage & Unapplied Credits",
    }
    for rule_id in sorted(by_rule):
        name = rule_names.get(rule_id, "Rule " + rule_id)
        lines.append(f"- **{rule_id} ({name})** — ₹{by_rule[rule_id]:,.2f} at risk")

    lines += ["", "## Top Actionable Findings"]
    for f in findings:
        lines.append(
            f"- **[{f['severity'].upper()}] {f['finding_id']}** · {f['title']} — "
            f"**{f['amount_at_risk']:,.2f} {f['currency']}** (Status: `{f['status']}`)"
        )
        if f.get("summary"):
            lines.append(f"  > *Evidence summary:* {f['summary']}")

    lines += [
        "",
        "## Recommended Next Actions",
        "1. Block disbursement on high/critical open findings immediately.",
        "2. Forward R1 & R5 evidence packets to vendor management for credit note issuance.",
        "3. Reconcile R2 price variances with procurement contracts team.",
    ]
    return "\n".join(lines)


def build_memo_structured(
    conn: sqlite3.Connection,
    batch_id: str | None = None,
    workspace_id: str = "default",
) -> dict:
    """Return both CFO Markdown memo and structured JSON summary."""
    stats = get_stats(conn, workspace_id=workspace_id)
    rows = [
        dict(r)
        for r in conn.execute(
            "SELECT * FROM findings WHERE workspace_id = ? ORDER BY amount_at_risk DESC",
            (workspace_id,),
        ).fetchall()
    ]

    rule_breakdown: dict[str, dict] = {}
    formatted_findings: list[dict] = []
    for row in rows:
        rid = row["rule_id"]
        bucket = rule_breakdown.setdefault(rid, {"count": 0, "amount_at_risk": 0.0, "currencies": []})
        bucket["count"] += 1
        bucket["amount_at_risk"] = round(bucket["amount_at_risk"] + float(row["amount_at_risk"]), 2)
        if row["currency"] not in bucket["currencies"]:
            bucket["currencies"].append(row["currency"])

        formatted_findings.append({
            "finding_id": row["finding_id"],
            "rule_id": rid,
            "title": row["title"],
            "severity": row["severity"],
            "amount_at_risk": row["amount_at_risk"],
            "currency": row["currency"],
            "status": row["status"],
            "recommended_action": row.get("recommended_action") or "HOLD_PAYMENT",
            "evidence": json.loads(row.get("evidence") or "[]"),
            "entity_refs": json.loads(row.get("entity_refs") or "{}"),
        })

    out = {
        "memo_markdown": build_memo(conn, workspace_id=workspace_id),
        "summary": {
            "total_spend_audited": stats["total_audited_spend"],
            "total_money_at_risk": stats["total_at_risk"],
            "open_at_risk": stats["open_at_risk"],
            "recovered_amount": stats["recovered_amount"],
            "total_findings": stats["total_findings"],
        },
        "by_rule": rule_breakdown,
        "findings": formatted_findings,
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }
    if batch_id:
        out["batch_id"] = batch_id
    return out


def make_workspace_view_conn(
    conn: sqlite3.Connection, workspace_id: str = "default"
) -> sqlite3.Connection:
    """Build an in-memory SQLite connection scoped to ``workspace_id`` for analytics/exports."""
    mem = sqlite3.connect(":memory:")
    mem.row_factory = sqlite3.Row
    mem.executescript(
        """
        CREATE TABLE vendors (
            vendor_id TEXT PRIMARY KEY, vendor_name TEXT, tax_id TEXT,
            default_currency TEXT, status TEXT
        );
        CREATE TABLE invoices (
            invoice_number TEXT, vendor_id TEXT, invoice_date TEXT, po_id TEXT,
            line_no INTEGER, item TEXT, quantity REAL, unit_price REAL,
            currency TEXT, tax_pct REAL, line_total REAL, source_file TEXT,
            status TEXT, workspace_id TEXT
        );
        CREATE TABLE findings (
            finding_id TEXT PRIMARY KEY, rule_id TEXT, title TEXT, severity TEXT,
            amount_at_risk REAL, currency TEXT, status TEXT, entity_refs TEXT,
            evidence TEXT, confidence REAL, summary TEXT, explanation TEXT,
            recommended_action TEXT, proof_trail TEXT, created_at TEXT, workspace_id TEXT
        );
        """
    )
    v_rows = conn.execute(
        "SELECT vendor_id, vendor_name, tax_id, default_currency, status FROM vendors"
    ).fetchall()
    mem.executemany("INSERT INTO vendors VALUES (?, ?, ?, ?, ?)", [tuple(r) for r in v_rows])

    inv_rows = conn.execute(
        "SELECT invoice_number, vendor_id, invoice_date, po_id, line_no, item, quantity, "
        "unit_price, currency, tax_pct, line_total, source_file, status, workspace_id "
        "FROM invoices WHERE workspace_id = ?",
        (workspace_id,),
    ).fetchall()
    mem.executemany(
        "INSERT INTO invoices VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        [tuple(r) for r in inv_rows],
    )

    f_rows = conn.execute(
        "SELECT finding_id, rule_id, title, severity, amount_at_risk, currency, status, "
        "entity_refs, evidence, confidence, summary, explanation, recommended_action, "
        "proof_trail, created_at, workspace_id FROM findings WHERE workspace_id = ?",
        (workspace_id,),
    ).fetchall()
    mem.executemany(
        "INSERT INTO findings VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        [tuple(r) for r in f_rows],
    )
    mem.commit()
    return mem

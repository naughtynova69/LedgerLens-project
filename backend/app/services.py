"""Service layer between the API routes and the deterministic core.

Everything in this module is framework-free (stdlib + app.detect/explain only)
so the full pipeline is unit-testable without installing FastAPI.
"""
from __future__ import annotations

import csv
import json
from pathlib import Path
import sqlite3

from . import config
from .detect import DetectionContext, run_all
from .explain.gemini_explain import fallback_without_gemini


def _rows(conn: sqlite3.Connection, table: str) -> list[dict]:
    return [dict(row) for row in conn.execute(f"SELECT * FROM {table}").fetchall()]


def generate_explanation_for_finding(finding_dict: dict) -> dict:
    """Generate explanation via Gemini if key is configured, else use deterministic fallback."""
    if config.GEMINI_API_KEY:
        try:
            from .explain.gemini_explain import explain_finding
            return explain_finding(finding_dict)
        except Exception:
            pass
    return fallback_without_gemini(finding_dict)


def run_detection(conn: sqlite3.Connection) -> dict:
    """Load normalized tables, run every registered rule, persist findings.

    Returns {"findings_created": int, "finding_ids": [...]}.
    """
    ctx = DetectionContext(
        invoices=_rows(conn, "invoices"),
        payments=_rows(conn, "payments"),
        purchase_orders=_rows(conn, "purchase_orders"),
        contracts=_rows(conn, "contracts"),
        vendors=_rows(conn, "vendors"),
    )
    findings = run_all(ctx)

    existing = conn.execute("SELECT COUNT(*) AS n FROM findings").fetchone()["n"]
    created: list[str] = []
    for offset, finding in enumerate(findings):
        finding_id = f"F-{existing + offset + 1:04d}"
        f_dict = finding.as_dict()
        f_dict["finding_id"] = finding_id
        explanation = generate_explanation_for_finding(f_dict)

        conn.execute(
            """INSERT OR REPLACE INTO findings
               (finding_id, rule_id, title, severity, amount_at_risk, currency,
                status, entity_refs, evidence, confidence, summary, explanation)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                finding_id,
                finding.rule_id,
                finding.title,
                finding.severity,
                finding.amount_at_risk,
                finding.currency,
                "open",
                json.dumps(finding.entity_refs),
                json.dumps([e.as_dict() for e in finding.evidence]),
                finding.confidence,
                finding.summary,
                json.dumps(explanation),
            ),
        )
        created.append(finding_id)
    conn.commit()
    return {"findings_created": len(created), "finding_ids": created}


def record_decision(conn: sqlite3.Connection, finding_id: str, action: str,
                    reviewer: str, note: str = "") -> dict:
    """Apply a reviewer decision, update the finding status, append to audit_log."""
    status_by_action = {
        "approve": "approved",
        "reject": "rejected",
        "request_docs": "open",
        "recovery": "recovery",
    }
    if action not in status_by_action:
        raise ValueError(f"unknown action: {action}")

    row = conn.execute("SELECT finding_id FROM findings WHERE finding_id = ?",
                       (finding_id,)).fetchone()
    if row is None:
        raise LookupError(f"finding not found: {finding_id}")

    conn.execute("UPDATE findings SET status = ? WHERE finding_id = ?",
                 (status_by_action[action], finding_id))
    conn.execute(
        "INSERT INTO decisions (finding_id, action, reviewer, note) VALUES (?, ?, ?, ?)",
        (finding_id, action, reviewer, note),
    )
    conn.execute(
        """INSERT INTO audit_log (actor, action, object_type, object_id, detail)
           VALUES (?, ?, 'finding', ?, ?)""",
        (reviewer, action, finding_id, note),
    )
    conn.commit()
    return {"finding_id": finding_id, "status": status_by_action[action]}


def get_finding_with_sources(conn: sqlite3.Connection, finding_id: str) -> dict | None:
    """Return finding detail including joined source records for the evidence panel."""
    row = conn.execute("SELECT * FROM findings WHERE finding_id = ?", (finding_id,)).fetchone()
    if row is None:
        return None

    finding = dict(row)
    finding["entity_refs"] = json.loads(finding.get("entity_refs") or "{}")
    finding["evidence"] = json.loads(finding.get("evidence") or "[]")
    if finding.get("explanation"):
        try:
            finding["explanation"] = json.loads(finding["explanation"])
        except Exception:
            pass

    # Source records resolution
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
        # Check payments tied to these invoice numbers
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

    # Decisions history
    decisions = [
        dict(r) for r in conn.execute(
            "SELECT * FROM decisions WHERE finding_id = ? ORDER BY id ASC", (finding_id,)
        ).fetchall()
    ]

    finding["source_records"] = source_records
    finding["decisions"] = decisions
    return finding


def get_stats(conn: sqlite3.Connection) -> dict:
    """Return dashboard analytics and spend exposure KPIs."""
    findings = [dict(r) for r in conn.execute("SELECT * FROM findings").fetchall()]
    batches_count = conn.execute("SELECT COUNT(*) AS n FROM batches").fetchone()["n"]

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

    # Invoices total amount
    total_audited_spend = 0.0
    try:
        spend_row = conn.execute("SELECT SUM(line_total) AS s FROM invoices").fetchone()
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


def ingest_csv_file_to_table(conn: sqlite3.Connection, path: Path, kind: str) -> int:
    """Insert rows from a CSV file into the corresponding SQLite table."""
    table_name = "payments" if kind == "payment_ledger" else kind
    rows_inserted = 0

    with path.open("r", encoding="utf-8", errors="replace") as f:
        reader = csv.DictReader(f)
        for row in reader:
            cleaned_row = {k.strip(): (v.strip() if isinstance(v, str) else v) for k, v in row.items()}
            # Cast numeric fields appropriately if present
            for num_col in ("quantity", "unit_price", "tax_pct", "line_total", "amount",
                            "contracted_unit_price", "discount_pct", "fx_rate_to_inr"):
                if num_col in cleaned_row and cleaned_row[num_col]:
                    try:
                        cleaned_row[num_col] = float(cleaned_row[num_col])
                    except (ValueError, TypeError):
                        pass

            cols = list(cleaned_row.keys())
            placeholders = ",".join(["?"] * len(cols))
            conn.execute(
                f"INSERT OR REPLACE INTO {table_name} ({','.join(cols)}) VALUES ({placeholders})",
                list(cleaned_row.values()),
            )
            rows_inserted += 1

    conn.commit()
    return rows_inserted


def seed_sample_dataset(conn: sqlite3.Connection, sample_dir: Path) -> dict:
    """Populate database from sample_data CSVs and run detection."""
    # Reset existing decisions, findings, and demo batches for an idempotent demo
    conn.execute("DELETE FROM decisions")
    conn.execute("DELETE FROM findings")
    conn.execute("DELETE FROM audit_log")
    conn.execute("DELETE FROM batches WHERE kind = 'sample_data_demo'")
    conn.commit()

    counts = {}
    for kind in ["vendors", "contracts", "purchase_orders", "invoices", "payments"]:
        csv_file = sample_dir / f"{kind}.csv"
        if csv_file.exists():
            counts[kind] = ingest_csv_file_to_table(conn, csv_file, kind)

    # Register demo batch
    cur = conn.execute("SELECT COUNT(*) AS n FROM batches")
    batch_id = f"DEMO-{cur.fetchone()['n'] + 1:04d}"
    conn.execute(
        "INSERT INTO batches (batch_id, kind, stored_path, rows_detected, state) "
        "VALUES (?, 'sample_data_demo', 'sample_data/', ?, 'detected')",
        (batch_id, sum(counts.values())),
    )
    conn.commit()

    detection_res = run_detection(conn)
    stats = get_stats(conn)

    return {
        "batch_id": batch_id,
        "rows_loaded": counts,
        "findings_created": detection_res["findings_created"],
        "total_at_risk": stats["total_at_risk"],
        "stats": stats,
    }


def build_memo(conn: sqlite3.Connection) -> str:
    """Deterministic one-page audit memo (markdown)."""
    findings = [dict(r) for r in conn.execute(
        "SELECT * FROM findings ORDER BY amount_at_risk DESC").fetchall()]

    total_exposure = sum(f["amount_at_risk"] for f in findings)
    total_open_at_risk = sum(f["amount_at_risk"] for f in findings
                             if f["status"] in ("open", "approved", "recovery"))
    by_rule: dict[str, float] = {}
    for f in findings:
        by_rule[f["rule_id"]] = by_rule.get(f["rule_id"], 0.0) + f["amount_at_risk"]

    lines = [
        "# LedgerLens Audit Memo",
        "",
        f"**Executive Spend Exposure Summary**",
        f"- **Total identified exposure:** ₹{total_exposure:,.2f} across {len(findings)} finding(s).",
        f"- **Outstanding / active at risk:** ₹{total_open_at_risk:,.2f}.",
        f"- **Pipeline status:** Automated audit verification completed.",
        "",
        "## Exposure by Rule",
    ]
    rule_names = {
        "R1": "Duplicate & Near-Duplicate Invoices",
        "R2": "Contract Price Leakage",
        "R3": "Purchase Order Overbilling",
        "R4": "Currency & Tax Errors",
        "R5": "Cancelled Service Leakage",
    }
    for rule_id in sorted(by_rule):
        name = rule_names.get(rule_id, "Rule " + rule_id)
        lines.append(f"- **{rule_id} ({name})** — ₹{by_rule[rule_id]:,.2f} at risk")

    lines += ["", "## Top Actionable Findings"]
    for f in findings:
        lines.append(
            f"- **[{f['severity'].upper()}] {f['finding_id']}** · {f['title']} — "
            f"**₹{f['amount_at_risk']:,.2f} {f['currency']}** (Status: `{f['status']}`)"
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

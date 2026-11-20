"""BigQuery warehouse sync and FX-normalized executive analytics for LedgerLens."""
from __future__ import annotations

from datetime import datetime, timezone
import json
import os
import sqlite3
from typing import Any

from ..normalize.normalize import REFERENCE_FX_RATES, normalize_currency

_DEFAULT_DATASET = "ledgerlens_analytics"
_RECOVERED_STATUSES = {"rejected", "recovery", "recovered"}
_CORE_RULE_IDS = ("R1", "R2", "R3", "R4", "R5")


def _load_bigquery_sdk() -> Any | None:
    """Lazily import google.cloud.bigquery, returning None if unavailable."""
    try:
        from google.cloud import bigquery  # type: ignore[import-not-found]
    except Exception:
        return None
    return bigquery


def is_bigquery_configured() -> bool:
    """Return True when GCP_PROJECT_ID is set and google.cloud.bigquery is importable."""
    project_id = os.getenv("GCP_PROJECT_ID", "").strip()
    if not project_id:
        return False
    return _load_bigquery_sdk() is not None


def _fx_rate_for(currency: str | None) -> float:
    """Resolve deterministic INR FX multiplier from REFERENCE_FX_RATES."""
    code = normalize_currency(currency or "INR") or "INR"
    return float(REFERENCE_FX_RATES.get(code, 1.0))


def _fetchall_dicts(conn: sqlite3.Connection, query: str) -> list[dict[str, Any]]:
    """Execute query and return rows as plain dicts regardless of connection row_factory."""
    cur = conn.execute(query)
    cols = [col[0] for col in (cur.description or [])]
    return [dict(zip(cols, row)) for row in cur.fetchall()]


def _parse_json_dict(raw: Any) -> dict[str, Any]:
    """Safely parse a JSON string or dict into a dict."""
    if isinstance(raw, dict):
        return raw
    if not raw:
        return {}
    try:
        parsed = json.loads(str(raw))
        return parsed if isinstance(parsed, dict) else {}
    except Exception:
        return {}


def _load_vendor_lookups(
    conn: sqlite3.Connection, invoices: list[dict[str, Any]]
) -> tuple[dict[str, str], dict[str, str]]:
    """Build vendor_id -> vendor_name and invoice_number -> vendor_id lookup maps."""
    vendors_by_id: dict[str, str] = {}
    for row in _fetchall_dicts(conn, "SELECT vendor_id, vendor_name FROM vendors"):
        vid = str(row.get("vendor_id") or "").strip()
        if vid:
            vendors_by_id[vid] = str(row.get("vendor_name") or vid)

    invoice_vendor_by_num: dict[str, str] = {}
    for inv in invoices:
        inv_num = str(inv.get("invoice_number") or "").strip()
        vid = str(inv.get("vendor_id") or "").strip()
        if inv_num and vid and inv_num not in invoice_vendor_by_num:
            invoice_vendor_by_num[inv_num] = vid

    return vendors_by_id, invoice_vendor_by_num


def _resolve_finding_vendor(
    finding: dict[str, Any],
    vendors_by_id: dict[str, str],
    invoice_vendor_by_num: dict[str, str],
) -> tuple[str, str]:
    """Extract (vendor_id, vendor_name) for a finding via entity_refs or linked invoices."""
    refs = _parse_json_dict(finding.get("entity_refs"))
    vendor_id = str(refs.get("vendor_id") or "").strip()

    if not vendor_id:
        inv_nums = refs.get("invoice_numbers") or refs.get("invoice_number") or []
        if isinstance(inv_nums, str):
            inv_nums = [inv_nums]
        if isinstance(inv_nums, list):
            for inv_num in inv_nums:
                candidate = invoice_vendor_by_num.get(str(inv_num).strip(), "")
                if candidate:
                    vendor_id = candidate
                    break

    if not vendor_id:
        vendor_id = "UNKNOWN"

    vendor_name = (
        vendors_by_id.get(vendor_id)
        or str(refs.get("vendor_name") or "").strip()
        or vendor_id
    )
    return vendor_id, vendor_name


def _prepare_sync_payloads(conn: sqlite3.Connection) -> dict[str, list[dict[str, Any]]]:
    """Read SQLite tables and transform rows into BigQuery JSON payloads."""
    synced_at = datetime.now(timezone.utc).isoformat()
    invoices = _fetchall_dicts(conn, "SELECT * FROM invoices")
    findings = _fetchall_dicts(conn, "SELECT * FROM findings")
    audit_log = _fetchall_dicts(conn, "SELECT * FROM audit_log")
    vendors_by_id, invoice_vendor_by_num = _load_vendor_lookups(conn, invoices)

    audited_invoices: list[dict[str, Any]] = []
    for inv in invoices:
        currency = normalize_currency(str(inv.get("currency") or "INR")) or "INR"
        fx_rate = _fx_rate_for(currency)
        line_total = float(inv.get("line_total") or 0.0)
        vendor_id = str(inv.get("vendor_id") or "UNKNOWN")
        audited_invoices.append(
            {
                "invoice_number": str(inv.get("invoice_number") or ""),
                "line_no": int(inv.get("line_no") or 1),
                "vendor_id": vendor_id,
                "vendor_name": vendors_by_id.get(vendor_id, vendor_id),
                "invoice_date": inv.get("invoice_date"),
                "po_id": inv.get("po_id"),
                "item": str(inv.get("item") or ""),
                "quantity": float(inv.get("quantity") or 0.0),
                "unit_price": float(inv.get("unit_price") or 0.0),
                "currency": currency,
                "tax_pct": float(inv.get("tax_pct") or 0.0),
                "line_total": round(line_total, 2),
                "fx_rate_to_inr": fx_rate,
                "line_total_inr": round(line_total * fx_rate, 2),
                "source_file": inv.get("source_file"),
                "status": str(inv.get("status") or "unpaid"),
                "synced_at": synced_at,
            }
        )

    audit_findings: list[dict[str, Any]] = []
    for finding in findings:
        currency = normalize_currency(str(finding.get("currency") or "INR")) or "INR"
        fx_rate = _fx_rate_for(currency)
        amount = float(finding.get("amount_at_risk") or 0.0)
        vendor_id, vendor_name = _resolve_finding_vendor(
            finding, vendors_by_id, invoice_vendor_by_num
        )
        audit_findings.append(
            {
                "finding_id": str(finding.get("finding_id") or ""),
                "rule_id": str(finding.get("rule_id") or ""),
                "title": str(finding.get("title") or ""),
                "severity": str(finding.get("severity") or ""),
                "status": str(finding.get("status") or "open"),
                "amount_at_risk": round(amount, 2),
                "currency": currency,
                "fx_rate_to_inr": fx_rate,
                "amount_at_risk_inr": round(amount * fx_rate, 2),
                "vendor_id": vendor_id,
                "vendor_name": vendor_name,
                "confidence": float(finding.get("confidence") or 0.0),
                "summary": finding.get("summary") or "",
                "recommended_action": finding.get("recommended_action") or "",
                "entity_refs": finding.get("entity_refs") or "{}",
                "evidence": finding.get("evidence") or "[]",
                "explanation": finding.get("explanation"),
                "proof_trail": finding.get("proof_trail") or "{}",
                "created_at": finding.get("created_at"),
                "synced_at": synced_at,
            }
        )

    audit_log_events: list[dict[str, Any]] = []
    for event in audit_log:
        audit_log_events.append(
            {
                "event_id": int(event.get("id") or 0),
                "ts": event.get("ts"),
                "actor": str(event.get("actor") or ""),
                "action": str(event.get("action") or ""),
                "object_type": str(event.get("object_type") or ""),
                "object_id": str(event.get("object_id") or ""),
                "detail": event.get("detail") or "",
                "synced_at": synced_at,
            }
        )

    return {
        "audited_invoices": audited_invoices,
        "audit_findings": audit_findings,
        "audit_log_events": audit_log_events,
    }


def _table_schemas(bq: Any) -> dict[str, tuple[list[Any], list[str]]]:
    """Return BigQuery SchemaField lists and clustering fields for each target table."""
    sf = bq.SchemaField
    return {
        "audited_invoices": (
            [
                sf("invoice_number", "STRING", mode="REQUIRED"),
                sf("line_no", "INT64", mode="REQUIRED"),
                sf("vendor_id", "STRING", mode="REQUIRED"),
                sf("vendor_name", "STRING", mode="NULLABLE"),
                sf("invoice_date", "STRING", mode="NULLABLE"),
                sf("po_id", "STRING", mode="NULLABLE"),
                sf("item", "STRING", mode="REQUIRED"),
                sf("quantity", "FLOAT64", mode="REQUIRED"),
                sf("unit_price", "FLOAT64", mode="REQUIRED"),
                sf("currency", "STRING", mode="REQUIRED"),
                sf("tax_pct", "FLOAT64", mode="REQUIRED"),
                sf("line_total", "FLOAT64", mode="REQUIRED"),
                sf("fx_rate_to_inr", "FLOAT64", mode="REQUIRED"),
                sf("line_total_inr", "FLOAT64", mode="REQUIRED"),
                sf("source_file", "STRING", mode="NULLABLE"),
                sf("status", "STRING", mode="REQUIRED"),
                sf("synced_at", "TIMESTAMP", mode="REQUIRED"),
            ],
            ["vendor_id", "currency"],
        ),
        "audit_findings": (
            [
                sf("finding_id", "STRING", mode="REQUIRED"),
                sf("rule_id", "STRING", mode="REQUIRED"),
                sf("title", "STRING", mode="REQUIRED"),
                sf("severity", "STRING", mode="REQUIRED"),
                sf("status", "STRING", mode="REQUIRED"),
                sf("amount_at_risk", "FLOAT64", mode="REQUIRED"),
                sf("currency", "STRING", mode="REQUIRED"),
                sf("fx_rate_to_inr", "FLOAT64", mode="REQUIRED"),
                sf("amount_at_risk_inr", "FLOAT64", mode="REQUIRED"),
                sf("vendor_id", "STRING", mode="NULLABLE"),
                sf("vendor_name", "STRING", mode="NULLABLE"),
                sf("confidence", "FLOAT64", mode="REQUIRED"),
                sf("summary", "STRING", mode="NULLABLE"),
                sf("recommended_action", "STRING", mode="NULLABLE"),
                sf("entity_refs", "STRING", mode="NULLABLE"),
                sf("evidence", "STRING", mode="NULLABLE"),
                sf("explanation", "STRING", mode="NULLABLE"),
                sf("proof_trail", "STRING", mode="NULLABLE"),
                sf("created_at", "STRING", mode="NULLABLE"),
                sf("synced_at", "TIMESTAMP", mode="REQUIRED"),
            ],
            ["rule_id", "status", "severity"],
        ),
        "audit_log_events": (
            [
                sf("event_id", "INT64", mode="REQUIRED"),
                sf("ts", "STRING", mode="NULLABLE"),
                sf("actor", "STRING", mode="REQUIRED"),
                sf("action", "STRING", mode="REQUIRED"),
                sf("object_type", "STRING", mode="REQUIRED"),
                sf("object_id", "STRING", mode="REQUIRED"),
                sf("detail", "STRING", mode="NULLABLE"),
                sf("synced_at", "TIMESTAMP", mode="REQUIRED"),
            ],
            ["action", "object_type"],
        ),
    }


def _ensure_dataset_and_tables(client: Any, bq: Any, project_id: str, dataset: str) -> None:
    """Create the BigQuery dataset and partitioned/clustered tables if absent."""
    dataset_ref = bq.Dataset(f"{project_id}.{dataset}")
    client.create_dataset(dataset_ref, exists_ok=True)

    for table_name, (schema, clustering_fields) in _table_schemas(bq).items():
        table_ref = bq.Table(f"{project_id}.{dataset}.{table_name}", schema=schema)
        table_ref.time_partitioning = bq.TimePartitioning(
            type_=bq.TimePartitioningType.DAY,
            field="synced_at",
        )
        table_ref.clustering_fields = clustering_fields
        client.create_table(table_ref, exists_ok=True)


def sync_to_bigquery(conn: sqlite3.Connection) -> dict[str, Any]:
    """Sync SQLite audit tables to BigQuery or return a local simulation report."""
    project_id = os.getenv("GCP_PROJECT_ID", "").strip()
    dataset = os.getenv("BQ_DATASET", _DEFAULT_DATASET).strip() or _DEFAULT_DATASET

    payloads = _prepare_sync_payloads(conn)
    table_counts = {name: len(rows) for name, rows in payloads.items()}
    total_rows_prepared = sum(table_counts.values())

    bq = _load_bigquery_sdk() if project_id else None
    if not project_id or bq is None:
        return {
            "mode": "local_simulation",
            "synced": False,
            "project_id": project_id,
            "dataset": dataset,
            "tables": table_counts,
            "total_rows_prepared": total_rows_prepared,
        }

    try:
        client = bq.Client(project=project_id)
        _ensure_dataset_and_tables(client, bq, project_id, dataset)
        schemas = _table_schemas(bq)
        for table_name, rows in payloads.items():
            if not rows:
                continue
            schema, _ = schemas[table_name]
            job_config = bq.LoadJobConfig(
                schema=schema,
                write_disposition=bq.WriteDisposition.WRITE_APPEND,
            )
            table_id = f"{project_id}.{dataset}.{table_name}"
            client.load_table_from_json(rows, table_id, job_config=job_config).result()
    except Exception as exc:
        return {
            "mode": "local_simulation",
            "synced": False,
            "fallback": True,
            "error": str(exc),
            "project_id": project_id,
            "dataset": dataset,
            "tables": table_counts,
            "total_rows_prepared": total_rows_prepared,
        }

    return {
        "mode": "bigquery",
        "synced": True,
        "project_id": project_id,
        "dataset": dataset,
        "tables": table_counts,
        "total_rows_prepared": total_rows_prepared,
        "total_rows_synced": total_rows_prepared,
    }


def compute_executive_analytics(conn: sqlite3.Connection) -> dict[str, Any]:
    """Compute FX-normalized INR KPIs, vendor ranking, and R1-R5 exposure breakdown."""
    invoices = _fetchall_dicts(conn, "SELECT * FROM invoices")
    findings = _fetchall_dicts(conn, "SELECT * FROM findings")
    vendors_by_id, invoice_vendor_by_num = _load_vendor_lookups(conn, invoices)

    total_audited_spend_inr = 0.0
    for inv in invoices:
        fx_rate = _fx_rate_for(inv.get("currency"))
        total_audited_spend_inr += float(inv.get("line_total") or 0.0) * fx_rate

    total_at_risk_inr = 0.0
    open_at_risk_inr = 0.0
    recovered_inr = 0.0

    vendor_stats: dict[str, dict[str, Any]] = {}
    by_rule: dict[str, dict[str, Any]] = {
        rule_id: {
            "count": 0,
            "amount_at_risk_inr": 0.0,
            "open_inr": 0.0,
            "recovered_inr": 0.0,
        }
        for rule_id in _CORE_RULE_IDS
    }

    for finding in findings:
        fx_rate = _fx_rate_for(finding.get("currency"))
        amount_inr = float(finding.get("amount_at_risk") or 0.0) * fx_rate
        status = str(finding.get("status") or "open").strip().lower()
        is_open = status == "open"
        is_recovered = status in _RECOVERED_STATUSES

        total_at_risk_inr += amount_inr
        if is_open:
            open_at_risk_inr += amount_inr
        if is_recovered:
            recovered_inr += amount_inr

        rule_id = str(finding.get("rule_id") or "UNKNOWN").strip() or "UNKNOWN"
        if rule_id not in by_rule:
            by_rule[rule_id] = {
                "count": 0,
                "amount_at_risk_inr": 0.0,
                "open_inr": 0.0,
                "recovered_inr": 0.0,
            }
        rule_bucket = by_rule[rule_id]
        rule_bucket["count"] += 1
        rule_bucket["amount_at_risk_inr"] += amount_inr
        if is_open:
            rule_bucket["open_inr"] += amount_inr
        if is_recovered:
            rule_bucket["recovered_inr"] += amount_inr

        vendor_id, vendor_name = _resolve_finding_vendor(
            finding, vendors_by_id, invoice_vendor_by_num
        )
        if vendor_id not in vendor_stats:
            vendor_stats[vendor_id] = {
                "vendor_id": vendor_id,
                "vendor_name": vendor_name,
                "finding_count": 0,
                "amount_at_risk_inr": 0.0,
                "open_inr": 0.0,
                "recovered_inr": 0.0,
            }
        v_bucket = vendor_stats[vendor_id]
        v_bucket["finding_count"] += 1
        v_bucket["amount_at_risk_inr"] += amount_inr
        if is_open:
            v_bucket["open_inr"] += amount_inr
        if is_recovered:
            v_bucket["recovered_inr"] += amount_inr

    total_audited_spend_inr = round(total_audited_spend_inr, 2)
    total_at_risk_inr = round(total_at_risk_inr, 2)
    open_at_risk_inr = round(open_at_risk_inr, 2)
    recovered_inr = round(recovered_inr, 2)

    leakage_pct_of_spend = (
        round((total_at_risk_inr / total_audited_spend_inr) * 100.0, 2)
        if total_audited_spend_inr > 0
        else 0.0
    )
    recovery_rate_pct = (
        round((recovered_inr / total_at_risk_inr) * 100.0, 2)
        if total_at_risk_inr > 0
        else 0.0
    )

    top_vendors = sorted(
        (
            {
                "vendor_id": v["vendor_id"],
                "vendor_name": v["vendor_name"],
                "finding_count": v["finding_count"],
                "amount_at_risk_inr": round(v["amount_at_risk_inr"], 2),
                "open_inr": round(v["open_inr"], 2),
                "recovered_inr": round(v["recovered_inr"], 2),
            }
            for v in vendor_stats.values()
        ),
        key=lambda item: (-item["amount_at_risk_inr"], item["vendor_id"]),
    )[:10]

    for bucket in by_rule.values():
        bucket["amount_at_risk_inr"] = round(bucket["amount_at_risk_inr"], 2)
        bucket["open_inr"] = round(bucket["open_inr"], 2)
        bucket["recovered_inr"] = round(bucket["recovered_inr"], 2)

    return {
        "total_audited_spend_inr": total_audited_spend_inr,
        "total_at_risk_inr": total_at_risk_inr,
        "open_at_risk_inr": open_at_risk_inr,
        "recovered_inr": recovered_inr,
        "leakage_pct_of_spend": leakage_pct_of_spend,
        "recovery_rate_pct": recovery_rate_pct,
        "total_findings": len(findings),
        "fx_rates": dict(REFERENCE_FX_RATES),
        "top_vendors": top_vendors,
        "by_rule": by_rule,
    }

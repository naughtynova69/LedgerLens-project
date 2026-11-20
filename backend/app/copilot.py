"""Outbound webhook alert dispatcher and grounded CFO Copilot (Track #11)."""
from __future__ import annotations

from datetime import datetime, timezone
import json
import logging
import sqlite3
from typing import Any
import urllib.error
import urllib.request

from .gcp.vertex_ai import create_genai_client, has_live_ai_credentials

logger = logging.getLogger(__name__)

COPILOT_MODEL = "gemini-3.8-vision-flash"

_COPILOT_SYSTEM_PROMPT = """\
You are LedgerLens CFO Copilot. Answer the user's question using ONLY the grounded
findings, summary statistics, and deterministic proof_trail math provided below.
Rules:
- Cite exact finding_id, rule_id, amount_at_risk, currency, and proof_trail values.
- Never invent numbers, IDs, or conclusions not present in the provided context.
- Keep the answer concise, actionable, and suitable for a CFO or audit controller.
"""


def dispatch_webhook_alert(
    webhook_url: str | None,
    event_type: str,
    payload: dict[str, Any],
    timeout: float = 3.0,
) -> dict[str, Any]:
    """Send a JSON webhook alert via stdlib ``urllib.request``.

    Returns a graceful no-op result when ``webhook_url`` is empty.
    """
    url = (webhook_url or "").strip()
    if not url:
        return {"sent": False, "status_code": None, "error": None}

    envelope = {
        "event_type": event_type,
        "payload": payload,
        "ts": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    }
    body = json.dumps(envelope, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            status = getattr(resp, "status", None) or resp.getcode()
            return {
                "sent": bool(status is not None and 200 <= int(status) < 300),
                "status_code": int(status) if status is not None else None,
                "error": None,
            }
    except urllib.error.HTTPError as exc:
        return {"sent": False, "status_code": exc.code, "error": str(exc)}
    except Exception as exc:
        logger.warning("Webhook dispatch to %s failed: %s", url, exc)
        return {"sent": False, "status_code": None, "error": str(exc)}


def _parse_proof_trail(raw: Any) -> dict[str, Any]:
    if isinstance(raw, dict):
        return raw
    if isinstance(raw, str) and raw.strip():
        try:
            parsed = json.loads(raw)
            return parsed if isinstance(parsed, dict) else {"raw": parsed}
        except json.JSONDecodeError:
            return {"raw": raw}
    return {}


def _gather_grounded_context(
    conn: sqlite3.Connection,
    top_n: int = 5,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    has_table = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name='findings'"
    ).fetchone()
    if not has_table:
        return {"total_findings": 0, "open_findings": 0, "total_amount_at_risk": 0.0}, []

    stats_row = conn.execute(
        "SELECT COUNT(*), "
        "SUM(CASE WHEN status = 'open' THEN 1 ELSE 0 END), "
        "COALESCE(SUM(amount_at_risk), 0.0) "
        "FROM findings"
    ).fetchone()
    stats = {
        "total_findings": int(stats_row[0] or 0),
        "open_findings": int(stats_row[1] or 0),
        "total_amount_at_risk": round(float(stats_row[2] or 0.0), 2),
    }

    rows = conn.execute(
        "SELECT finding_id, rule_id, title, severity, amount_at_risk, currency, "
        "status, recommended_action, proof_trail "
        "FROM findings ORDER BY amount_at_risk DESC, finding_id ASC LIMIT ?",
        (top_n,),
    ).fetchall()

    top_findings: list[dict[str, Any]] = []
    for row in rows:
        top_findings.append(
            {
                "finding_id": row[0],
                "rule_id": row[1],
                "title": row[2],
                "severity": row[3],
                "amount_at_risk": float(row[4] or 0.0),
                "currency": row[5] or "INR",
                "status": row[6],
                "recommended_action": row[7] or "",
                "proof_trail": _parse_proof_trail(row[8]),
            }
        )
    return stats, top_findings


def _format_offline_answer(
    question: str,
    workspace_id: str,
    stats: dict[str, Any],
    top_findings: list[dict[str, Any]],
) -> str:
    if not top_findings:
        return (
            f"Workspace '{workspace_id}' currently has 0 findings "
            f"(total_amount_at_risk=0.0). No anomalies to report for: {question}"
        )

    lines = [
        f"Workspace '{workspace_id}' summary: {stats['total_findings']} findings "
        f"({stats['open_findings']} open), total amount_at_risk={stats['total_amount_at_risk']:.2f}.",
        "Top grounded findings:",
    ]
    for f in top_findings:
        proof_json = json.dumps(f["proof_trail"], ensure_ascii=False, sort_keys=True)
        lines.append(
            f"- {f['finding_id']} ({f['rule_id']}, {f['severity']}, {f['status']}): "
            f"amount_at_risk={f['amount_at_risk']:.2f} {f['currency']} | "
            f"proof_trail={proof_json}"
        )
    return "\n".join(lines)


def ask_copilot(
    conn: sqlite3.Connection,
    question: str,
    workspace_id: str = "default",
) -> dict[str, Any]:
    """Answer a CFO question grounded in findings, stats, and ``proof_trail`` math."""
    stats, top_findings = _gather_grounded_context(conn)
    citations = [
        {
            "finding_id": f["finding_id"],
            "rule_id": f["rule_id"],
            "amount_at_risk": f["amount_at_risk"],
            "currency": f["currency"],
            "proof_trail": f["proof_trail"],
        }
        for f in top_findings
    ]

    if has_live_ai_credentials():
        try:
            client = create_genai_client()
            context_payload = {
                "workspace_id": workspace_id,
                "question": question,
                "stats": stats,
                "top_findings": top_findings,
            }
            prompt = (
                f"{_COPILOT_SYSTEM_PROMPT}\n\n"
                f"GROUNDED_CONTEXT:\n{json.dumps(context_payload, ensure_ascii=False)}"
            )
            response = client.models.generate_content(
                model=COPILOT_MODEL,
                contents=[prompt],
            )
            text = (getattr(response, "text", None) or "").strip()
            if text:
                return {
                    "answer": text,
                    "mode": "gemini",
                    "model": COPILOT_MODEL,
                    "workspace_id": workspace_id,
                    "stats": stats,
                    "citations": citations,
                }
        except Exception as exc:
            logger.warning("Gemini Copilot call failed (%s); using deterministic fallback.", exc)

    return {
        "answer": _format_offline_answer(question, workspace_id, stats, top_findings),
        "mode": "deterministic_fallback",
        "model": None,
        "workspace_id": workspace_id,
        "stats": stats,
        "citations": citations,
    }

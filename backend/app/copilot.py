"""Outbound webhook alert dispatcher and grounded CFO Copilot (Track #11)."""
from __future__ import annotations

from datetime import datetime, timezone
import json
import logging
import os
import sqlite3
import time
from typing import Any
import urllib.error
import urllib.request

from .gcp.vertex_ai import create_genai_client, has_live_ai_credentials
from .http_guard import guarded_urlopen

logger = logging.getLogger(__name__)

COPILOT_MODEL = "gemini-3.8-vision-flash"
DEFAULT_HMS_BASE_URL = "https://100milionseek.top/v1"
DEFAULT_HMS_MODEL = "deepseek-v4.1-flash-free"
DEFAULT_OPENAI_BASE_URL = "https://api.openai.com/v1"
DEFAULT_OPENAI_MODEL = "gpt-4o-mini"

_RULE_NAMES: dict[str, str] = {
    "R1": "Duplicate & Near-Duplicate Invoices",
    "R2": "Contract Price Leakage",
    "R3": "Purchase Order Overbilling",
    "R4": "Currency & Tax Errors",
    "R5": "Cancelled Service Leakage",
    "R6": "Cross-Entity Duplicate & Threshold-Splitting",
    "R7": "Approver-Vendor Collusion",
    "R8": "Contract Lineage & Unapplied Credits",
}

_RULE_KEYWORDS: dict[str, tuple[str, ...]] = {
    "R1": ("duplicate", "r1", "double", "same invoice"),
    "R2": ("contract", "price", "rate", "variance", "r2"),
    "R3": ("po", "purchase order", "overbill", "quantity", "qty", "r3"),
    "R4": ("currency", "tax", "gst", "fx", "exchange", "r4"),
    "R5": ("cancel", "terminated", "subscription", "r5"),
    "R6": ("threshold", "split", "cross-entity", "r6"),
    "R7": ("collusion", "approver", "vendor", "r7"),
    "R8": ("credit", "lineage", "r8"),
}

_COPILOT_SYSTEM_PROMPT = """\
You are LedgerLens CFO Copilot. Answer the user's question using ONLY the grounded
findings, summary statistics, rule exposure memo, and deterministic proof_trail math
provided below.
Rules:
- Cite exact finding_id, rule_id, amount_at_risk, currency, and proof_trail values.
- Never invent numbers, IDs, or conclusions not present in the provided context.
- If a selected_finding_id or current_page is provided, prioritize it in your answer.
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
        # SSRF guard: https-only, hostname denylist, public-IP resolution,
        # redirect targets re-validated (see app.http_guard).
        with guarded_urlopen(req, timeout=timeout) as resp:
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


def _format_proof_trail_text(proof_trail: dict[str, Any]) -> str:
    """Render a proof_trail dict as a safe string for UI citations."""
    if not proof_trail:
        return ""
    if list(proof_trail.keys()) == ["raw"]:
        return str(proof_trail["raw"])
    return json.dumps(proof_trail, ensure_ascii=False, sort_keys=True)


def _table_columns(conn: sqlite3.Connection, table_name: str) -> set[str]:
    rows = conn.execute(f"PRAGMA table_info({table_name})").fetchall()
    return {row[1] for row in rows}


def _should_filter_by_workspace(conn: sqlite3.Connection, workspace_id: str) -> bool:
    """Return True when findings should be scoped to ``workspace_id``.

    Strict isolation applies for ``default``, any workspace that owns findings,
    and any registered workspace in ``workspaces``. Legacy/synthetic test DBs
    that insert default-scoped rows and pass an unregistered ad-hoc
    ``workspace_id`` fall back to unfiltered reads.
    """
    cols = _table_columns(conn, "findings")
    if "workspace_id" not in cols:
        return False
    if workspace_id == "default":
        return True
    has_own_findings = conn.execute(
        "SELECT 1 FROM findings WHERE workspace_id = ? LIMIT 1",
        (workspace_id,),
    ).fetchone()
    if has_own_findings:
        return True
    has_workspaces_table = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name='workspaces'"
    ).fetchone()
    if has_workspaces_table:
        registered = conn.execute(
            "SELECT 1 FROM workspaces WHERE workspace_id = ? LIMIT 1",
            (workspace_id,),
        ).fetchone()
        if registered:
            return True
    return False


def _row_to_finding(row: tuple[Any, ...], has_summary: bool) -> dict[str, Any]:
    item = {
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
    if has_summary:
        item["summary"] = row[9] or ""
    return item


def _gather_grounded_context(
    conn: sqlite3.Connection,
    workspace_id: str = "default",
    top_n: int = 5,
    selected_finding_id: str | None = None,
) -> tuple[dict[str, Any], list[dict[str, Any]], dict[str, float]]:
    """Query workspace-scoped stats, top findings, and rule exposure breakdown."""
    has_table = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name='findings'"
    ).fetchone()
    if not has_table:
        return (
            {
                "total_findings": 0,
                "open_findings": 0,
                "total_amount_at_risk": 0.0,
                "open_amount_at_risk": 0.0,
            },
            [],
            {},
        )

    filter_ws = _should_filter_by_workspace(conn, workspace_id)
    where_clause = "WHERE workspace_id = ?" if filter_ws else ""
    params: tuple[Any, ...] = (workspace_id,) if filter_ws else ()

    stats_row = conn.execute(
        "SELECT COUNT(*), "
        "SUM(CASE WHEN status = 'open' THEN 1 ELSE 0 END), "
        "COALESCE(SUM(amount_at_risk), 0.0), "
        "COALESCE(SUM(CASE WHEN status = 'open' THEN amount_at_risk ELSE 0.0 END), 0.0) "
        f"FROM findings {where_clause}",
        params,
    ).fetchone()
    stats = {
        "total_findings": int(stats_row[0] or 0),
        "open_findings": int(stats_row[1] or 0),
        "total_amount_at_risk": round(float(stats_row[2] or 0.0), 2),
        "open_amount_at_risk": round(float(stats_row[3] or 0.0), 2),
    }

    rule_rows = conn.execute(
        f"SELECT rule_id, COALESCE(SUM(amount_at_risk), 0.0) FROM findings {where_clause} "
        "GROUP BY rule_id ORDER BY rule_id ASC",
        params,
    ).fetchall()
    by_rule = {str(r[0]): round(float(r[1] or 0.0), 2) for r in rule_rows if r[0]}

    has_summary = "summary" in _table_columns(conn, "findings")
    select_cols = (
        "finding_id, rule_id, title, severity, amount_at_risk, currency, "
        "status, recommended_action, proof_trail"
        + (", summary" if has_summary else "")
    )

    top_findings: list[dict[str, Any]] = []
    seen_ids: set[str] = set()

    if selected_finding_id:
        sel_where = f"{where_clause} AND finding_id = ?" if where_clause else "WHERE finding_id = ?"
        sel_row = conn.execute(
            f"SELECT {select_cols} FROM findings {sel_where} LIMIT 1",
            (*params, selected_finding_id),
        ).fetchone()
        if sel_row is not None:
            finding = _row_to_finding(sel_row, has_summary)
            top_findings.append(finding)
            seen_ids.add(str(finding["finding_id"]))

    rows = conn.execute(
        f"SELECT {select_cols} FROM findings {where_clause} "
        "ORDER BY amount_at_risk DESC, finding_id ASC LIMIT ?",
        (*params, top_n),
    ).fetchall()

    for row in rows:
        finding = _row_to_finding(row, has_summary)
        fid = str(finding["finding_id"])
        if fid not in seen_ids:
            top_findings.append(finding)
            seen_ids.add(fid)

    return stats, top_findings[:top_n], by_rule


def _prioritize_findings_for_question(
    question: str,
    top_findings: list[dict[str, Any]],
    selected_finding_id: str | None = None,
) -> list[dict[str, Any]]:
    """Order findings so selected or question-matching items appear first."""
    q = (question or "").lower()
    matched_rules = {
        rule_id
        for rule_id, keywords in _RULE_KEYWORDS.items()
        if any(kw in q for kw in keywords)
    }
    want_open = "open" in q
    want_high = any(k in q for k in ("high", "critical", "severe", "urgent"))

    def _score(f: dict[str, Any]) -> tuple[int, float]:
        score = 0
        if selected_finding_id and f.get("finding_id") == selected_finding_id:
            score += 100
        if f.get("rule_id") in matched_rules:
            score += 20
        if want_open and str(f.get("status", "")).lower() == "open":
            score += 10
        if want_high and str(f.get("severity", "")).lower() in ("high", "critical"):
            score += 10
        return (score, float(f.get("amount_at_risk") or 0.0))

    return sorted(top_findings, key=_score, reverse=True)


def _format_offline_answer(
    question: str,
    workspace_id: str,
    stats: dict[str, Any],
    top_findings: list[dict[str, Any]],
    by_rule: dict[str, float] | None = None,
    current_page: str | None = None,
    selected_finding_id: str | None = None,
    conversation_history: list[dict[str, Any]] | None = None,
) -> str:
    """Build a deterministic, CFO-ready grounded answer from workspace findings and memo data."""
    if not top_findings:
        page_note = f" (page: {current_page})" if current_page else ""
        return (
            f"Workspace '{workspace_id}'{page_note} currently has 0 findings "
            f"(total_amount_at_risk=0.0). No anomalies to report for: {question}"
        )

    ordered = _prioritize_findings_for_question(
        question, top_findings, selected_finding_id=selected_finding_id
    )
    lines = [
        f"Workspace '{workspace_id}' summary: {stats['total_findings']} findings "
        f"({stats['open_findings']} open), total amount_at_risk={stats['total_amount_at_risk']:.2f} "
        f"(open amount_at_risk={stats.get('open_amount_at_risk', 0.0):.2f}).",
    ]
    if current_page:
        lines.append(f"Context page: {current_page}.")
    if selected_finding_id and ordered and ordered[0].get("finding_id") == selected_finding_id:
        lines.append(f"Focused finding: {selected_finding_id}.")
    if conversation_history:
        lines.append(f"Follow-up context: {len(conversation_history)} prior message(s) considered.")

    if by_rule:
        rule_parts = [
            f"{rid} ({_RULE_NAMES.get(rid, rid)}): {amt:.2f}"
            for rid, amt in sorted(by_rule.items())
        ]
        lines.append("Exposure by rule: " + "; ".join(rule_parts) + ".")

    lines.append("Top grounded findings:")
    for f in ordered:
        proof_json = json.dumps(f["proof_trail"], ensure_ascii=False, sort_keys=True)
        action = f" | action={f['recommended_action']}" if f.get("recommended_action") else ""
        lines.append(
            f"- {f['finding_id']} ({f['rule_id']}, {f['severity']}, {f['status']}): "
            f"{f['title']} | amount_at_risk={f['amount_at_risk']:.2f} {f['currency']}"
            f"{action} | proof_trail={proof_json}"
        )
    return "\n".join(lines)


def _sanitize_history(
    conversation_history: list[dict[str, Any]] | None,
) -> list[dict[str, str]]:
    if not conversation_history:
        return []
    cleaned: list[dict[str, str]] = []
    for item in conversation_history[-6:]:
        if not isinstance(item, dict):
            continue
        role = str(item.get("role") or "user").strip().lower()
        if role not in ("user", "assistant", "system"):
            role = "user"
        content = str(item.get("content") or "").strip()
        if content:
            cleaned.append({"role": role, "content": content})
    return cleaned


def _resolve_openai_config() -> tuple[str, str, str] | None:
    """Return ``(api_key, base_url, model)`` if an OpenAI-compatible key is configured."""
    hms_key = os.getenv("HMS_API_KEY", "").strip()
    openai_key = os.getenv("COPILOT_OPENAI_API_KEY", "").strip() or os.getenv("OPENAI_API_KEY", "").strip()
    api_key = openai_key or hms_key
    if not api_key:
        return None

    explicit_base = (
        os.getenv("COPILOT_OPENAI_BASE_URL", "").strip()
        or os.getenv("OPENAI_BASE_URL", "").strip()
    )
    if explicit_base:
        base_url = explicit_base.rstrip("/")
    elif hms_key and not openai_key:
        base_url = DEFAULT_HMS_BASE_URL
    else:
        base_url = DEFAULT_OPENAI_BASE_URL

    explicit_model = (
        os.getenv("COPILOT_OPENAI_MODEL", "").strip()
        or os.getenv("OPENAI_MODEL", "").strip()
    )
    if explicit_model:
        model = explicit_model
    elif "100milionseek" in base_url or (hms_key and not openai_key):
        model = DEFAULT_HMS_MODEL
    else:
        model = DEFAULT_OPENAI_MODEL

    return api_key, base_url, model


def _call_openai_compatible(
    context_payload: dict[str, Any],
    history: list[dict[str, str]],
    timeout: float = 10.0,
) -> tuple[str, str] | None:
    """Call an OpenAI-compatible chat completions endpoint with DeepSeek reasoning fallback."""
    cfg = _resolve_openai_config()
    if cfg is None:
        return None
    api_key, base_url, model = cfg
    endpoint = f"{base_url}/chat/completions"

    messages: list[dict[str, str]] = [{"role": "system", "content": _COPILOT_SYSTEM_PROMPT}]
    messages.extend(history)
    messages.append(
        {
            "role": "user",
            "content": f"GROUNDED_CONTEXT:\n{json.dumps(context_payload, ensure_ascii=False)}",
        }
    )

    body = json.dumps(
        {
            "model": model,
            "messages": messages,
            "temperature": 0.1,
        },
        ensure_ascii=False,
    ).encode("utf-8")

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}",
        # Custom UA avoids Cloudflare 1010 blocks on Python's default urllib UA.
        "User-Agent": "LedgerLens-Copilot/1.0",
    }

    for attempt in range(2):
        req = urllib.request.Request(endpoint, data=body, headers=headers, method="POST")
        try:
            with guarded_urlopen(req, timeout=timeout) as resp:
                raw = resp.read().decode("utf-8", errors="replace")
            data = json.loads(raw)
            choices = data.get("choices") or []
            if not choices or not isinstance(choices[0], dict):
                return None
            msg = choices[0].get("message") or {}
            # DeepSeek-style models may return empty `content` and populate `reasoning_content`.
            text = (msg.get("content") or msg.get("reasoning_content") or "").strip()
            if text:
                return text, model
            return None
        except urllib.error.HTTPError as exc:
            if exc.code in (502, 503) and attempt == 0:
                time.sleep(0.3)
                continue
            logger.warning("OpenAI-compatible Copilot HTTP %s failed: %s", exc.code, exc)
            return None
        except Exception as exc:
            logger.warning("OpenAI-compatible Copilot call failed (%s); falling back.", exc)
            return None
    return None


def _extract_gemini_text(response: Any) -> str:
    try:
        return (getattr(response, "text", None) or "").strip()
    except Exception:
        return ""


def ask_copilot(
    conn: sqlite3.Connection,
    question: str,
    workspace_id: str = "default",
    current_page: str | None = None,
    selected_finding_id: str | None = None,
    conversation_history: list[dict[str, Any]] | None = None,
    timeout: float = 10.0,
) -> dict[str, Any]:
    """Answer a CFO question grounded in findings, stats, memo, and ``proof_trail`` math."""
    clean_question = (question or "").strip() or "Summarize current audit exposure and top findings."
    clean_workspace = (workspace_id or "default").strip() or "default"
    history = _sanitize_history(conversation_history)

    stats, top_findings, by_rule = _gather_grounded_context(
        conn,
        workspace_id=clean_workspace,
        selected_finding_id=selected_finding_id,
    )
    citations = [
        {
            "finding_id": f["finding_id"],
            "rule_id": f["rule_id"],
            "amount_at_risk": f["amount_at_risk"],
            "currency": f["currency"],
            "proof_trail": _format_proof_trail_text(f["proof_trail"]),
        }
        for f in top_findings
    ]

    context_payload: dict[str, Any] = {
        "workspace_id": clean_workspace,
        "question": clean_question,
        "stats": stats,
        "by_rule": by_rule,
        "top_findings": top_findings,
    }
    if current_page:
        context_payload["current_page"] = current_page
    if selected_finding_id:
        context_payload["selected_finding_id"] = selected_finding_id
    if history:
        context_payload["conversation_history"] = history

    if has_live_ai_credentials():
        try:
            client = create_genai_client()
            prompt = (
                f"{_COPILOT_SYSTEM_PROMPT}\n\n"
                f"GROUNDED_CONTEXT:\n{json.dumps(context_payload, ensure_ascii=False)}"
            )
            response = client.models.generate_content(
                model=COPILOT_MODEL,
                contents=[prompt],
            )
            text = _extract_gemini_text(response)
            if text:
                return {
                    "answer": text,
                    "mode": "gemini",
                    "model": COPILOT_MODEL,
                    "workspace_id": clean_workspace,
                    "stats": stats,
                    "citations": citations,
                }
        except Exception as exc:
            logger.warning("Gemini Copilot call failed (%s); trying fallback.", exc)

    openai_result = _call_openai_compatible(context_payload, history, timeout=timeout)
    if openai_result is not None:
        answer_text, model_name = openai_result
        return {
            "answer": answer_text,
            "mode": "openai_compatible",
            "model": model_name,
            "workspace_id": clean_workspace,
            "stats": stats,
            "citations": citations,
        }

    return {
        "answer": _format_offline_answer(
            clean_question,
            clean_workspace,
            stats,
            top_findings,
            by_rule=by_rule,
            current_page=current_page,
            selected_finding_id=selected_finding_id,
            conversation_history=history,
        ),
        "mode": "deterministic_fallback",
        "model": None,
        "workspace_id": clean_workspace,
        "stats": stats,
        "citations": citations,
    }

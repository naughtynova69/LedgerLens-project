"""Finance policy settings and bulk decision helpers."""
from __future__ import annotations

import json
import math
import sqlite3
from typing import Any

DEFAULT_POLICY: dict[str, int | float] = {
    "r1_max_amount_drift_pct": 0.5,
    "r1_max_date_gap_days": 30,
    "r4_max_fx_drift_pct": 2.0,
    "auto_hold_threshold_inr": 10000.0,
}

_INT_POLICY_KEYS = frozenset({"r1_max_date_gap_days"})

_STATUS_BY_ACTION: dict[str, str] = {
    "approve": "approved",
    "reject": "rejected",
    "request_docs": "open",
    "recovery": "recovery",
    "recover": "recovery",
}


def ensure_policy_table(conn: sqlite3.Connection) -> None:
    """Create the policy_settings table idempotently if it does not exist."""
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS policy_settings (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL,
            updated_at TEXT DEFAULT (datetime('now'))
        )
        """
    )
    conn.commit()


def _parse_policy_value(key: str, raw: Any) -> int | float:
    """Parse a stored or incoming policy value into the expected numeric type."""
    if raw is None or isinstance(raw, bool):
        raise ValueError(f"invalid value for {key}: {raw!r}")
    try:
        num = float(raw)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"invalid numeric value for {key}: {raw!r}") from exc
    if not math.isfinite(num) or num < 0:
        raise ValueError(f"policy value for {key} must be finite and non-negative: {raw!r}")
    return int(num) if key in _INT_POLICY_KEYS else float(num)


def get_policy(conn: sqlite3.Connection) -> dict[str, int | float]:
    """Return effective policy settings by overlaying stored overrides onto defaults."""
    ensure_policy_table(conn)
    policy: dict[str, int | float] = DEFAULT_POLICY.copy()
    rows = conn.execute("SELECT key, value FROM policy_settings").fetchall()
    for row in rows:
        key, raw_value = row[0], row[1]
        if key in policy:
            policy[key] = _parse_policy_value(key, raw_value)
    return policy


def update_policy(
    conn: sqlite3.Connection,
    updates: dict[str, Any],
    actor: str = "controller",
) -> dict[str, int | float]:
    """Validate and persist policy updates, record an audit log entry, and return the policy."""
    ensure_policy_table(conn)
    if not isinstance(updates, dict):
        raise ValueError("updates must be a dict")

    normalized: dict[str, int | float] = {}
    for key, raw_val in updates.items():
        if key not in DEFAULT_POLICY:
            raise ValueError(f"unknown policy key: {key}")
        normalized[key] = _parse_policy_value(key, raw_val)

    for key, value in normalized.items():
        conn.execute(
            """
            INSERT INTO policy_settings (key, value, updated_at)
            VALUES (?, ?, datetime('now'))
            ON CONFLICT(key) DO UPDATE SET
                value = excluded.value,
                updated_at = datetime('now')
            """,
            (key, str(value)),
        )

    conn.execute(
        """
        INSERT INTO audit_log (actor, action, object_type, object_id, detail)
        VALUES (?, 'policy_update', 'policy', 'global', ?)
        """,
        (actor, json.dumps(normalized, sort_keys=True)),
    )
    conn.commit()
    return get_policy(conn)


def apply_bulk_decision(
    conn: sqlite3.Connection,
    finding_ids: list[str],
    action: str,
    reviewer: str,
    note: str = "",
) -> dict[str, Any]:
    """Apply a reviewer decision across multiple finding IDs, recording errors for missing IDs."""
    if action not in _STATUS_BY_ACTION:
        raise ValueError(f"unknown action: {action}")
    if not finding_ids or not isinstance(finding_ids, (list, tuple)):
        raise ValueError("finding_ids must be a non-empty list")

    target_status = _STATUS_BY_ACTION[action]
    updated: list[str] = []
    errors: list[dict[str, str]] = []

    for finding_id in dict.fromkeys(finding_ids):
        row = conn.execute(
            "SELECT finding_id FROM findings WHERE finding_id = ?",
            (finding_id,),
        ).fetchone()
        if row is None:
            errors.append({"finding_id": finding_id, "error": f"finding not found: {finding_id}"})
            continue

        conn.execute(
            "UPDATE findings SET status = ? WHERE finding_id = ?",
            (target_status, finding_id),
        )
        conn.execute(
            "INSERT INTO decisions (finding_id, action, reviewer, note) VALUES (?, ?, ?, ?)",
            (finding_id, action, reviewer, note),
        )
        conn.execute(
            """
            INSERT INTO audit_log (actor, action, object_type, object_id, detail)
            VALUES (?, ?, 'finding', ?, ?)
            """,
            (reviewer, action, finding_id, note),
        )
        updated.append(finding_id)

    conn.commit()
    return {
        "updated_count": len(updated),
        "updated_ids": updated,
        "status": target_status,
        "errors": errors,
    }

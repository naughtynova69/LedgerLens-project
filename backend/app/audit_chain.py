"""Cryptographic SHA-256 hash-chaining for tamper-evident audit logs."""
from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
from typing import Any, Iterable, Mapping

GENESIS_HASH = "0" * 64

_CREATE_AUDIT_CHAIN_SQL = """
CREATE TABLE IF NOT EXISTS audit_chain (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    ts          TEXT NOT NULL,
    actor       TEXT NOT NULL,
    action      TEXT NOT NULL,
    object_type TEXT NOT NULL,
    object_id   TEXT NOT NULL,
    detail      TEXT NOT NULL DEFAULT '',
    prev_hash   TEXT NOT NULL,
    entry_hash  TEXT NOT NULL
)
"""


def compute_entry_hash(
    prev_hash: str,
    ts: str,
    actor: str,
    action: str,
    object_type: str,
    object_id: str,
    detail: str,
) -> str:
    """Compute a deterministic SHA-256 hex digest for a chained audit entry."""
    canonical = json.dumps(
        [
            prev_hash or GENESIS_HASH,
            str(ts),
            str(actor),
            str(action),
            str(object_type),
            str(object_id),
            str(detail or ""),
        ],
        separators=(",", ":"),
        ensure_ascii=True,
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def ensure_audit_chain_table(conn: Any) -> None:
    """Create the audit_chain table if it does not already exist."""
    conn.execute(_CREATE_AUDIT_CHAIN_SQL)
    conn.commit()


def append_chained_audit_event(
    conn: Any,
    actor: str,
    action: str,
    object_type: str,
    object_id: str,
    detail: str = "",
    ts: str | None = None,
) -> dict[str, Any]:
    """Append a cryptographically chained audit event to ``audit_chain``."""
    ensure_audit_chain_table(conn)
    event_ts = ts or datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    detail_str = str(detail or "")

    last_row = conn.execute(
        "SELECT entry_hash FROM audit_chain ORDER BY id DESC LIMIT 1"
    ).fetchone()
    prev_hash = str(last_row[0]) if last_row else GENESIS_HASH

    entry_hash = compute_entry_hash(
        prev_hash=prev_hash,
        ts=event_ts,
        actor=actor,
        action=action,
        object_type=object_type,
        object_id=object_id,
        detail=detail_str,
    )

    cur = conn.execute(
        "INSERT INTO audit_chain "
        "(ts, actor, action, object_type, object_id, detail, prev_hash, entry_hash) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        (event_ts, actor, action, object_type, object_id, detail_str, prev_hash, entry_hash),
    )
    conn.commit()

    return {
        "id": cur.lastrowid,
        "ts": event_ts,
        "actor": actor,
        "action": action,
        "object_type": object_type,
        "object_id": object_id,
        "detail": detail_str,
        "prev_hash": prev_hash,
        "entry_hash": entry_hash,
    }


def verify_audit_chain(rows: Iterable[Mapping[str, Any] | Any]) -> dict[str, Any]:
    """Verify hash linkage and entry digests across ordered ``audit_chain`` rows."""
    expected_prev = GENESIS_HASH
    checked = 0

    for row in rows:
        checked += 1
        row_id = row["id"]
        if row["prev_hash"] != expected_prev:
            return {"valid": False, "checked": checked, "broken_at_id": row_id}

        expected_hash = compute_entry_hash(
            prev_hash=row["prev_hash"],
            ts=row["ts"],
            actor=row["actor"],
            action=row["action"],
            object_type=row["object_type"],
            object_id=row["object_id"],
            detail=row["detail"],
        )
        if row["entry_hash"] != expected_hash:
            return {"valid": False, "checked": checked, "broken_at_id": row_id}

        expected_prev = row["entry_hash"]

    return {"valid": True, "checked": checked, "broken_at_id": None}

"""Multi-tenant CA / audit firm workspace management and RBAC helpers (Track #9)."""
from __future__ import annotations

from datetime import datetime, timezone
import json
import re
import sqlite3
from typing import Any, Iterable
import uuid

VALID_ROLES: frozenset[str] = frozenset({"analyst", "controller", "auditor", "admin"})

_DEFAULT_ROLE_POLICY = json.dumps(
    {
        "analyst": ["read", "upload", "run_detection"],
        "controller": ["read", "decide", "export"],
        "auditor": ["read", "verify_audit", "export"],
        "admin": ["read", "upload", "run_detection", "decide", "verify_audit", "export", "manage_workspaces"],
    }
)

_CREATE_WORKSPACES_SQL = """
CREATE TABLE IF NOT EXISTS workspaces (
    workspace_id TEXT PRIMARY KEY,
    name         TEXT NOT NULL,
    client_code  TEXT NOT NULL DEFAULT '',
    role_policy  TEXT NOT NULL DEFAULT '{}',
    created_at   TEXT NOT NULL
)
"""


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _slugify(name: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", name.strip().lower()).strip("-")
    return slug or "ws"


def _row_to_dict(row: Any) -> dict[str, Any]:
    return {
        "workspace_id": row[0],
        "name": row[1],
        "client_code": row[2],
        "role_policy": row[3],
        "created_at": row[4],
    }


def ensure_workspaces_table(conn: sqlite3.Connection) -> None:
    """Create the ``workspaces`` table if it does not already exist."""
    conn.execute(_CREATE_WORKSPACES_SQL)
    conn.commit()


def list_workspaces(conn: sqlite3.Connection) -> list[dict[str, Any]]:
    """Return all workspaces, auto-seeding the ``default`` workspace if empty."""
    ensure_workspaces_table(conn)
    rows = conn.execute(
        "SELECT workspace_id, name, client_code, role_policy, created_at "
        "FROM workspaces ORDER BY created_at ASC, workspace_id ASC"
    ).fetchall()

    if not rows:
        now = _utc_now_iso()
        conn.execute(
            "INSERT INTO workspaces (workspace_id, name, client_code, role_policy, created_at) "
            "VALUES (?, ?, ?, ?, ?)",
            ("default", "Default Workspace", "DEFAULT", _DEFAULT_ROLE_POLICY, now),
        )
        conn.commit()
        return [
            {
                "workspace_id": "default",
                "name": "Default Workspace",
                "client_code": "DEFAULT",
                "role_policy": _DEFAULT_ROLE_POLICY,
                "created_at": now,
            }
        ]

    return [_row_to_dict(r) for r in rows]


def create_workspace(
    conn: sqlite3.Connection,
    name: str,
    client_code: str = "",
) -> dict[str, Any]:
    """Create a new tenant workspace and return its record."""
    clean_name = (name or "").strip()
    if not clean_name:
        raise ValueError("Workspace name must not be empty")

    ensure_workspaces_table(conn)
    workspace_id = f"{_slugify(clean_name)}-{uuid.uuid4().hex[:6]}"
    clean_code = (client_code or "").strip().upper()
    now = _utc_now_iso()

    conn.execute(
        "INSERT INTO workspaces (workspace_id, name, client_code, role_policy, created_at) "
        "VALUES (?, ?, ?, ?, ?)",
        (workspace_id, clean_name, clean_code, _DEFAULT_ROLE_POLICY, now),
    )
    conn.commit()

    return {
        "workspace_id": workspace_id,
        "name": clean_name,
        "client_code": clean_code,
        "role_policy": _DEFAULT_ROLE_POLICY,
        "created_at": now,
    }


def require_role(role: str, allowed_roles: Iterable[str]) -> str:
    """Validate that ``role`` is a recognized RBAC role and in ``allowed_roles``.

    Raises ``PermissionError`` when the role is unknown or not permitted.
    """
    norm_role = (role or "").strip().lower()
    allowed = {str(r).strip().lower() for r in allowed_roles}

    if norm_role not in VALID_ROLES:
        raise PermissionError(f"Unknown RBAC role: {role!r}")
    if norm_role not in allowed:
        raise PermissionError(
            f"Role {norm_role!r} is not permitted; requires one of {sorted(allowed)}"
        )
    return norm_role

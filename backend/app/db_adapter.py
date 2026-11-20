"""Unified DB repository helper supporting SQLite and AlloyDB/PostgreSQL dialects."""
from __future__ import annotations

from typing import Any, Sequence

_POSTGRES_DIALECTS = {"postgres", "postgresql", "alloydb"}
_SQLITE_DIALECTS = {"sqlite"}


def _normalize_dialect(dialect: str) -> str:
    norm = (dialect or "sqlite").strip().lower()
    if norm in _SQLITE_DIALECTS:
        return "sqlite"
    if norm in _POSTGRES_DIALECTS:
        return "postgres"
    raise ValueError(f"Unsupported SQL dialect: {dialect!r}")


def _replace_qmarks_outside_literals(sql: str) -> str:
    """Replace SQL ``?`` parameter placeholders with ``%s``, skipping literals/comments."""
    out: list[str] = []
    i = 0
    n = len(sql)
    in_single = False
    in_double = False
    in_line_comment = False

    while i < n:
        ch = sql[i]
        if in_line_comment:
            out.append(ch)
            if ch == "\n":
                in_line_comment = False
            i += 1
            continue

        if in_single:
            out.append(ch)
            if ch == "'":
                if i + 1 < n and sql[i + 1] == "'":
                    out.append(sql[i + 1])
                    i += 2
                    continue
                in_single = False
            i += 1
            continue

        if in_double:
            out.append(ch)
            if ch == '"':
                if i + 1 < n and sql[i + 1] == '"':
                    out.append(sql[i + 1])
                    i += 2
                    continue
                in_double = False
            i += 1
            continue

        if ch == "-" and i + 1 < n and sql[i + 1] == "-":
            in_line_comment = True
            out.append("--")
            i += 2
            continue
        if ch == "'":
            in_single = True
            out.append(ch)
            i += 1
            continue
        if ch == '"':
            in_double = True
            out.append(ch)
            i += 1
            continue
        if ch == "?":
            out.append("%s")
            i += 1
            continue

        out.append(ch)
        i += 1

    return "".join(out)


class DBAdapter:
    """Dialect-aware SQL adaptation and execution helpers for SQLite and Postgres/AlloyDB."""

    @staticmethod
    def adapt_sql(sql: str, dialect: str = "sqlite") -> str:
        """Convert ``?`` placeholders to ``%s`` when targeting Postgres/AlloyDB."""
        target = _normalize_dialect(dialect)
        if target == "sqlite":
            return sql
        return _replace_qmarks_outside_literals(sql)

    @staticmethod
    def upsert_sql(
        table: str,
        columns: Sequence[str],
        conflict_cols: Sequence[str],
        dialect: str = "sqlite",
    ) -> str:
        """Build a dialect-appropriate UPSERT statement."""
        if not columns:
            raise ValueError("columns must not be empty")
        target = _normalize_dialect(dialect)
        col_list = ", ".join(columns)

        if target == "sqlite":
            placeholders = ", ".join("?" for _ in columns)
            return f"INSERT OR REPLACE INTO {table} ({col_list}) VALUES ({placeholders})"

        if not conflict_cols:
            raise ValueError("conflict_cols must not be empty for postgres upsert")
        placeholders = ", ".join("%s" for _ in columns)
        conflict_list = ", ".join(conflict_cols)
        conflict_set = set(conflict_cols)
        update_cols = [c for c in columns if c not in conflict_set]
        if update_cols:
            assignments = ", ".join(f"{c} = EXCLUDED.{c}" for c in update_cols)
            conflict_clause = f"ON CONFLICT ({conflict_list}) DO UPDATE SET {assignments}"
        else:
            conflict_clause = f"ON CONFLICT ({conflict_list}) DO NOTHING"
        return f"INSERT INTO {table} ({col_list}) VALUES ({placeholders}) {conflict_clause}"

    @staticmethod
    def fetchall_dicts(
        conn: Any,
        sql: str,
        params: Sequence[Any] = (),
        dialect: str = "sqlite",
    ) -> list[dict[str, Any]]:
        """Execute a query with dialect-adapted SQL and return rows as dictionaries."""
        adapted = DBAdapter.adapt_sql(sql, dialect)
        cur = conn.cursor()
        try:
            cur.execute(adapted, tuple(params) if params is not None else ())
            rows = cur.fetchall()
            if not rows:
                return []
            first = rows[0]
            if isinstance(first, dict):
                return [dict(r) for r in rows]
            if hasattr(first, "keys"):
                return [{k: r[k] for k in r.keys()} for r in rows]
            cols = [desc[0] for desc in (cur.description or [])]
            return [dict(zip(cols, r)) for r in rows]
        finally:
            if hasattr(cur, "close"):
                cur.close()

    @staticmethod
    def execute(
        conn: Any,
        sql: str,
        params: Sequence[Any] = (),
        dialect: str = "sqlite",
    ) -> Any:
        """Execute a statement with dialect-adapted SQL and return the cursor."""
        adapted = DBAdapter.adapt_sql(sql, dialect)
        cur = conn.cursor()
        cur.execute(adapted, tuple(params) if params is not None else ())
        return cur

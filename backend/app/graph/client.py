"""Thread-safe LadybugDB lifecycle wrapper (docs master-prompt §2.2).

LadybugDB runs in-process — a single on-disk ``.lbdb`` file (or ``:memory:`` in
pytest) per the LadybugDB Get Started guide. No external graph server exists in
this stack, so Cloud Run stays a single container.

Native library resolution: the ``ladybug`` wheel ships the ctypes C-API binding
but not the platform native ``lbug`` shared library. ``scripts/setup_lbug_native.py``
downloads the pinned release binary into ``<repo>/.cache/lbug-prebuilt/lib``; this
module points the binding at it via ``LBUG_C_API_LIB_PATH`` BEFORE the first
``import ladybug`` anywhere in the process.
"""
from __future__ import annotations

import os
import sys
import threading
from pathlib import Path
from typing import Any, Iterator

_REPO_ROOT = Path(__file__).resolve().parents[3]
_NATIVE_LIB_DIR = _REPO_ROOT / ".cache" / "lbug-prebuilt" / "lib"

_NATIVE_NAMES = {
    "win32": ("lbug_shared.dll",),
    "darwin": ("liblbug.dylib", "liblbug.0.dylib"),
}.get(
    sys.platform,
    ("liblbug.so", "liblbug.so.0"),
)


def _ensure_native_library() -> None:
    """Expose the downloaded native lib to the ladybug ctypes binding.

    Must run before the first ``import ladybug`` in the process; harmless if
    the binding later finds the library by itself.
    """
    if os.getenv("LBUG_C_API_LIB_PATH"):
        return
    for name in _NATIVE_NAMES:
        candidate = _NATIVE_LIB_DIR / name
        if candidate.is_file():
            os.environ["LBUG_C_API_LIB_PATH"] = str(candidate)
            return


_ensure_native_library()

import ladybug as lb  # noqa: E402  (import must follow native-lib resolution)

from .. import config  # noqa: E402


class GraphClient:
    """Owns the single ``lb.Database`` for the process.

    Write/projection transactions are serialized with an ``RLock`` while reads
    run on dedicated short-lived ``lb.Connection`` instances concurrently.
    """

    def __init__(self, path: str | None = None, buffer_pool_mb: int | None = None) -> None:
        if path is None:
            path = ":memory:" if _running_under_pytest() else config.GRAPH_PATH
        self.path = path
        self.buffer_pool_mb = int(buffer_pool_mb if buffer_pool_mb is not None else config.GRAPH_BUFFER_POOL_MB)
        pool_bytes = max(0, self.buffer_pool_mb) * 1024 * 1024
        self._db = lb.Database(path, buffer_pool_size=pool_bytes)
        self._write_lock = threading.RLock()

    # -- internals ---------------------------------------------------------

    def _open_connection(self) -> lb.Connection:
        return lb.Connection(self._db)

    @staticmethod
    def _result_to_rows(result: Any) -> list[dict]:
        names = list(result.get_column_names())
        return [dict(zip(names, row)) for row in result.get_all()]

    # -- public API --------------------------------------------------------

    @property
    def is_memory(self) -> bool:
        return self.path == ":memory:"

    def execute_read(self, query: str, parameters: dict | None = None) -> list[dict]:
        """Run a read-only Cypher query; returns rows as plain dicts."""
        conn = self._open_connection()
        try:
            return self._result_to_rows(conn.execute(query, parameters or {}))
        finally:
            conn.close()

    def execute_write(self, query: str, parameters: dict | None = None) -> list[dict]:
        """Run a write Cypher query under the global write lock."""
        with self._write_lock:
            conn = self._open_connection()
            try:
                return self._result_to_rows(conn.execute(query, parameters or {}))
            finally:
                conn.close()

    def write_transaction(self) -> Iterator[GraphClient]:
        """Context manager serializing a multi-statement write transaction.

        The RLock is reentrant, so nested ``execute_write`` calls from the same
        thread inside the transaction do not deadlock.
        """
        return _WriteTransaction(self)

    def health_check(self) -> dict:
        """Deterministic graph engine health probe (never calls the LLM)."""
        try:
            rows = self.execute_read("RETURN 1 AS ok;")
            return {
                "ok": bool(rows and rows[0].get("ok") == 1),
                "engine": "ladybug",
                "mode": "memory" if self.is_memory else "file",
                "path": self.path,
                "buffer_pool_mb": self.buffer_pool_mb,
            }
        except Exception as exc:  # pragma: no cover - defensive
            return {"ok": False, "engine": "ladybug", "error": str(exc)}

    def close(self) -> None:
        try:
            self._db.close()
        except Exception:  # pragma: no cover - defensive
            pass


class _WriteTransaction:
    def __init__(self, client: GraphClient) -> None:
        self._client = client

    def __enter__(self) -> GraphClient:
        self._client._write_lock.acquire()
        return self._client

    def __exit__(self, exc_type, exc, tb) -> None:
        self._client._write_lock.release()


def _running_under_pytest() -> bool:
    return "pytest" in sys.modules


def get_graph_client() -> GraphClient:
    """Build the configured graph client (callers own the lifecycle)."""
    return GraphClient()


_SHARED_CLIENT: GraphClient | None = None
_SHARED_CLIENT_LOCK = threading.Lock()


def get_shared_graph_client() -> GraphClient:
    """Process-wide shared client for API/skill read paths.

    File-backed when configured for production; ``:memory:`` under pytest.
    The write path (detection projection) serializes through the same
    instance's RLock, so shared reads stay consistent.
    """
    global _SHARED_CLIENT
    with _SHARED_CLIENT_LOCK:
        if _SHARED_CLIENT is None:
            _SHARED_CLIENT = get_graph_client()
        return _SHARED_CLIENT

"""Shared probe: is the native LadybugDB library usable in this environment?

The ``ladybug`` wheel imports cleanly everywhere, but ``lb.Database(...)`` only
works once the platform-native ``lbug`` shared library is resolvable (downloaded
by ``backend/scripts/setup_lbug_native.py``). Graph tests skip — with a printed
reason — instead of erroring when the binary is absent (e.g. a sandboxed CI job
without network access).
"""
from __future__ import annotations

import ladybug as lb


def _probe() -> bool:
    try:
        db = lb.Database(":memory:")
        db.close()
        return True
    except Exception:
        return False


NATIVE_GRAPH_AVAILABLE = _probe()
SKIP_REASON = (
    "native LadybugDB library not available — run: python backend/scripts/setup_lbug_native.py"
)

"""Google Cloud Platform integration helpers for LedgerLens."""
from __future__ import annotations

from . import pubsub, vertex_ai
from .pubsub import is_pubsub_configured, publish_recovery_event
from .vertex_ai import (
    create_genai_client,
    has_live_ai_credentials,
    is_vertex_configured,
)

try:
    from . import config_gcp
    from .config_gcp import get_gcp_readiness_status, get_gcp_settings
except ImportError:  # pragma: no cover
    config_gcp = None  # type: ignore[assignment]
    get_gcp_readiness_status = None  # type: ignore[assignment]
    get_gcp_settings = None  # type: ignore[assignment]

try:
    from . import secrets
    from .secrets import is_secret_manager_configured, resolve_secret
except ImportError:  # pragma: no cover
    secrets = None  # type: ignore[assignment]
    is_secret_manager_configured = None  # type: ignore[assignment]
    resolve_secret = None  # type: ignore[assignment]

try:
    from . import alloydb
    from .alloydb import (
        check_alloydb_connection,
        export_sqlite_to_alloydb,
        init_alloydb_schema,
        is_alloydb_configured,
    )
except ImportError:  # pragma: no cover
    alloydb = None  # type: ignore[assignment]
    check_alloydb_connection = None  # type: ignore[assignment]
    export_sqlite_to_alloydb = None  # type: ignore[assignment]
    init_alloydb_schema = None  # type: ignore[assignment]
    is_alloydb_configured = None  # type: ignore[assignment]

try:
    from . import bigquery
    from .bigquery import (
        compute_executive_analytics,
        is_bigquery_configured,
        sync_to_bigquery,
    )
except ImportError:  # pragma: no cover
    bigquery = None  # type: ignore[assignment]
    compute_executive_analytics = None  # type: ignore[assignment]
    is_bigquery_configured = None  # type: ignore[assignment]
    sync_to_bigquery = None  # type: ignore[assignment]

try:
    from . import storage
    from .storage import compute_sha256, is_gcs_configured, store_evidence_object
except ImportError:  # pragma: no cover
    storage = None  # type: ignore[assignment]
    compute_sha256 = None  # type: ignore[assignment]
    is_gcs_configured = None  # type: ignore[assignment]
    store_evidence_object = None  # type: ignore[assignment]

__all__ = [
    "alloydb",
    "bigquery",
    "check_alloydb_connection",
    "compute_executive_analytics",
    "compute_sha256",
    "config_gcp",
    "create_genai_client",
    "export_sqlite_to_alloydb",
    "get_gcp_readiness_status",
    "get_gcp_settings",
    "has_live_ai_credentials",
    "init_alloydb_schema",
    "is_alloydb_configured",
    "is_bigquery_configured",
    "is_gcs_configured",
    "is_pubsub_configured",
    "is_secret_manager_configured",
    "is_vertex_configured",
    "publish_recovery_event",
    "pubsub",
    "resolve_secret",
    "secrets",
    "storage",
    "store_evidence_object",
    "sync_to_bigquery",
    "vertex_ai",
]

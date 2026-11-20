"""Google Cloud Platform configuration and readiness inspection for LedgerLens."""
from __future__ import annotations

import importlib.util
import os
from typing import Any

GCP_PROJECT_ID: str = os.getenv("GCP_PROJECT_ID", "")
GCP_LOCATION: str = os.getenv("GCP_LOCATION", "asia-south1")
DB_BACKEND: str = os.getenv("DB_BACKEND", "sqlite")
ALLOYDB_INSTANCE_URI: str = os.getenv("ALLOYDB_INSTANCE_URI", "")
ALLOYDB_USER: str = os.getenv("ALLOYDB_USER", "postgres")
ALLOYDB_PASS: str = os.getenv("ALLOYDB_PASS", "")
ALLOYDB_DB: str = os.getenv("ALLOYDB_DB", "ledgerlens")
DATABASE_URL: str = os.getenv("DATABASE_URL", "")
BQ_DATASET: str = os.getenv("BQ_DATASET", "ledgerlens_analytics")
GCS_UPLOAD_BUCKET: str = os.getenv("GCS_UPLOAD_BUCKET", "")
USE_VERTEX_AI: bool = os.getenv("USE_VERTEX_AI", "false").lower() in ("1", "true", "yes")
PUBSUB_RECOVERY_TOPIC: str = os.getenv("PUBSUB_RECOVERY_TOPIC", "")
SECRET_MANAGER_PROJECT: str = os.getenv("SECRET_MANAGER_PROJECT", "")


def _parse_bool_env(name: str, default: str = "false") -> bool:
    """Return True when an environment flag is set to a truthy string."""
    return os.getenv(name, default).lower() in ("1", "true", "yes")


def _sdk_installed(module_name: str) -> bool:
    """Safely check whether an optional Python module can be imported."""
    try:
        return importlib.util.find_spec(module_name) is not None
    except (ModuleNotFoundError, ValueError, ImportError):
        return False


def get_gcp_settings() -> dict[str, Any]:
    """Read current GCP settings dynamically from environment variables."""
    return {
        "gcp_project_id": os.getenv("GCP_PROJECT_ID", ""),
        "gcp_location": os.getenv("GCP_LOCATION", "asia-south1"),
        "db_backend": os.getenv("DB_BACKEND", "sqlite"),
        "alloydb_instance_uri": os.getenv("ALLOYDB_INSTANCE_URI", ""),
        "alloydb_user": os.getenv("ALLOYDB_USER", "postgres"),
        "has_alloydb_password": bool(os.getenv("ALLOYDB_PASS", "")),
        "alloydb_db": os.getenv("ALLOYDB_DB", "ledgerlens"),
        "database_url": os.getenv("DATABASE_URL", ""),
        "bq_dataset": os.getenv("BQ_DATASET", "ledgerlens_analytics"),
        "gcs_upload_bucket": os.getenv("GCS_UPLOAD_BUCKET", ""),
        "use_vertex_ai": _parse_bool_env("USE_VERTEX_AI", "false"),
        "pubsub_recovery_topic": os.getenv("PUBSUB_RECOVERY_TOPIC", ""),
        "secret_manager_project": os.getenv("SECRET_MANAGER_PROJECT", ""),
    }


def get_gcp_readiness_status() -> dict[str, Any]:
    """Return per-service GCP configuration and optional SDK readiness status."""
    settings = get_gcp_settings()
    project_id = str(settings["gcp_project_id"])
    location = str(settings["gcp_location"])
    db_backend = str(settings["db_backend"]).lower()
    alloydb_uri = str(settings["alloydb_instance_uri"])
    database_url = str(settings["database_url"])
    bq_dataset = str(settings["bq_dataset"])
    gcs_bucket = str(settings["gcs_upload_bucket"])
    use_vertex_ai = bool(settings["use_vertex_ai"])
    pubsub_topic = str(settings["pubsub_recovery_topic"])
    secret_project = str(settings["secret_manager_project"])

    alloydb_configured = db_backend == "alloydb" and bool(alloydb_uri or database_url)
    bigquery_configured = bool(project_id and bq_dataset)
    storage_configured = bool(gcs_bucket)
    vertex_configured = bool(use_vertex_ai and project_id)
    secret_manager_configured = bool(secret_project)
    pubsub_configured = bool(pubsub_topic)

    alloydb_sdk = _sdk_installed("google.cloud.alloydb.connector") and _sdk_installed("psycopg")
    bigquery_sdk = _sdk_installed("google.cloud.bigquery")
    storage_sdk = _sdk_installed("google.cloud.storage")
    genai_sdk = _sdk_installed("google.genai")
    secretmanager_sdk = _sdk_installed("google.cloud.secretmanager")
    pubsub_sdk = _sdk_installed("google.cloud.pubsub_v1")

    services = {
        "alloydb": {
            "mode": "configured" if alloydb_configured else "local_fallback",
            "sdk_installed": alloydb_sdk,
            "target": alloydb_uri or database_url or "sqlite",
        },
        "bigquery": {
            "mode": "configured" if bigquery_configured else "local_fallback",
            "sdk_installed": bigquery_sdk,
            "target": f"{project_id}.{bq_dataset}" if bigquery_configured else bq_dataset,
        },
        "cloud_storage": {
            "mode": "configured" if storage_configured else "local_fallback",
            "sdk_installed": storage_sdk,
            "target": f"gs://{gcs_bucket}" if storage_configured else "local_uploads",
        },
        "vertex_ai": {
            "mode": "configured" if vertex_configured else "local_fallback",
            "sdk_installed": genai_sdk,
            "target": f"{project_id}/{location}" if vertex_configured else "gemini_api_key",
        },
        "secret_manager": {
            "mode": "configured" if secret_manager_configured else "local_fallback",
            "sdk_installed": secretmanager_sdk,
            "target": secret_project or "env_fallback",
        },
        "pubsub": {
            "mode": "configured" if pubsub_configured else "local_fallback",
            "sdk_installed": pubsub_sdk,
            "target": pubsub_topic or "in_process",
        },
    }

    return {
        "project_id": project_id,
        "location": location,
        "billing_ready": bool(project_id),
        "services": services,
    }

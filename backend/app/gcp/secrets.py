"""Secret resolution via environment variables with optional GCP Secret Manager fallback."""
from __future__ import annotations

import os


def _resolve_secret_manager_project() -> str:
    """Return the Secret Manager project when explicitly set or enabled."""
    secret_project = os.getenv("SECRET_MANAGER_PROJECT", "").strip()
    if secret_project:
        return secret_project
    if os.getenv("USE_SECRET_MANAGER", "false").lower() in ("1", "true", "yes"):
        return os.getenv("GCP_PROJECT_ID", "").strip()
    return ""


def is_secret_manager_configured() -> bool:
    """Return True when Secret Manager project config is explicitly set or enabled."""
    return bool(_resolve_secret_manager_project())


def resolve_secret(secret_id: str, env_var: str, default: str = "") -> str:
    """Resolve a secret from env first, then GCP Secret Manager, else default."""
    env_value = os.getenv(env_var, "")
    if env_value:
        return env_value

    project_id = _resolve_secret_manager_project()
    if project_id:
        try:
            from google.cloud import secretmanager

            client = secretmanager.SecretManagerServiceClient()
            name = f"projects/{project_id}/secrets/{secret_id}/versions/latest"
            response = client.access_secret_version(request={"name": name})
            return response.payload.data.decode("utf-8")
        except Exception:
            pass

    return os.getenv(env_var) or default

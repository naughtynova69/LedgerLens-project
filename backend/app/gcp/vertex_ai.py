"""Vertex AI / google-genai client factory and credential checks."""
from __future__ import annotations

import os

from .. import config

_TRUTHY_VALUES = ("1", "true", "yes")


def is_vertex_configured() -> bool:
    """Return True when Vertex AI mode is enabled and GCP_PROJECT_ID is non-empty."""
    use_vertex = os.getenv("USE_VERTEX_AI", "false").strip().lower() in _TRUTHY_VALUES
    project_id = os.getenv("GCP_PROJECT_ID", "").strip()
    return use_vertex and bool(project_id)


def has_live_ai_credentials() -> bool:
    """Return True when either GEMINI_API_KEY or Vertex AI configuration is present."""
    return bool(config.GEMINI_API_KEY) or is_vertex_configured()


def create_genai_client():
    """Create a lazily-imported google-genai Client with a strict HTTP timeout."""
    if not is_vertex_configured() and not config.GEMINI_API_KEY:
        raise RuntimeError(
            "Neither GEMINI_API_KEY nor USE_VERTEX_AI+GCP_PROJECT_ID is configured."
        )

    from google import genai

    try:
        timeout_ms = max(1000, int(os.getenv("GEMINI_TIMEOUT_MS", "10000")))
    except ValueError:
        timeout_ms = 10000

    kwargs: dict = {}
    if is_vertex_configured():
        project = os.getenv("GCP_PROJECT_ID", "").strip()
        location = os.getenv("GCP_LOCATION", "asia-south1").strip() or "asia-south1"
        kwargs = {"vertexai": True, "project": project, "location": location}
    elif config.GEMINI_API_KEY.startswith("AQ."):
        kwargs = {"vertexai": True, "api_key": config.GEMINI_API_KEY}
    else:
        kwargs = {"api_key": config.GEMINI_API_KEY}

    try:
        return genai.Client(**kwargs, http_options={"timeout": timeout_ms})
    except TypeError:
        return genai.Client(**kwargs)

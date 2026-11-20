"""Google Cloud Storage and local fallback helpers for evidence objects."""

from __future__ import annotations

import hashlib
import logging
import os
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

_CHUNK_SIZE = 65536


def is_gcs_configured() -> bool:
    """Return True when GCS_UPLOAD_BUCKET is configured to a non-empty value."""
    return bool(os.getenv("GCS_UPLOAD_BUCKET", "").strip())


def compute_sha256(path: Path) -> str:
    """Stream a file in 64KB chunks and return its lowercase hex SHA-256 digest."""
    file_path = Path(path)
    digest = hashlib.sha256()
    with file_path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(_CHUNK_SIZE), b""):
            digest.update(chunk)
    return digest.hexdigest()


def store_evidence_object(
    local_path: Path,
    batch_id: str,
    original_name: str,
) -> dict[str, Any]:
    """Store an evidence file in GCS when configured, falling back to local storage."""
    resolved_path = Path(local_path)
    sha256 = compute_sha256(resolved_path)
    size_bytes = resolved_path.stat().st_size
    bucket_name = os.getenv("GCS_UPLOAD_BUCKET", "").strip()
    safe_name = Path(original_name or resolved_path.name).name or resolved_path.name
    blob_name = f"batches/{batch_id}/{safe_name}"

    if bucket_name:
        try:
            from google.cloud import storage

            client = storage.Client()
            bucket = client.bucket(bucket_name)
            blob = bucket.blob(blob_name)
            blob.metadata = {"sha256": sha256, "batch_id": batch_id}
            blob.upload_from_filename(str(resolved_path))
            return {
                "uri": f"gs://{bucket_name}/{blob_name}",
                "sha256": sha256,
                "backend": "gcs",
                "bucket": bucket_name,
                "size_bytes": size_bytes,
            }
        except Exception as exc:
            logger.warning(
                "GCS upload failed for %s; falling back to local storage: %s",
                resolved_path,
                exc,
            )

    return {
        "uri": str(resolved_path),
        "sha256": sha256,
        "backend": "local",
        "bucket": bucket_name,
        "size_bytes": size_bytes,
    }

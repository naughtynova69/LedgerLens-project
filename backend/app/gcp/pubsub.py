"""Cloud Pub/Sub recovery event publisher with local no-op fallback."""
from __future__ import annotations

import json
import logging
import os
from typing import Any

logger = logging.getLogger(__name__)


def _get_recovery_topic() -> str:
    return os.getenv("PUBSUB_RECOVERY_TOPIC", "").strip()


def is_pubsub_configured() -> bool:
    """Return True when PUBSUB_RECOVERY_TOPIC is configured."""
    return bool(_get_recovery_topic())


def publish_recovery_event(event_type: str, payload: dict[str, Any]) -> dict[str, Any]:
    """Publish a recovery event to Cloud Pub/Sub, falling back to local_noop."""
    topic = _get_recovery_topic()
    if not topic:
        return {
            "published": False,
            "mode": "local_noop",
            "topic": topic,
            "event_type": event_type,
        }

    try:
        from google.cloud import pubsub_v1

        publisher = pubsub_v1.PublisherClient()
        if topic.startswith("projects/"):
            topic_path = topic
        else:
            project_id = os.getenv("GCP_PROJECT_ID", "").strip()
            topic_path = publisher.topic_path(project_id, topic) if project_id else topic

        data = json.dumps({"event_type": event_type, "payload": payload}, default=str).encode("utf-8")
        future = publisher.publish(topic_path, data, event_type=event_type)
        message_id = str(future.result())
        return {
            "published": True,
            "mode": "pubsub",
            "topic": topic,
            "event_type": event_type,
            "message_id": message_id,
        }
    except Exception as exc:
        logger.warning(
            "Pub/Sub publish unavailable for event %s on topic %s: %s",
            event_type,
            topic,
            exc,
        )
        return {
            "published": False,
            "mode": "local_noop",
            "topic": topic,
            "event_type": event_type,
        }

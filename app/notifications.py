import os
import json
import logging
import requests
from typing import Any

try:
    from google.cloud import pubsub_v1  # type: ignore
except Exception:  # pragma: no cover - library optional
    pubsub_v1 = None  # type: ignore

logger = logging.getLogger(__name__)
_publisher = None


def _get_publisher():
    global _publisher
    if _publisher is None and pubsub_v1 is not None:
        _publisher = pubsub_v1.PublisherClient()
    return _publisher


def send_notification(message: str, severity: str = "ERROR", **kwargs: Any) -> None:
    """Send a notification via Pub/Sub or webhook if configured."""
    data = {"message": message, "severity": severity}
    data.update(kwargs)

    topic = os.getenv("NOTIFICATION_TOPIC")
    url = os.getenv("NOTIFICATION_URL")

    if topic and pubsub_v1 is not None:
        try:
            publisher = _get_publisher()
            project = os.getenv("GOOGLE_CLOUD_PROJECT") or os.getenv("GCP_PROJECT")
            if "/" in topic:
                topic_path = topic
            else:
                topic_path = publisher.topic_path(project, topic)
            publisher.publish(topic_path, json.dumps(data).encode("utf-8"))
        except Exception as exc:  # pragma: no cover - external
            logger.exception("Failed to publish notification: %s", exc)

    if url:
        try:
            requests.post(url, json=data, timeout=5)
        except Exception as exc:  # pragma: no cover - external
            logger.exception("Failed to post notification: %s", exc)



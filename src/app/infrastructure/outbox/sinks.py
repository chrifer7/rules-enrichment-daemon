import logging

import httpx

from app.application.ports.outbox_sink_port import OutboxSinkPort

logger = logging.getLogger(__name__)


class StructuredLogOutboxSink(OutboxSinkPort):
    def publish(self, event_type: str, payload: dict) -> None:
        logger.info(
            "outbox_event",
            extra={
                "event.action": "outbox_publish",
                "event.category": "message",
                "event.outcome": "success",
                "event.type": event_type,
                "payload": payload,
            },
        )


class WebhookOutboxSink(OutboxSinkPort):
    def __init__(self, webhook_url: str):
        self._webhook_url = webhook_url

    def publish(self, event_type: str, payload: dict) -> None:
        with httpx.Client(timeout=5.0) as client:
            resp = client.post(self._webhook_url, json={"event_type": event_type, "payload": payload})
            resp.raise_for_status()

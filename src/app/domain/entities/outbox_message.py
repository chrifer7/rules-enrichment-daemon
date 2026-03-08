from dataclasses import dataclass
from datetime import datetime
from typing import Any

from app.domain.enums.processing import OutboxStatus


@dataclass(slots=True)
class OutboxMessage:
    message_id: str
    aggregate_type: str
    aggregate_id: str
    event_type: str
    payload_json: dict[str, Any]
    status: OutboxStatus
    created_at: datetime
    published_at: datetime | None

from dataclasses import dataclass
from datetime import datetime
from typing import Any


@dataclass(slots=True)
class DeadLetterItem:
    order_id: str
    correlation_id: str
    reason: str
    payload_json: dict[str, Any]
    created_at: datetime

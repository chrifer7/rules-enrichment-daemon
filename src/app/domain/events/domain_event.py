from dataclasses import dataclass
from datetime import datetime
from typing import Any


@dataclass(slots=True)
class DomainEvent:
    event_type: str
    aggregate_id: str
    payload: dict[str, Any]
    created_at: datetime

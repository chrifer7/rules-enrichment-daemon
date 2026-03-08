from dataclasses import dataclass
from datetime import datetime

from app.domain.enums.processing import ProcessingStatus


@dataclass(slots=True)
class ProcessingAttempt:
    order_id: str
    correlation_id: str
    attempt_number: int
    status: ProcessingStatus
    started_at: datetime
    finished_at: datetime | None
    error_message: str | None

from sqlalchemy import desc, func, select
from sqlalchemy.orm import Session

from app.application.ports.processing_attempt_repository import ProcessingAttemptRepository
from app.domain.entities.processing_attempt import ProcessingAttempt
from app.infrastructure.db.models import ProcessingAttemptModel


class SqlAlchemyProcessingAttemptRepository(ProcessingAttemptRepository):
    def __init__(self, session: Session):
        self._session = session

    def get_next_attempt_number(self, order_id: str) -> int:
        stmt = select(func.max(ProcessingAttemptModel.attempt_number)).where(ProcessingAttemptModel.order_id == order_id)
        current = self._session.scalar(stmt)
        return int(current) + 1 if current else 1

    def save(self, attempt: ProcessingAttempt) -> None:
        self._session.add(
            ProcessingAttemptModel(
                order_id=attempt.order_id,
                correlation_id=attempt.correlation_id,
                attempt_number=attempt.attempt_number,
                status=attempt.status.value,
                started_at=attempt.started_at,
                finished_at=attempt.finished_at,
                error_message=attempt.error_message,
            )
        )

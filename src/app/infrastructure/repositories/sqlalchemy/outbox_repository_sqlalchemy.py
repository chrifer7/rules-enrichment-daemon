from datetime import datetime, timezone

from sqlalchemy import asc, select
from sqlalchemy.orm import Session

from app.application.ports.outbox_repository import OutboxRepository
from app.domain.entities.outbox_message import OutboxMessage
from app.domain.enums.processing import OutboxStatus
from app.infrastructure.db.models import OutboxMessageModel
from app.infrastructure.repositories.mappers import to_outbox


class SqlAlchemyOutboxRepository(OutboxRepository):
    def __init__(self, session: Session):
        self._session = session

    def enqueue(self, message: OutboxMessage) -> None:
        self._session.add(
            OutboxMessageModel(
                message_id=message.message_id,
                aggregate_type=message.aggregate_type,
                aggregate_id=message.aggregate_id,
                event_type=message.event_type,
                payload_json=message.payload_json,
                status=message.status.value,
                created_at=message.created_at,
                published_at=message.published_at,
            )
        )

    def list_pending(self, limit: int) -> list[OutboxMessage]:
        stmt = (
            select(OutboxMessageModel)
            .where(OutboxMessageModel.status == OutboxStatus.PENDING.value)
            .order_by(asc(OutboxMessageModel.created_at))
            .limit(limit)
        )
        return [to_outbox(model) for model in self._session.scalars(stmt).all()]

    def mark_published(self, message_id: str) -> None:
        model = self._session.get(OutboxMessageModel, message_id)
        if model:
            model.status = OutboxStatus.PUBLISHED.value
            model.published_at = datetime.now(tz=timezone.utc)

    def mark_failed(self, message_id: str) -> None:
        model = self._session.get(OutboxMessageModel, message_id)
        if model:
            model.status = OutboxStatus.FAILED.value

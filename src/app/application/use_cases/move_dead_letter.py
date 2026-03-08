from datetime import datetime

from app.application.ports.unit_of_work import UnitOfWork
from app.domain.entities.dead_letter_item import DeadLetterItem
from app.domain.entities.outbox_message import OutboxMessage
from app.domain.enums.processing import OutboxStatus


class MoveOrderToDeadLetterUseCase:
    def __init__(self, uow: UnitOfWork):
        self._uow = uow

    def execute(self, *, order_id: str, correlation_id: str, reason: str, payload: dict, now: datetime) -> None:
        with self._uow:
            self._uow.dead_letter.save(
                DeadLetterItem(
                    order_id=order_id,
                    correlation_id=correlation_id,
                    reason=reason,
                    payload_json=payload,
                    created_at=now,
                )
            )
            self._uow.outbox.enqueue(
                OutboxMessage(
                    message_id=f"outbox-dead-letter-{correlation_id}",
                    aggregate_type="Order",
                    aggregate_id=order_id,
                    event_type="OrderMovedToDeadLetter",
                    payload_json={"reason": reason, **payload},
                    status=OutboxStatus.PENDING,
                    created_at=now,
                    published_at=None,
                )
            )
            self._uow.commit()

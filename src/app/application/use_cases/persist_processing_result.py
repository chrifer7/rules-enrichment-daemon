from datetime import datetime

from app.application.ports.unit_of_work import UnitOfWork
from app.domain.entities.outbox_message import OutboxMessage
from app.domain.entities.processed_order import ProcessedOrder
from app.domain.enums.processing import OutboxStatus, ProcessingStatus


class PersistProcessingResultUseCase:
    def __init__(self, uow: UnitOfWork):
        self._uow = uow

    def execute(
        self,
        *,
        order_id: str,
        correlation_id: str,
        attempt_number: int,
        enrichment_hash: str,
        success: bool,
        now: datetime,
        event_payload: dict,
    ) -> None:
        with self._uow:
            status = ProcessingStatus.SUCCESS if success else ProcessingStatus.FAILED
            self._uow.attempts.save(
                attempt=self._build_attempt(
                    order_id=order_id,
                    correlation_id=correlation_id,
                    attempt_number=attempt_number,
                    status=status,
                    now=now,
                    error_message=None if success else "processing failed",
                )
            )
            if success:
                self._uow.processed_orders.save(
                    ProcessedOrder(
                        order_id=order_id,
                        enrichment_hash=enrichment_hash,
                        processed_at=now,
                        correlation_id=correlation_id,
                    )
                )

            self._uow.outbox.enqueue(
                OutboxMessage(
                    message_id=f"outbox-{correlation_id}-{order_id}",
                    aggregate_type="Order",
                    aggregate_id=order_id,
                    event_type="OrderEnrichmentSucceeded" if success else "OrderEnrichmentFailed",
                    payload_json=event_payload,
                    status=OutboxStatus.PENDING,
                    created_at=now,
                    published_at=None,
                )
            )
            self._uow.commit()

    @staticmethod
    def _build_attempt(*, order_id: str, correlation_id: str, attempt_number: int, status, now, error_message):
        from app.domain.entities.processing_attempt import ProcessingAttempt

        return ProcessingAttempt(
            order_id=order_id,
            correlation_id=correlation_id,
            attempt_number=attempt_number,
            status=status,
            started_at=now,
            finished_at=now,
            error_message=error_message,
        )

from abc import ABC, abstractmethod

from app.application.ports.dead_letter_repository import DeadLetterRepository
from app.application.ports.outbox_repository import OutboxRepository
from app.application.ports.processing_attempt_repository import ProcessingAttemptRepository
from app.application.ports.processed_order_repository import ProcessedOrderRepository
from app.application.ports.rule_repository import EnrichmentRuleRepository


class UnitOfWork(ABC):
    rules: EnrichmentRuleRepository
    attempts: ProcessingAttemptRepository
    processed_orders: ProcessedOrderRepository
    outbox: OutboxRepository
    dead_letter: DeadLetterRepository

    @abstractmethod
    def __enter__(self) -> "UnitOfWork":
        raise NotImplementedError

    @abstractmethod
    def __exit__(self, exc_type, exc_value, traceback) -> None:
        raise NotImplementedError

    @abstractmethod
    def commit(self) -> None:
        raise NotImplementedError

    @abstractmethod
    def rollback(self) -> None:
        raise NotImplementedError

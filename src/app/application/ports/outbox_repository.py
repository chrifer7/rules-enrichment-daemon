from abc import ABC, abstractmethod

from app.domain.entities.outbox_message import OutboxMessage


class OutboxRepository(ABC):
    @abstractmethod
    def enqueue(self, message: OutboxMessage) -> None:
        raise NotImplementedError

    @abstractmethod
    def list_pending(self, limit: int) -> list[OutboxMessage]:
        raise NotImplementedError

    @abstractmethod
    def mark_published(self, message_id: str) -> None:
        raise NotImplementedError

    @abstractmethod
    def mark_failed(self, message_id: str) -> None:
        raise NotImplementedError

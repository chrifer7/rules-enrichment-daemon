from abc import ABC, abstractmethod

from app.domain.entities.processing_attempt import ProcessingAttempt


class ProcessingAttemptRepository(ABC):
    @abstractmethod
    def get_next_attempt_number(self, order_id: str) -> int:
        raise NotImplementedError

    @abstractmethod
    def save(self, attempt: ProcessingAttempt) -> None:
        raise NotImplementedError

from abc import ABC, abstractmethod

from app.domain.entities.dead_letter_item import DeadLetterItem


class DeadLetterRepository(ABC):
    @abstractmethod
    def save(self, item: DeadLetterItem) -> None:
        raise NotImplementedError

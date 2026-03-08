from abc import ABC, abstractmethod

from app.domain.entities.external_order import ExternalOrder


class Specification(ABC):
    @abstractmethod
    def is_satisfied_by(self, order: ExternalOrder) -> bool:
        raise NotImplementedError

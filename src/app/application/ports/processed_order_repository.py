from abc import ABC, abstractmethod

from app.domain.entities.processed_order import ProcessedOrder


class ProcessedOrderRepository(ABC):
    @abstractmethod
    def get_by_order_id(self, order_id: str) -> ProcessedOrder | None:
        raise NotImplementedError

    @abstractmethod
    def save(self, processed: ProcessedOrder) -> None:
        raise NotImplementedError

from abc import ABC, abstractmethod
from datetime import datetime
from typing import Any

from app.domain.entities.external_order import ExternalOrder


class ExternalWmsPort(ABC):
    @abstractmethod
    def health_check(self) -> bool:
        raise NotImplementedError

    @abstractmethod
    def get_orders_for_enrichment(self, *, updated_since: datetime | None, limit: int) -> list[ExternalOrder]:
        raise NotImplementedError

    @abstractmethod
    def get_order_by_id(self, order_id: str) -> ExternalOrder:
        raise NotImplementedError

    @abstractmethod
    def submit_enrichment(self, order_id: str, payload: dict[str, Any], correlation_id: str) -> None:
        raise NotImplementedError

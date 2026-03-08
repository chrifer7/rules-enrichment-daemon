from sqlalchemy import select
from sqlalchemy.orm import Session

from app.application.ports.processed_order_repository import ProcessedOrderRepository
from app.domain.entities.processed_order import ProcessedOrder
from app.infrastructure.db.models import ProcessedOrderModel
from app.infrastructure.repositories.mappers import to_processed


class SqlAlchemyProcessedOrderRepository(ProcessedOrderRepository):
    def __init__(self, session: Session):
        self._session = session

    def get_by_order_id(self, order_id: str) -> ProcessedOrder | None:
        model = self._session.get(ProcessedOrderModel, order_id)
        return to_processed(model) if model else None

    def save(self, processed: ProcessedOrder) -> None:
        model = self._session.get(ProcessedOrderModel, processed.order_id)
        if model is None:
            model = ProcessedOrderModel(order_id=processed.order_id)
            self._session.add(model)
        model.enrichment_hash = processed.enrichment_hash
        model.processed_at = processed.processed_at
        model.correlation_id = processed.correlation_id

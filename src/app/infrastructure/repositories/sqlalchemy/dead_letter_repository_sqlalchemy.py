from sqlalchemy.orm import Session

from app.application.ports.dead_letter_repository import DeadLetterRepository
from app.domain.entities.dead_letter_item import DeadLetterItem
from app.infrastructure.db.models import DeadLetterItemModel


class SqlAlchemyDeadLetterRepository(DeadLetterRepository):
    def __init__(self, session: Session):
        self._session = session

    def save(self, item: DeadLetterItem) -> None:
        self._session.add(
            DeadLetterItemModel(
                order_id=item.order_id,
                correlation_id=item.correlation_id,
                reason=item.reason,
                payload_json=item.payload_json,
                created_at=item.created_at,
            )
        )

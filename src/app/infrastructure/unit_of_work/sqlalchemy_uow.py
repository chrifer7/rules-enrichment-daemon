from collections.abc import Callable

from sqlalchemy.orm import Session

from app.application.ports.unit_of_work import UnitOfWork
from app.infrastructure.repositories.sqlalchemy.dead_letter_repository_sqlalchemy import SqlAlchemyDeadLetterRepository
from app.infrastructure.repositories.sqlalchemy.outbox_repository_sqlalchemy import SqlAlchemyOutboxRepository
from app.infrastructure.repositories.sqlalchemy.processing_attempt_repository_sqlalchemy import (
    SqlAlchemyProcessingAttemptRepository,
)
from app.infrastructure.repositories.sqlalchemy.processed_order_repository_sqlalchemy import (
    SqlAlchemyProcessedOrderRepository,
)
from app.infrastructure.repositories.sqlalchemy.rule_repository_sqlalchemy import SqlAlchemyEnrichmentRuleRepository


class SqlAlchemyUnitOfWork(UnitOfWork):
    # Unit of Work is a transaction boundary pattern:
    # several repositories share one SQLAlchemy session so a business operation
    # can commit or roll back all of its database changes together.
    def __init__(self, session_factory: Callable[[], Session]):
        self._session_factory = session_factory
        self.session: Session | None = None

    def __enter__(self):
        # Every repository receives the same session instance, which means they are all
        # participating in the same database transaction.
        self.session = self._session_factory()
        self.rules = SqlAlchemyEnrichmentRuleRepository(self.session)
        self.attempts = SqlAlchemyProcessingAttemptRepository(self.session)
        self.processed_orders = SqlAlchemyProcessedOrderRepository(self.session)
        self.outbox = SqlAlchemyOutboxRepository(self.session)
        self.dead_letter = SqlAlchemyDeadLetterRepository(self.session)
        return self

    def __exit__(self, exc_type, exc_value, traceback) -> None:
        if self.session is None:
            return
        if exc_type:
            # If any exception escapes the business code, revert the transaction.
            self.rollback()
        self.session.close()

    def commit(self) -> None:
        assert self.session is not None
        self.session.commit()

    def rollback(self) -> None:
        assert self.session is not None
        self.session.rollback()

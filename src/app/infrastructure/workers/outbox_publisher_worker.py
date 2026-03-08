import logging
import time

from app.application.commands.publish_outbox import OutboxPublishCommand
from app.application.use_cases.publish_outbox import PublishOutboxMessagesUseCase

logger = logging.getLogger(__name__)


class OutboxPublisherWorker:
    def __init__(self, use_case: PublishOutboxMessagesUseCase, interval_seconds: int):
        self._use_case = use_case
        self._interval_seconds = interval_seconds
        self._running = False

    def run_forever(self) -> None:
        self._running = True
        while self._running:
            published = self._use_case.execute(OutboxPublishCommand(batch_size=100))
            logger.info(
                "outbox_publish_cycle",
                extra={
                    "event.action": "outbox_publish_cycle",
                    "event.category": "process",
                    "event.outcome": "success",
                    "outbox.published": published,
                },
            )
            time.sleep(self._interval_seconds)

    def run_once(self) -> int:
        return self._use_case.execute(OutboxPublishCommand(batch_size=100))

    def stop(self) -> None:
        self._running = False

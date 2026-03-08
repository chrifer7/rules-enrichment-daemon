import logging
import time
from datetime import datetime

from app.application.facades.enrichment_facade import EnrichmentFacade

logger = logging.getLogger(__name__)


class PollingWorker:
    def __init__(self, facade: EnrichmentFacade, poll_interval_seconds: int):
        self._facade = facade
        self._poll_interval_seconds = poll_interval_seconds
        self._running = False
        self._updated_since: datetime | None = None

    def run_forever(self) -> None:
        self._running = True
        while self._running:
            _, _, _, updated_since = self._facade.run_once(updated_since=self._updated_since)
            self._updated_since = updated_since
            time.sleep(self._poll_interval_seconds)

    def run_once(self) -> tuple[int, int, int]:
        fetched, success, failed, updated = self._facade.run_once(updated_since=self._updated_since)
        self._updated_since = updated
        return fetched, success, failed

    def stop(self) -> None:
        self._running = False

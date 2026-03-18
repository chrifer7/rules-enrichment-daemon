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
        # This cursor only lives in process memory.
        # For the PoC that is enough, but after a pod restart the daemon starts polling again
        # from a fresh cursor because nothing durable is storing this value.
        self._updated_since: datetime | None = None

    def run_forever(self) -> None:
        self._running = True
        while self._running:
            _, _, _, updated_since = self._facade.run_once(updated_since=self._updated_since)
            self._updated_since = updated_since
            time.sleep(self._poll_interval_seconds)

    def run_once(self) -> tuple[int, int, int]:
        # `run_once()` is useful for tests and for the higher-level daemon loop.
        # It shares the same cursor logic as `run_forever()` without owning the outer loop.
        fetched, success, failed, updated = self._facade.run_once(updated_since=self._updated_since)
        self._updated_since = updated
        return fetched, success, failed

    def stop(self) -> None:
        self._running = False

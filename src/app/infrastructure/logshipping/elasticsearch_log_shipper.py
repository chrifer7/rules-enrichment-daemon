import json
import logging
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import httpx

from app.config.settings import Settings

logger = logging.getLogger(__name__)


class ElasticsearchLogShipper:
    def __init__(self, settings: Settings):
        self._settings = settings
        self._log_path = Path(settings.log_file_path)
        # Keep the last byte offset in memory so each loop only reads newly appended lines.
        self._offset = 0

    def run_forever(self) -> None:
        logger.info("log_shipper_start", extra={"event.action": "log_shipper_start", "event.category": "process"})
        while True:
            try:
                events = self._read_new_events()
                if events:
                    self._ship(events)
            except Exception:
                logger.exception(
                    "log_shipper_iteration_failed",
                    extra={"event.action": "log_shipper_iteration", "event.category": "process", "event.outcome": "failure"},
                )
            time.sleep(self._settings.log_shipper_flush_interval_seconds)

    def _read_new_events(self) -> list[dict[str, Any]]:
        if not self._log_path.exists():
            return []

        current_size = self._log_path.stat().st_size
        if current_size < self._offset:
            # File was truncated or recreated; restart tailing from the beginning.
            self._offset = 0

        events: list[dict[str, Any]] = []
        with self._log_path.open("r", encoding="utf-8") as handle:
            # Resume from the last processed byte instead of rereading the whole file.
            handle.seek(self._offset)
            for raw_line in handle:
                line = raw_line.strip()
                if not line:
                    continue
                events.append(self._parse_line(line))
            self._offset = handle.tell()
        return events

    def _parse_line(self, line: str) -> dict[str, Any]:
        try:
            event = json.loads(line)
            if not isinstance(event, dict):
                raise ValueError("Expected JSON object.")
        except Exception:
            # The daemon normally writes ECS JSON, but this fallback keeps the shipper
            # resilient if a plain-text line ever appears in the file.
            event = {"message": line}

        event.setdefault("@timestamp", datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"))
        service = event.get("service")
        if not isinstance(service, dict):
            service = {}
            event["service"] = service
        service.setdefault("name", self._settings.app_name)
        event.setdefault("event", {})
        return event

    def _ship(self, events: list[dict[str, Any]]) -> None:
        endpoint = self._settings.log_shipper_elasticsearch_url.rstrip("/")
        auth = (self._settings.log_shipper_elasticsearch_username, self._settings.log_shipper_elasticsearch_password)
        payload = self._build_bulk_payload(events)

        with httpx.Client(timeout=self._settings.external_api_timeout_seconds) as client:
            # `_bulk` is much cheaper than sending one HTTP request per log event.
            response = client.post(
                f"{endpoint}/_bulk",
                content=payload,
                headers={"Content-Type": "application/x-ndjson"},
                auth=auth,
            )
            response.raise_for_status()

            body = response.json()
            if body.get("errors"):
                logger.warning(
                    "log_shipper_bulk_partial_failure",
                    extra={
                        "event.action": "log_shipper_bulk",
                        "event.category": "process",
                        "event.outcome": "failure",
                        "error.message": json.dumps(body)[:2000],
                    },
                )
            else:
                logger.info(
                    "log_shipper_bulk_success",
                    extra={
                        "event.action": "log_shipper_bulk",
                        "event.category": "process",
                        "event.outcome": "success",
                        "log_shipper.batch_size": len(events),
                    },
                )

    def _build_bulk_payload(self, events: list[dict[str, Any]]) -> str:
        lines: list[str] = []
        for event in events:
            index_name = self._resolve_index_name(event)
            lines.append(json.dumps({"index": {"_index": index_name}}, separators=(",", ":")))
            lines.append(json.dumps(event, separators=(",", ":")))
        return "\n".join(lines) + "\n"

    def _resolve_index_name(self, event: dict[str, Any]) -> str:
        timestamp = str(event.get("@timestamp", ""))
        date_portion = timestamp[:10] if len(timestamp) >= 10 else datetime.now(timezone.utc).strftime("%Y-%m-%d")
        normalized_date = date_portion.replace("-", ".")
        return f"{self._settings.log_shipper_index_prefix}-{normalized_date}"

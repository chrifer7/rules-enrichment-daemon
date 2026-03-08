from dataclasses import dataclass
from datetime import datetime
from typing import Any


@dataclass(slots=True)
class EnrichmentPayloadDTO:
    correlation_id: str
    source_system: str
    enrichment_version: int
    applied_rules: list[dict[str, str]]
    enriched_fields: dict[str, Any]


@dataclass(slots=True)
class PollResultDTO:
    run_id: str
    fetched_orders: int
    processed_orders: int
    failed_orders: int
    started_at: datetime
    finished_at: datetime

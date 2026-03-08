from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any


@dataclass(slots=True)
class EnrichmentRule:
    rule_id: str
    facility_code: str | None
    client_code: str | None
    zone_code: str | None
    rule_type: str
    priority: int
    is_active: bool
    conditions_json: dict[str, Any]
    enrichment_json: dict[str, Any]
    valid_from: datetime | None
    valid_to: datetime | None

    def is_valid_at(self, now: datetime) -> bool:
        now_utc = _as_utc(now)
        valid_from_utc = _as_utc(self.valid_from)
        valid_to_utc = _as_utc(self.valid_to)

        if valid_from_utc and now_utc < valid_from_utc:
            return False
        if valid_to_utc and now_utc > valid_to_utc:
            return False
        return self.is_active


def _as_utc(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)

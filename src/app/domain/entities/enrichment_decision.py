from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass(slots=True)
class EnrichmentDecision:
    order_id: str
    matched_rules: list[str]
    enriched_fields: dict[str, Any]
    decision_timestamp: datetime
    explanation: str
    applied_rule_details: list[dict[str, str]] = field(default_factory=list)

    @property
    def has_matches(self) -> bool:
        return len(self.matched_rules) > 0

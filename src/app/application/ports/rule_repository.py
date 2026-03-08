from abc import ABC, abstractmethod
from datetime import datetime

from app.domain.entities.enrichment_rule import EnrichmentRule


class EnrichmentRuleRepository(ABC):
    @abstractmethod
    def list_active_rules(
        self,
        *,
        now: datetime,
        client_code: str | None,
        facility_code: str | None,
        zone_code: str | None,
    ) -> list[EnrichmentRule]:
        raise NotImplementedError

    @abstractmethod
    def upsert_many(self, rules: list[EnrichmentRule]) -> None:
        raise NotImplementedError

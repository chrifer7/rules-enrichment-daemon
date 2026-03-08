from datetime import datetime

from app.application.ports.unit_of_work import UnitOfWork
from app.domain.entities.enrichment_rule import EnrichmentRule


class RefreshRulesCacheUseCase:
    def __init__(self, uow: UnitOfWork):
        self._uow = uow
        self._cache: dict[tuple[str | None, str | None, str | None], tuple[datetime, list[EnrichmentRule]]] = {}

    def execute(
        self,
        *,
        now: datetime,
        ttl_seconds: int,
        client_code: str | None,
        facility_code: str | None,
        zone_code: str | None,
    ) -> list[EnrichmentRule]:
        key = (client_code, facility_code, zone_code)
        cached = self._cache.get(key)
        if cached:
            ts, data = cached
            if (now - ts).total_seconds() <= ttl_seconds:
                return data

        with self._uow:
            rules = self._uow.rules.list_active_rules(
                now=now,
                client_code=client_code,
                facility_code=facility_code,
                zone_code=zone_code,
            )
        self._cache[key] = (now, rules)
        return rules

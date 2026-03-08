from app.application.dto.enrichment import EnrichmentPayloadDTO
from app.domain.entities.enrichment_decision import EnrichmentDecision


class EnrichmentPayloadBuilder:
    def __init__(self, *, correlation_id: str, source_system: str, enrichment_version: int):
        self._correlation_id = correlation_id
        self._source_system = source_system
        self._enrichment_version = enrichment_version

    def build(self, decision: EnrichmentDecision) -> EnrichmentPayloadDTO:
        return EnrichmentPayloadDTO(
            correlation_id=self._correlation_id,
            source_system=self._source_system,
            enrichment_version=self._enrichment_version,
            applied_rules=decision.applied_rule_details,
            enriched_fields=decision.enriched_fields,
        )

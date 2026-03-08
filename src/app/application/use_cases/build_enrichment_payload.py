from app.application.builders.enrichment_payload_builder import EnrichmentPayloadBuilder
from app.domain.entities.enrichment_decision import EnrichmentDecision


class BuildEnrichmentPayloadUseCase:
    def __init__(self, *, source_system: str, enrichment_version: int):
        self._source_system = source_system
        self._enrichment_version = enrichment_version

    def execute(self, *, correlation_id: str, decision: EnrichmentDecision):
        builder = EnrichmentPayloadBuilder(
            correlation_id=correlation_id,
            source_system=self._source_system,
            enrichment_version=self._enrichment_version,
        )
        return builder.build(decision)

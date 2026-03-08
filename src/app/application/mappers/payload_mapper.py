from app.application.dto.enrichment import EnrichmentPayloadDTO


def payload_to_dict(payload: EnrichmentPayloadDTO) -> dict:
    return {
        "correlation_id": payload.correlation_id,
        "source_system": payload.source_system,
        "enrichment_version": payload.enrichment_version,
        "applied_rules": payload.applied_rules,
        "enriched_fields": payload.enriched_fields,
    }

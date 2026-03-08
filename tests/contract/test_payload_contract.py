from app.application.dto.enrichment import EnrichmentPayloadDTO
from app.application.mappers.payload_mapper import payload_to_dict


def test_enrichment_payload_contract_shape() -> None:
    payload = EnrichmentPayloadDTO(
        correlation_id="corr-1",
        source_system="rules-enrichment-daemon",
        enrichment_version=1,
        applied_rules=[{"rule_id": "RULE-1", "rule_type": "destination", "description": "matched"}],
        enriched_fields={"destination_lane": "ES01"},
    )
    body = payload_to_dict(payload)

    assert set(body.keys()) == {
        "correlation_id",
        "source_system",
        "enrichment_version",
        "applied_rules",
        "enriched_fields",
    }

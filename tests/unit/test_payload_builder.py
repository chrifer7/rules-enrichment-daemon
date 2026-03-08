from app.application.builders.enrichment_payload_builder import EnrichmentPayloadBuilder
from app.domain.entities.enrichment_decision import EnrichmentDecision
from datetime import datetime, timezone


def test_payload_builder_shape() -> None:
    decision = EnrichmentDecision(
        order_id="ORD-1",
        matched_rules=["RULE-1"],
        enriched_fields={"destination_lane": "ES01"},
        decision_timestamp=datetime.now(tz=timezone.utc),
        explanation="ok",
        applied_rule_details=[{"rule_id": "RULE-1", "rule_type": "destination", "description": "matched"}],
    )
    payload = EnrichmentPayloadBuilder(
        correlation_id="corr-1",
        source_system="rules-enrichment-daemon",
        enrichment_version=1,
    ).build(decision)

    assert payload.correlation_id == "corr-1"
    assert payload.enriched_fields["destination_lane"] == "ES01"

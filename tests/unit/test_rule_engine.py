from datetime import datetime, timezone

from app.domain.entities.enrichment_rule import EnrichmentRule
from app.domain.entities.external_order import ExternalOrder
from app.domain.entities.external_order_line import ExternalOrderLine
from app.domain.services.rule_evaluation_service import RuleEvaluationService
from app.domain.value_objects.address import Address


def test_rule_evaluation_matches_destination_country() -> None:
    order = ExternalOrder(
        order_id="ORD-1",
        client_code="DHL",
        facility_code="FC-MIL-01",
        zone_code="A1",
        order_type="OUTBOUND",
        priority=2,
        status="READY_FOR_ENRICHMENT",
        source_address=Address("A", "Via Roma 10", "Milano", "20100", "IT"),
        destination_address=Address("B", "Calle Mayor 1", "Madrid", "28001", "ES"),
        total_weight_kg=12,
        total_volume_m3=0.12,
        lines=[
            ExternalOrderLine(1, "SKU", "item", 1, "EA", 1.0, 0.01, False, "AMBIENT")
        ],
        created_at=datetime.now(tz=timezone.utc),
        updated_at=datetime.now(tz=timezone.utc),
    )

    rule = EnrichmentRule(
        rule_id="RULE-1",
        facility_code=None,
        client_code=None,
        zone_code=None,
        rule_type="destination",
        priority=1,
        is_active=True,
        conditions_json={"and": [{"field": "destination_address.country_code", "op": "eq", "value": "ES"}]},
        enrichment_json={"destination_lane": "ES01"},
        valid_from=None,
        valid_to=None,
    )

    decision = RuleEvaluationService().evaluate(order=order, rules=[rule], now=datetime.now(tz=timezone.utc))
    assert decision.has_matches is True
    assert decision.enriched_fields["destination_lane"] == "ES01"

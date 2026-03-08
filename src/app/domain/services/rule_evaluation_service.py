from datetime import datetime

from app.domain.entities.enrichment_decision import EnrichmentDecision
from app.domain.entities.enrichment_rule import EnrichmentRule
from app.domain.entities.external_order import ExternalOrder
from app.domain.services.rule_specification_factory import RuleSpecificationFactory


class RuleEvaluationService:
    def __init__(self, specification_factory: RuleSpecificationFactory | None = None):
        self._spec_factory = specification_factory or RuleSpecificationFactory()

    def evaluate(self, *, order: ExternalOrder, rules: list[EnrichmentRule], now: datetime) -> EnrichmentDecision:
        active = [rule for rule in rules if rule.is_valid_at(now)]
        active.sort(key=lambda r: r.priority)

        matched_rules: list[str] = []
        applied_details: list[dict[str, str]] = []
        enriched_fields: dict = {}

        for rule in active:
            spec = self._spec_factory.from_json(rule.conditions_json)
            if spec.is_satisfied_by(order):
                matched_rules.append(rule.rule_id)
                applied_details.append(
                    {
                        "rule_id": rule.rule_id,
                        "rule_type": rule.rule_type,
                        "description": f"matched priority {rule.priority}",
                    }
                )
                enriched_fields.update(rule.enrichment_json)

        explanation = "No rules matched" if not matched_rules else f"Matched {len(matched_rules)} rules"
        return EnrichmentDecision(
            order_id=order.order_id,
            matched_rules=matched_rules,
            enriched_fields=enriched_fields,
            decision_timestamp=now,
            explanation=explanation,
            applied_rule_details=applied_details,
        )

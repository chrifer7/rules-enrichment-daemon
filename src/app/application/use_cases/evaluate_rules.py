from datetime import datetime

from app.application.ports.unit_of_work import UnitOfWork
from app.domain.entities.enrichment_decision import EnrichmentDecision
from app.domain.entities.external_order import ExternalOrder
from app.domain.services.rule_evaluation_service import RuleEvaluationService


class EvaluateRulesUseCase:
    def __init__(self, rule_evaluator: RuleEvaluationService | None = None):
        self._rule_evaluator = rule_evaluator or RuleEvaluationService()

    def execute(self, *, order: ExternalOrder, rules, now: datetime) -> EnrichmentDecision:
        return self._rule_evaluator.evaluate(order=order, rules=rules, now=now)

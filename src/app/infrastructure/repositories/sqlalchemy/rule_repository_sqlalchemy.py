from datetime import datetime

from sqlalchemy import asc, or_, select
from sqlalchemy.orm import Session

from app.application.ports.rule_repository import EnrichmentRuleRepository
from app.domain.entities.enrichment_rule import EnrichmentRule
from app.infrastructure.db.models import EnrichmentRuleModel
from app.infrastructure.repositories.mappers import to_rule


class SqlAlchemyEnrichmentRuleRepository(EnrichmentRuleRepository):
    def __init__(self, session: Session):
        self._session = session

    def list_active_rules(
        self,
        *,
        now: datetime,
        client_code: str | None,
        facility_code: str | None,
        zone_code: str | None,
    ) -> list[EnrichmentRule]:
        stmt = select(EnrichmentRuleModel).where(EnrichmentRuleModel.is_active.is_(True))
        stmt = stmt.where(or_(EnrichmentRuleModel.valid_from.is_(None), EnrichmentRuleModel.valid_from <= now))
        stmt = stmt.where(or_(EnrichmentRuleModel.valid_to.is_(None), EnrichmentRuleModel.valid_to >= now))
        if client_code:
            stmt = stmt.where(or_(EnrichmentRuleModel.client_code == client_code, EnrichmentRuleModel.client_code.is_(None)))
        if facility_code:
            stmt = stmt.where(or_(EnrichmentRuleModel.facility_code == facility_code, EnrichmentRuleModel.facility_code.is_(None)))
        if zone_code:
            stmt = stmt.where(or_(EnrichmentRuleModel.zone_code == zone_code, EnrichmentRuleModel.zone_code.is_(None)))
        stmt = stmt.order_by(asc(EnrichmentRuleModel.priority))
        return [to_rule(model) for model in self._session.scalars(stmt).all()]

    def upsert_many(self, rules: list[EnrichmentRule]) -> None:
        for rule in rules:
            model = self._session.get(EnrichmentRuleModel, rule.rule_id)
            if model is None:
                model = EnrichmentRuleModel(rule_id=rule.rule_id)
                self._session.add(model)
            model.facility_code = rule.facility_code
            model.client_code = rule.client_code
            model.zone_code = rule.zone_code
            model.rule_type = rule.rule_type
            model.priority = rule.priority
            model.is_active = rule.is_active
            model.conditions_json = rule.conditions_json
            model.enrichment_json = rule.enrichment_json
            model.valid_from = rule.valid_from
            model.valid_to = rule.valid_to

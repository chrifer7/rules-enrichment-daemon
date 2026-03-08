from app.bootstrap import Bootstrap
from app.domain.entities.enrichment_rule import EnrichmentRule
from datetime import datetime, timezone


def test_sqlalchemy_rule_repository_roundtrip() -> None:
    bootstrap = Bootstrap()
    now = datetime.now(tz=timezone.utc)
    with bootstrap.uow() as uow:
        uow.rules.upsert_many(
            [
                EnrichmentRule(
                    rule_id="RULE-X",
                    facility_code=None,
                    client_code=None,
                    zone_code=None,
                    rule_type="destination",
                    priority=1,
                    is_active=True,
                    conditions_json={"and": [{"field": "destination_address.country_code", "op": "eq", "value": "ES"}]},
                    enrichment_json={"destination_lane": "ES01"},
                    valid_from=now,
                    valid_to=None,
                )
            ]
        )
        uow.commit()

    with bootstrap.uow() as uow:
        rules = uow.rules.list_active_rules(now=now, client_code=None, facility_code=None, zone_code=None)
    assert any(rule.rule_id == "RULE-X" for rule in rules)

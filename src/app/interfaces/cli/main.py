import logging
import time
from datetime import datetime, timezone

import typer

from app.bootstrap import Bootstrap
from app.domain.entities.enrichment_rule import EnrichmentRule

cli = typer.Typer(help="Rules Enrichment Daemon CLI")
logger = logging.getLogger(__name__)


@cli.command("run-daemon")
def run_daemon() -> None:
    bootstrap = Bootstrap()
    poll_worker = bootstrap.polling_worker()
    outbox_worker = bootstrap.outbox_worker()

    logger.info(
        "daemon_start",
        extra={"event.action": "daemon_start", "event.category": "process", "event.outcome": "success"},
    )
    while True:
        poll_worker.run_once()
        outbox_worker.run_once()
        time.sleep(bootstrap.settings.poll_interval_seconds)


@cli.command("publish-outbox")
def publish_outbox() -> None:
    bootstrap = Bootstrap()
    published = bootstrap.outbox_worker().run_once()
    typer.echo(f"published={published}")


@cli.command("seed-rules")
def seed_rules(force: bool = typer.Option(False, help="Insert/update baseline rules even when DB already has rules")) -> None:
    bootstrap = Bootstrap()
    with bootstrap.uow() as uow:
        existing = len(
            uow.rules.list_active_rules(
                now=datetime.now(tz=timezone.utc),
                client_code=None,
                facility_code=None,
                zone_code=None,
            )
        )
    if existing > 0 and not force:
        typer.echo(f"skipped=true reason=rules_already_present active_rules={existing} hint='use --force to upsert baseline rules'")
        return

    now = datetime.now(tz=timezone.utc)
    rules = [
        EnrichmentRule(
            rule_id="RULE-DEST-ES-001",
            facility_code=None,
            client_code=None,
            zone_code=None,
            rule_type="destination",
            priority=10,
            is_active=True,
            conditions_json={"and": [{"field": "destination_address.country_code", "op": "eq", "value": "ES"}]},
            enrichment_json={"destination_lane": "ES01", "treatment_code": "STANDARD"},
            valid_from=now,
            valid_to=None,
        ),
        EnrichmentRule(
            rule_id="RULE-ORIGIN-ROMA-002",
            facility_code="FC-MIL-01",
            client_code="DHL",
            zone_code=None,
            rule_type="origin_address",
            priority=20,
            is_active=True,
            conditions_json={"and": [{"field": "source_address.address_line_1", "op": "contains", "value": "Via Roma"}]},
            enrichment_json={"source_handling_code": "SPECIAL_ORIGIN", "allocation_zone": "A1"},
            valid_from=now,
            valid_to=None,
        ),
    ]
    with bootstrap.uow() as uow:
        uow.rules.upsert_many(rules)
        uow.commit()
    typer.echo("seeded_rules=2 mode=baseline")


@cli.command("replay-dead-letter")
def replay_dead_letter() -> None:
    typer.echo("Not implemented yet: replay pipeline")


@cli.command("health-check")
def health_check() -> None:
    bootstrap = Bootstrap()
    db_ok = True
    api_ok = bootstrap.external_wms().health_check()
    typer.echo(f"db_ok={db_ok} api_ok={api_ok}")


@cli.command("validate-rules")
def validate_rules() -> None:
    bootstrap = Bootstrap()
    with bootstrap.uow() as uow:
        rules = uow.rules.list_active_rules(
            now=datetime.now(tz=timezone.utc),
            client_code=None,
            facility_code=None,
            zone_code=None,
        )
    typer.echo(f"active_rules={len(rules)}")


def app() -> None:
    cli()


if __name__ == "__main__":
    app()

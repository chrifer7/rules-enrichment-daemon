from dataclasses import dataclass

from app.application.facades.enrichment_facade import EnrichmentFacade
from app.application.ports.external_wms_port import ExternalWmsPort
from app.application.use_cases.build_enrichment_payload import BuildEnrichmentPayloadUseCase
from app.application.use_cases.evaluate_rules import EvaluateRulesUseCase
from app.application.use_cases.move_dead_letter import MoveOrderToDeadLetterUseCase
from app.application.use_cases.persist_processing_result import PersistProcessingResultUseCase
from app.application.use_cases.poll_orders import PollOrdersForEnrichmentUseCase
from app.application.use_cases.process_order import ProcessOrderForEnrichmentUseCase
from app.application.use_cases.publish_outbox import PublishOutboxMessagesUseCase
from app.application.use_cases.refresh_rules_cache import RefreshRulesCacheUseCase
from app.application.use_cases.submit_enrichment import SubmitEnrichmentUseCase
from app.config.settings import Settings, get_settings
from app.domain.services.enrichment_hash_service import EnrichmentHashService
from app.infrastructure.db.session import build_session_factory
from app.infrastructure.http.clients.manhattan_simulator_client import ManhattanSimulatorHttpClient
from app.infrastructure.http.retry.retry_policy import RetryPolicy
from app.infrastructure.outbox.sinks import StructuredLogOutboxSink, WebhookOutboxSink
from app.infrastructure.unit_of_work.sqlalchemy_uow import SqlAlchemyUnitOfWork
from app.infrastructure.workers.outbox_publisher_worker import OutboxPublisherWorker
from app.infrastructure.workers.polling_worker import PollingWorker
from app.shared.clock.clock import Clock
from app.shared.ids.ids import IdGenerator
from app.shared.logging.ecs import configure_logging


@dataclass(slots=True)
class Container:
    settings: Settings
    session_factory: object


class Bootstrap:
    def __init__(self, settings: Settings | None = None):
        self.settings = settings or get_settings()
        configure_logging(self.settings)

        self.container = Container(settings=self.settings, session_factory=build_session_factory(self.settings))

    def uow(self) -> SqlAlchemyUnitOfWork:
        return SqlAlchemyUnitOfWork(self.container.session_factory)

    def external_wms(self) -> ExternalWmsPort:
        return ManhattanSimulatorHttpClient(
            base_url=self.settings.external_api_base_url,
            timeout_seconds=self.settings.external_api_timeout_seconds,
            api_key=self.settings.external_api_api_key,
            retry_policy=RetryPolicy(max_attempts=3),
        )

    def outbox_sink(self):
        if self.settings.outbox_sink_mode == "webhook" and self.settings.outbox_webhook_url:
            return WebhookOutboxSink(self.settings.outbox_webhook_url)
        return StructuredLogOutboxSink()

    def enrichment_facade(self) -> EnrichmentFacade:
        evaluate = EvaluateRulesUseCase()
        build_payload = BuildEnrichmentPayloadUseCase(
            source_system=self.settings.enrichment_source_system,
            enrichment_version=self.settings.enrichment_version,
        )
        submit = SubmitEnrichmentUseCase(self.external_wms())
        persist = PersistProcessingResultUseCase(self.uow())
        dead_letter = MoveOrderToDeadLetterUseCase(self.uow())
        process = ProcessOrderForEnrichmentUseCase(
            uow=self.uow(),
            evaluate_rules_use_case=evaluate,
            build_payload_use_case=build_payload,
            submit_use_case=submit,
            persist_result_use_case=persist,
            move_dead_letter_use_case=dead_letter,
            hash_service=EnrichmentHashService(),
            id_generator=IdGenerator(),
            max_processing_attempts=self.settings.max_processing_attempts,
        )
        poll = PollOrdersForEnrichmentUseCase(self.external_wms())
        refresh_rules = RefreshRulesCacheUseCase(self.uow())
        return EnrichmentFacade(
            poll_use_case=poll,
            process_use_case=process,
            refresh_rules_cache_use_case=refresh_rules,
            clock=Clock(),
            id_generator=IdGenerator(),
            poll_batch_size=self.settings.poll_batch_size,
            rule_cache_ttl_seconds=self.settings.rule_cache_ttl_seconds,
        )

    def polling_worker(self) -> PollingWorker:
        return PollingWorker(self.enrichment_facade(), self.settings.poll_interval_seconds)

    def outbox_worker(self) -> OutboxPublisherWorker:
        use_case = PublishOutboxMessagesUseCase(self.uow(), self.outbox_sink())
        return OutboxPublisherWorker(use_case, self.settings.outbox_publish_interval_seconds)

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
    # This project uses a very small "container" object instead of a full DI framework.
    # Its only goal is to hold long-lived process dependencies in one place.
    settings: Settings
    session_factory: object


class Bootstrap:
    def __init__(self, settings: Settings | None = None):
        # `get_settings()` is cached, so callers usually get one stable configuration
        # object per process. This is a pragmatic choice for a daemon-style workload.
        self.settings = settings or get_settings()
        configure_logging(self.settings)

        # This class is the composition root of the application: the place where
        # concrete infrastructure implementations are wired to abstract ports/use cases.
        self.container = Container(settings=self.settings, session_factory=build_session_factory(self.settings))

    def uow(self) -> SqlAlchemyUnitOfWork:
        # Return a new Unit of Work every time so each business operation gets its
        # own fresh database session and transaction scope.
        return SqlAlchemyUnitOfWork(self.container.session_factory)

    def external_wms(self) -> ExternalWmsPort:
        # The application depends on the interface `ExternalWmsPort`.
        # Here we choose the Manhattan simulator as the concrete implementation.
        return ManhattanSimulatorHttpClient(
            base_url=self.settings.external_api_base_url,
            timeout_seconds=self.settings.external_api_timeout_seconds,
            api_key=self.settings.external_api_api_key,
            retry_policy=RetryPolicy(max_attempts=3),
        )

    def outbox_sink(self):
        # A small strategy switch:
        # - `webhook` sends outbox messages to an HTTP endpoint
        # - default mode writes them as structured logs for observability/demo purposes
        if self.settings.outbox_sink_mode == "webhook" and self.settings.outbox_webhook_url:
            return WebhookOutboxSink(self.settings.outbox_webhook_url)
        return StructuredLogOutboxSink()

    def enrichment_facade(self) -> EnrichmentFacade:
        # Build the orchestration facade from many narrow use cases.
        # This keeps the business logic modular and easier to test/replace later.
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
        # Workers are intentionally thin. They own the "loop forever" behavior and
        # delegate the real domain/application work to the facade layer.
        return PollingWorker(self.enrichment_facade(), self.settings.poll_interval_seconds)

    def outbox_worker(self) -> OutboxPublisherWorker:
        use_case = PublishOutboxMessagesUseCase(self.uow(), self.outbox_sink())
        return OutboxPublisherWorker(use_case, self.settings.outbox_publish_interval_seconds)

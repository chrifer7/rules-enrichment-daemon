from dataclasses import asdict
from datetime import datetime

from app.application.ports.unit_of_work import UnitOfWork
from app.application.use_cases.build_enrichment_payload import BuildEnrichmentPayloadUseCase
from app.application.use_cases.evaluate_rules import EvaluateRulesUseCase
from app.application.use_cases.move_dead_letter import MoveOrderToDeadLetterUseCase
from app.application.use_cases.persist_processing_result import PersistProcessingResultUseCase
from app.application.use_cases.submit_enrichment import SubmitEnrichmentUseCase
from app.domain.entities.external_order import ExternalOrder
from app.domain.services.enrichment_hash_service import EnrichmentHashService
from app.shared.errors.errors import EnrichmentSubmissionError
from app.shared.ids.ids import IdGenerator


class ProcessOrderForEnrichmentUseCase:
    def __init__(
        self,
        *,
        uow: UnitOfWork,
        evaluate_rules_use_case: EvaluateRulesUseCase,
        build_payload_use_case: BuildEnrichmentPayloadUseCase,
        submit_use_case: SubmitEnrichmentUseCase,
        persist_result_use_case: PersistProcessingResultUseCase,
        move_dead_letter_use_case: MoveOrderToDeadLetterUseCase,
        hash_service: EnrichmentHashService,
        id_generator: IdGenerator,
        max_processing_attempts: int,
    ):
        self._uow = uow
        self._evaluate_rules = evaluate_rules_use_case
        self._build_payload = build_payload_use_case
        self._submit = submit_use_case
        self._persist = persist_result_use_case
        self._dead_letter = move_dead_letter_use_case
        self._hash_service = hash_service
        self._ids = id_generator
        self._max_processing_attempts = max_processing_attempts

    def execute(self, *, order: ExternalOrder, rules, now: datetime) -> tuple[bool, str, bool]:
        correlation_id = self._ids.new_id()
        with self._uow:
            attempt_number = self._uow.attempts.get_next_attempt_number(order.order_id)

        decision = self._evaluate_rules.execute(order=order, rules=rules, now=now)
        preview_hash = self._hash_service.compute(order, decision.enriched_fields)

        with self._uow:
            processed = self._uow.processed_orders.get_by_order_id(order.order_id)

        if processed and processed.enrichment_hash == preview_hash:
            return True, correlation_id, True

        if not decision.has_matches:
            self._persist.execute(
                order_id=order.order_id,
                correlation_id=correlation_id,
                attempt_number=attempt_number,
                enrichment_hash=preview_hash,
                success=True,
                now=now,
                event_payload={"event": "NoRulesMatched", "order_id": order.order_id},
            )
            return True, correlation_id, False

        payload = self._build_payload.execute(correlation_id=correlation_id, decision=decision)

        try:
            self._submit.execute(order_id=order.order_id, payload=payload, correlation_id=correlation_id)
            self._persist.execute(
                order_id=order.order_id,
                correlation_id=correlation_id,
                attempt_number=attempt_number,
                enrichment_hash=preview_hash,
                success=True,
                now=now,
                event_payload={
                    "event": "OrderEnrichmentSucceeded",
                    "order_id": order.order_id,
                    "rules": decision.matched_rules,
                },
            )
            return True, correlation_id, False
        except Exception as exc:
            self._persist.execute(
                order_id=order.order_id,
                correlation_id=correlation_id,
                attempt_number=attempt_number,
                enrichment_hash=preview_hash,
                success=False,
                now=now,
                event_payload={
                    "event": "OrderEnrichmentFailed",
                    "order_id": order.order_id,
                    "error": str(exc),
                },
            )
            if attempt_number >= self._max_processing_attempts:
                self._dead_letter.execute(
                    order_id=order.order_id,
                    correlation_id=correlation_id,
                    reason="max attempts exceeded",
                    payload={"order": asdict(order)},
                    now=now,
                )
            raise EnrichmentSubmissionError(str(exc)) from exc

from app.domain.entities.dead_letter_item import DeadLetterItem
from app.domain.entities.enrichment_rule import EnrichmentRule
from app.domain.entities.outbox_message import OutboxMessage
from app.domain.entities.processed_order import ProcessedOrder
from app.domain.entities.processing_attempt import ProcessingAttempt
from app.domain.enums.processing import OutboxStatus, ProcessingStatus
from app.infrastructure.db.models import (
    DeadLetterItemModel,
    EnrichmentRuleModel,
    OutboxMessageModel,
    ProcessedOrderModel,
    ProcessingAttemptModel,
)


def to_rule(model: EnrichmentRuleModel) -> EnrichmentRule:
    return EnrichmentRule(
        rule_id=model.rule_id,
        facility_code=model.facility_code,
        client_code=model.client_code,
        zone_code=model.zone_code,
        rule_type=model.rule_type,
        priority=model.priority,
        is_active=model.is_active,
        conditions_json=model.conditions_json,
        enrichment_json=model.enrichment_json,
        valid_from=model.valid_from,
        valid_to=model.valid_to,
    )


def to_attempt(model: ProcessingAttemptModel) -> ProcessingAttempt:
    return ProcessingAttempt(
        order_id=model.order_id,
        correlation_id=model.correlation_id,
        attempt_number=model.attempt_number,
        status=ProcessingStatus(model.status),
        started_at=model.started_at,
        finished_at=model.finished_at,
        error_message=model.error_message,
    )


def to_processed(model: ProcessedOrderModel) -> ProcessedOrder:
    return ProcessedOrder(
        order_id=model.order_id,
        enrichment_hash=model.enrichment_hash,
        processed_at=model.processed_at,
        correlation_id=model.correlation_id,
    )


def to_outbox(model: OutboxMessageModel) -> OutboxMessage:
    return OutboxMessage(
        message_id=model.message_id,
        aggregate_type=model.aggregate_type,
        aggregate_id=model.aggregate_id,
        event_type=model.event_type,
        payload_json=model.payload_json,
        status=OutboxStatus(model.status),
        created_at=model.created_at,
        published_at=model.published_at,
    )


def to_dead_letter(model: DeadLetterItemModel) -> DeadLetterItem:
    return DeadLetterItem(
        order_id=model.order_id,
        correlation_id=model.correlation_id,
        reason=model.reason,
        payload_json=model.payload_json,
        created_at=model.created_at,
    )

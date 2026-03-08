from datetime import datetime

from sqlalchemy import JSON, Boolean, DateTime, Index, Integer, String, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class EnrichmentRuleModel(Base):
    __tablename__ = "enrichment_rules"

    rule_id: Mapped[str] = mapped_column(String(80), primary_key=True)
    facility_code: Mapped[str | None] = mapped_column(String(40), index=True)
    client_code: Mapped[str | None] = mapped_column(String(40), index=True)
    zone_code: Mapped[str | None] = mapped_column(String(40), index=True)
    rule_type: Mapped[str] = mapped_column(String(40), nullable=False)
    priority: Mapped[int] = mapped_column(Integer, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, index=True)
    conditions_json: Mapped[dict] = mapped_column(JSON, nullable=False)
    enrichment_json: Mapped[dict] = mapped_column(JSON, nullable=False)
    valid_from: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    valid_to: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class ProcessingAttemptModel(Base):
    __tablename__ = "processing_attempts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    order_id: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    correlation_id: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    attempt_number: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)


class ProcessedOrderModel(Base):
    __tablename__ = "processed_orders"

    order_id: Mapped[str] = mapped_column(String(80), primary_key=True)
    enrichment_hash: Mapped[str] = mapped_column(String(128), nullable=False)
    processed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    correlation_id: Mapped[str] = mapped_column(String(80), nullable=False, index=True)


class OutboxMessageModel(Base):
    __tablename__ = "outbox_messages"

    message_id: Mapped[str] = mapped_column(String(120), primary_key=True)
    aggregate_type: Mapped[str] = mapped_column(String(60), nullable=False)
    aggregate_id: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    event_type: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    payload_json: Mapped[dict] = mapped_column(JSON, nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class DaemonCheckpointModel(Base):
    __tablename__ = "daemon_checkpoints"

    checkpoint_name: Mapped[str] = mapped_column(String(80), primary_key=True)
    checkpoint_value: Mapped[str] = mapped_column(String(255), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class DeadLetterItemModel(Base):
    __tablename__ = "dead_letter_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    order_id: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    correlation_id: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    payload_json: Mapped[dict] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class RuleAuditEntryModel(Base):
    __tablename__ = "rule_audit_entries"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    order_id: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    rule_id: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    correlation_id: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    matched: Mapped[bool] = mapped_column(Boolean, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


Index("ix_rules_scope", EnrichmentRuleModel.client_code, EnrichmentRuleModel.facility_code, EnrichmentRuleModel.zone_code)
Index("ix_attempt_order_attempt", ProcessingAttemptModel.order_id, ProcessingAttemptModel.attempt_number)
Index("ix_outbox_status_created", OutboxMessageModel.status, OutboxMessageModel.created_at)

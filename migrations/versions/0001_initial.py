"""initial schema

Revision ID: 0001_initial
Revises:
Create Date: 2026-03-07 20:00:00.000000
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

revision: str = "0001_initial"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "enrichment_rules",
        sa.Column("rule_id", sa.String(length=80), nullable=False),
        sa.Column("facility_code", sa.String(length=40), nullable=True),
        sa.Column("client_code", sa.String(length=40), nullable=True),
        sa.Column("zone_code", sa.String(length=40), nullable=True),
        sa.Column("rule_type", sa.String(length=40), nullable=False),
        sa.Column("priority", sa.Integer(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("conditions_json", sa.JSON(), nullable=False),
        sa.Column("enrichment_json", sa.JSON(), nullable=False),
        sa.Column("valid_from", sa.DateTime(timezone=True), nullable=True),
        sa.Column("valid_to", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("rule_id"),
    )
    op.create_index("ix_enrichment_rules_client_code", "enrichment_rules", ["client_code"], unique=False)
    op.create_index("ix_enrichment_rules_facility_code", "enrichment_rules", ["facility_code"], unique=False)
    op.create_index("ix_enrichment_rules_is_active", "enrichment_rules", ["is_active"], unique=False)
    op.create_index("ix_enrichment_rules_zone_code", "enrichment_rules", ["zone_code"], unique=False)
    op.create_index("ix_rules_scope", "enrichment_rules", ["client_code", "facility_code", "zone_code"], unique=False)

    op.create_table(
        "processing_attempts",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("order_id", sa.String(length=80), nullable=False),
        sa.Column("correlation_id", sa.String(length=80), nullable=False),
        sa.Column("attempt_number", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_processing_attempts_order_id", "processing_attempts", ["order_id"], unique=False)
    op.create_index("ix_processing_attempts_correlation_id", "processing_attempts", ["correlation_id"], unique=False)
    op.create_index("ix_processing_attempts_status", "processing_attempts", ["status"], unique=False)
    op.create_index("ix_attempt_order_attempt", "processing_attempts", ["order_id", "attempt_number"], unique=False)

    op.create_table(
        "processed_orders",
        sa.Column("order_id", sa.String(length=80), nullable=False),
        sa.Column("enrichment_hash", sa.String(length=128), nullable=False),
        sa.Column("processed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("correlation_id", sa.String(length=80), nullable=False),
        sa.PrimaryKeyConstraint("order_id"),
    )
    op.create_index("ix_processed_orders_correlation_id", "processed_orders", ["correlation_id"], unique=False)

    op.create_table(
        "outbox_messages",
        sa.Column("message_id", sa.String(length=120), nullable=False),
        sa.Column("aggregate_type", sa.String(length=60), nullable=False),
        sa.Column("aggregate_id", sa.String(length=80), nullable=False),
        sa.Column("event_type", sa.String(length=80), nullable=False),
        sa.Column("payload_json", sa.JSON(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("message_id"),
    )
    op.create_index("ix_outbox_messages_aggregate_id", "outbox_messages", ["aggregate_id"], unique=False)
    op.create_index("ix_outbox_messages_created_at", "outbox_messages", ["created_at"], unique=False)
    op.create_index("ix_outbox_messages_event_type", "outbox_messages", ["event_type"], unique=False)
    op.create_index("ix_outbox_messages_status", "outbox_messages", ["status"], unique=False)
    op.create_index("ix_outbox_status_created", "outbox_messages", ["status", "created_at"], unique=False)

    op.create_table(
        "daemon_checkpoints",
        sa.Column("checkpoint_name", sa.String(length=80), nullable=False),
        sa.Column("checkpoint_value", sa.String(length=255), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("checkpoint_name"),
    )

    op.create_table(
        "dead_letter_items",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("order_id", sa.String(length=80), nullable=False),
        sa.Column("correlation_id", sa.String(length=80), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("payload_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_dead_letter_items_order_id", "dead_letter_items", ["order_id"], unique=False)
    op.create_index("ix_dead_letter_items_correlation_id", "dead_letter_items", ["correlation_id"], unique=False)

    op.create_table(
        "rule_audit_entries",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("order_id", sa.String(length=80), nullable=False),
        sa.Column("rule_id", sa.String(length=80), nullable=False),
        sa.Column("correlation_id", sa.String(length=80), nullable=False),
        sa.Column("matched", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_rule_audit_entries_order_id", "rule_audit_entries", ["order_id"], unique=False)
    op.create_index("ix_rule_audit_entries_rule_id", "rule_audit_entries", ["rule_id"], unique=False)
    op.create_index("ix_rule_audit_entries_correlation_id", "rule_audit_entries", ["correlation_id"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_rule_audit_entries_correlation_id", table_name="rule_audit_entries")
    op.drop_index("ix_rule_audit_entries_rule_id", table_name="rule_audit_entries")
    op.drop_index("ix_rule_audit_entries_order_id", table_name="rule_audit_entries")
    op.drop_table("rule_audit_entries")

    op.drop_index("ix_dead_letter_items_correlation_id", table_name="dead_letter_items")
    op.drop_index("ix_dead_letter_items_order_id", table_name="dead_letter_items")
    op.drop_table("dead_letter_items")

    op.drop_table("daemon_checkpoints")

    op.drop_index("ix_outbox_status_created", table_name="outbox_messages")
    op.drop_index("ix_outbox_messages_status", table_name="outbox_messages")
    op.drop_index("ix_outbox_messages_event_type", table_name="outbox_messages")
    op.drop_index("ix_outbox_messages_created_at", table_name="outbox_messages")
    op.drop_index("ix_outbox_messages_aggregate_id", table_name="outbox_messages")
    op.drop_table("outbox_messages")

    op.drop_index("ix_processed_orders_correlation_id", table_name="processed_orders")
    op.drop_table("processed_orders")

    op.drop_index("ix_attempt_order_attempt", table_name="processing_attempts")
    op.drop_index("ix_processing_attempts_status", table_name="processing_attempts")
    op.drop_index("ix_processing_attempts_correlation_id", table_name="processing_attempts")
    op.drop_index("ix_processing_attempts_order_id", table_name="processing_attempts")
    op.drop_table("processing_attempts")

    op.drop_index("ix_rules_scope", table_name="enrichment_rules")
    op.drop_index("ix_enrichment_rules_zone_code", table_name="enrichment_rules")
    op.drop_index("ix_enrichment_rules_is_active", table_name="enrichment_rules")
    op.drop_index("ix_enrichment_rules_facility_code", table_name="enrichment_rules")
    op.drop_index("ix_enrichment_rules_client_code", table_name="enrichment_rules")
    op.drop_table("enrichment_rules")

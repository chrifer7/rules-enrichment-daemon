"""seed bulk enrichment rules

Revision ID: 0002_seed_bulk_rules
Revises: 0001_initial
Create Date: 2026-03-08 09:20:00.000000
"""

from collections.abc import Sequence
from datetime import datetime, timedelta, timezone

import sqlalchemy as sa
from alembic import op

revision: str = "0002_seed_bulk_rules"
down_revision: str | None = "0001_initial"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


RULE_COUNT = 3200


def upgrade() -> None:
    now = datetime.now(tz=timezone.utc)

    rule_table = sa.table(
        "enrichment_rules",
        sa.column("rule_id", sa.String),
        sa.column("facility_code", sa.String),
        sa.column("client_code", sa.String),
        sa.column("zone_code", sa.String),
        sa.column("rule_type", sa.String),
        sa.column("priority", sa.Integer),
        sa.column("is_active", sa.Boolean),
        sa.column("conditions_json", sa.JSON),
        sa.column("enrichment_json", sa.JSON),
        sa.column("valid_from", sa.DateTime(timezone=True)),
        sa.column("valid_to", sa.DateTime(timezone=True)),
    )

    countries = ["ES", "FR", "DE", "IT", "PT", "NL"]
    temp_classes = ["AMBIENT", "CHILLED", "FROZEN"]

    rows: list[dict] = []
    for i in range(1, RULE_COUNT + 1):
        client_idx = ((i - 1) % 60) + 1
        facility_idx = ((i - 1) % 3) + 1
        country = countries[i % len(countries)]
        temp = temp_classes[i % len(temp_classes)]

        rows.append(
            {
                "rule_id": f"BULK-RULE-{i:05d}",
                "facility_code": f"SIMF-{client_idx:03d}-{facility_idx:02d}",
                "client_code": f"SIMC-{client_idx:03d}",
                "zone_code": None if i % 4 else f"SIMZ-SIMF-{client_idx:03d}-{facility_idx:02d}-01",
                "rule_type": "destination" if i % 2 else "composite",
                "priority": (i % 250) + 1,
                "is_active": True,
                "conditions_json": {
                    "and": [
                        {"field": "destination_address.country_code", "op": "eq", "value": country},
                        {"field": "total_weight_kg", "op": "gte", "value": float((i % 30) + 1)},
                        {"field": "source_address.address_line_1", "op": "contains", "value": "Via"},
                        {"field": "priority", "op": "lte", "value": 5},
                    ]
                },
                "enrichment_json": {
                    "destination_lane": f"{country}0{(i % 7) + 1}",
                    "source_handling_code": f"SRC-{(i % 12) + 1:02d}",
                    "treatment_code": "STANDARD" if i % 3 else "PRIORITY",
                    "allocation_zone": f"Z{(i % 18) + 1:02d}",
                    "shipping_constraints": {
                        "fragile": i % 5 == 0,
                        "temperature_class": temp,
                    },
                },
                "valid_from": now - timedelta(days=i % 10),
                "valid_to": None if i % 9 else now + timedelta(days=180),
            }
        )

    op.bulk_insert(rule_table, rows)


def downgrade() -> None:
    op.execute(sa.text("DELETE FROM enrichment_rules WHERE rule_id LIKE 'BULK-RULE-%'"))

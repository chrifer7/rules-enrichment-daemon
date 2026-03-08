"""seed long-tail enrichment rules

Revision ID: 0003_seed_longtail_rules
Revises: 0002_seed_bulk_rules
Create Date: 2026-03-08 09:30:00.000000
"""

from collections.abc import Sequence
from datetime import datetime, timedelta, timezone

import sqlalchemy as sa
from alembic import op

revision: str = "0003_seed_longtail_rules"
down_revision: str | None = "0002_seed_bulk_rules"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


RULE_COUNT = 2800


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

    countries = ["ES", "FR", "DE", "IT", "PT", "NL", "BE", "AT"]
    operations = ["contains", "starts_with", "ends_with"]

    rows: list[dict] = []
    for i in range(1, RULE_COUNT + 1):
        client_idx = ((i - 1) % 60) + 1
        facility_idx = ((i - 1) % 3) + 1
        country = countries[i % len(countries)]
        text_op = operations[i % len(operations)]

        rows.append(
            {
                "rule_id": f"LTAIL-RULE-{i:05d}",
                "facility_code": None if i % 6 else f"SIMF-{client_idx:03d}-{facility_idx:02d}",
                "client_code": f"SIMC-{client_idx:03d}",
                "zone_code": None,
                "rule_type": "origin_address",
                "priority": 300 + (i % 400),
                "is_active": True,
                "conditions_json": {
                    "or": [
                        {
                            "and": [
                                {"field": "destination_address.country_code", "op": "eq", "value": country},
                                {
                                    "field": "source_address.address_line_1",
                                    "op": text_op,
                                    "value": "Via" if text_op != "ends_with" else "10",
                                },
                            ]
                        },
                        {
                            "and": [
                                {"field": "total_volume_m3", "op": "gt", "value": round((i % 20) * 0.05, 3)},
                                {"field": "priority", "op": "in", "value": [1, 2, 3, 4, 5]},
                            ]
                        },
                    ]
                },
                "enrichment_json": {
                    "destination_lane": f"LN-{country}-{(i % 9) + 1}",
                    "source_handling_code": f"LTAIL-{(i % 40) + 1:02d}",
                    "treatment_code": "BULK" if i % 4 == 0 else "STANDARD",
                    "allocation_zone": f"LT-{(i % 30) + 1:02d}",
                },
                "valid_from": now - timedelta(days=(i % 45)),
                "valid_to": now + timedelta(days=365) if i % 8 == 0 else None,
            }
        )

    op.bulk_insert(rule_table, rows)


def downgrade() -> None:
    op.execute(sa.text("DELETE FROM enrichment_rules WHERE rule_id LIKE 'LTAIL-RULE-%'"))

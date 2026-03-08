import hashlib
import json

from app.domain.entities.external_order import ExternalOrder


class EnrichmentHashService:
    def compute(self, order: ExternalOrder, enriched_fields: dict) -> str:
        payload = {
            "order_id": order.order_id,
            "order_updated_at": order.updated_at.isoformat(),
            "enriched_fields": enriched_fields,
        }
        canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()

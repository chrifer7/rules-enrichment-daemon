from datetime import datetime

from app.application.ports.external_wms_port import ExternalWmsPort


class PollOrdersForEnrichmentUseCase:
    def __init__(self, external_wms: ExternalWmsPort):
        self._external_wms = external_wms

    def execute(self, *, updated_since: datetime | None, limit: int):
        return self._external_wms.get_orders_for_enrichment(updated_since=updated_since, limit=limit)

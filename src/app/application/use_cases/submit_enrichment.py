from app.application.mappers.payload_mapper import payload_to_dict
from app.application.ports.external_wms_port import ExternalWmsPort


class SubmitEnrichmentUseCase:
    def __init__(self, external_wms: ExternalWmsPort):
        self._external_wms = external_wms

    def execute(self, *, order_id: str, payload, correlation_id: str) -> None:
        self._external_wms.submit_enrichment(order_id=order_id, payload=payload_to_dict(payload), correlation_id=correlation_id)

from dataclasses import dataclass

from app.domain.entities.external_order import ExternalOrder


@dataclass(slots=True)
class ProcessOrderCommand:
    run_id: str
    order: ExternalOrder

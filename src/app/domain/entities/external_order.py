from dataclasses import dataclass
from datetime import datetime

from app.domain.entities.external_order_line import ExternalOrderLine
from app.domain.value_objects.address import Address


@dataclass(slots=True)
class ExternalOrder:
    order_id: str
    client_code: str
    facility_code: str
    zone_code: str | None
    order_type: str
    priority: int
    status: str
    source_address: Address
    destination_address: Address
    total_weight_kg: float
    total_volume_m3: float
    lines: list[ExternalOrderLine]
    created_at: datetime
    updated_at: datetime

    def has_hazmat(self) -> bool:
        return any(line.hazmat_flag for line in self.lines)

    def temperature_classes(self) -> set[str]:
        return {line.temperature_class for line in self.lines}

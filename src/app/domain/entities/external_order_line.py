from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ExternalOrderLine:
    line_number: int
    sku: str
    description: str
    quantity: int
    uom: str
    unit_weight_kg: float
    unit_volume_m3: float
    hazmat_flag: bool
    temperature_class: str

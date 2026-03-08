from dataclasses import dataclass
from datetime import datetime


@dataclass(slots=True)
class ProcessedOrder:
    order_id: str
    enrichment_hash: str
    processed_at: datetime
    correlation_id: str

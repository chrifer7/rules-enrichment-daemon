from dataclasses import dataclass
from datetime import datetime


@dataclass(slots=True)
class PollOrdersCommand:
    run_id: str
    updated_since: datetime | None
    limit: int

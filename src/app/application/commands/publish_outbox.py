from dataclasses import dataclass


@dataclass(slots=True)
class OutboxPublishCommand:
    batch_size: int = 100

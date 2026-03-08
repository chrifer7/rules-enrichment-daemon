from dataclasses import dataclass, field
from typing import Any


@dataclass(slots=True)
class LogContext:
    daemon_run_id: str
    correlation_id: str | None = None
    order_id: str | None = None
    client_code: str | None = None
    facility_code: str | None = None
    attempt: int | None = None
    trace_id: str | None = None
    transaction_id: str | None = None
    extras: dict[str, Any] = field(default_factory=dict)

    def to_extra(self, **kwargs: Any) -> dict[str, Any]:
        data: dict[str, Any] = {
            "daemon.run_id": self.daemon_run_id,
            "correlation.id": self.correlation_id,
            "order.id": self.order_id,
            "client.code": self.client_code,
            "facility.code": self.facility_code,
            "attempt": self.attempt,
            "trace.id": self.trace_id,
            "transaction.id": self.transaction_id,
        }
        data.update(self.extras)
        data.update(kwargs)
        return {k: v for k, v in data.items() if v is not None}

import logging
from datetime import datetime, timezone
from typing import Any

import httpx

from app.application.ports.external_wms_port import ExternalWmsPort
from app.domain.entities.external_order import ExternalOrder
from app.domain.entities.external_order_line import ExternalOrderLine
from app.domain.value_objects.address import Address
from app.infrastructure.http.retry.retry_policy import RetryPolicy
from app.shared.errors.errors import ExternalApiTimeoutError, ExternalApiUnavailableError

logger = logging.getLogger(__name__)


class ManhattanSimulatorHttpClient(ExternalWmsPort):
    def __init__(
        self,
        *,
        base_url: str,
        timeout_seconds: int,
        api_key: str,
        retry_policy: RetryPolicy,
    ):
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout_seconds
        self._api_key = api_key
        self._retry = retry_policy

    def health_check(self) -> bool:
        try:
            response = self._request("GET", "/health")
            return response.status_code == 200
        except Exception:
            return False

    def get_orders_for_enrichment(self, *, updated_since: datetime | None, limit: int) -> list[ExternalOrder]:
        params: dict[str, str | int] = {"status": "READY_FOR_ENRICHMENT", "limit": limit, "offset": 0}
        if updated_since:
            params["updated_since"] = updated_since.isoformat()
        response = self._request("GET", "/api/v1/orders", params=params)
        data = response.json()
        return [self._to_order(item) for item in data]

    def get_order_by_id(self, order_id: str) -> ExternalOrder:
        response = self._request("GET", f"/api/v1/orders/{order_id}")
        return self._to_order(response.json())

    def submit_enrichment(self, order_id: str, payload: dict[str, Any], correlation_id: str) -> None:
        headers = {"X-Correlation-ID": correlation_id}
        self._request("POST", f"/api/v1/orders/{order_id}/enrichment", json=payload, headers=headers)

    def _request(self, method: str, path: str, **kwargs) -> httpx.Response:
        url = f"{self._base_url}{path}"
        headers = kwargs.pop("headers", {})
        if self._api_key:
            headers["X-API-Key"] = self._api_key

        def execute() -> httpx.Response:
            with httpx.Client(timeout=self._timeout) as client:
                return client.request(method, url, headers=headers, **kwargs)

        try:
            response = self._retry.run(execute)
            response.raise_for_status()
            logger.info(
                "external_api_request",
                extra={
                    "event.action": "external_api_request",
                    "event.category": "network",
                    "event.outcome": "success",
                    "http.method": method,
                    "url.full": url,
                    "http.response.status_code": response.status_code,
                },
            )
            return response
        except httpx.TimeoutException as exc:
            raise ExternalApiTimeoutError(str(exc)) from exc
        except httpx.HTTPError as exc:
            raise ExternalApiUnavailableError(str(exc)) from exc

    @staticmethod
    def _parse_datetime(value: str) -> datetime:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
        # Some simulator payloads may omit timezone info; normalize to UTC.
        return dt if dt.tzinfo is not None else dt.replace(tzinfo=timezone.utc)

    @staticmethod
    def _to_order(data: dict[str, Any]) -> ExternalOrder:
        return ExternalOrder(
            order_id=data["order_id"],
            client_code=data["client_code"],
            facility_code=data["facility_code"],
            zone_code=data.get("zone_code"),
            order_type=data["order_type"],
            priority=data["priority"],
            status=data["status"],
            source_address=Address(**data["source_address"]),
            destination_address=Address(**data["destination_address"]),
            total_weight_kg=data["total_weight_kg"],
            total_volume_m3=data["total_volume_m3"],
            lines=[
                ExternalOrderLine(
                    line_number=line["line_number"],
                    sku=line["sku"],
                    description=line["description"],
                    quantity=line["quantity"],
                    uom=line["uom"],
                    unit_weight_kg=line["unit_weight_kg"],
                    unit_volume_m3=line["unit_volume_m3"],
                    hazmat_flag=line["hazmat_flag"],
                    temperature_class=line["temperature_class"],
                )
                for line in data.get("lines", [])
            ],
            created_at=ManhattanSimulatorHttpClient._parse_datetime(data["created_at"]),
            updated_at=ManhattanSimulatorHttpClient._parse_datetime(data["updated_at"]),
        )

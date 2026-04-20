from __future__ import annotations

from decimal import Decimal
from uuid import uuid4

import httpx

from finkernel.config import Settings
from finkernel.connectors.errors import BrokerConnectorError
from finkernel.schemas.control_plane import BrokerOrderSnapshot
from finkernel.schemas.trade import OrderType
from finkernel.schemas.simulation import PositionSnapshot
from finkernel.schemas.trade import BrokerExecutionResult
from finkernel.storage.models import WorkflowRequestModel


class AlpacaBrokerClient:
    broker_slug = "alpaca_paper"

    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def submit_order(self, workflow_request: WorkflowRequestModel) -> BrokerExecutionResult:
        if not self.settings.alpaca_api_key or not self.settings.alpaca_secret_key:
            raise BrokerConnectorError("AUTH_CONFIGURATION_MISSING", "Alpaca credentials are not configured.")
        if workflow_request.order_type != OrderType.LIMIT.value:
            raise BrokerConnectorError(
                "ORDER_TYPE_NOT_SUPPORTED",
                f"Alpaca adapter currently supports limit orders only, got {workflow_request.order_type}.",
            )

        payload = {
            "symbol": workflow_request.symbol,
            "qty": workflow_request.quantity,
            "side": workflow_request.side,
            "type": "limit",
            "limit_price": str(workflow_request.limit_price),
            "time_in_force": self.settings.default_time_in_force,
            "client_order_id": workflow_request.request_id,
        }
        headers = {
            "APCA-API-KEY-ID": self.settings.alpaca_api_key,
            "APCA-API-SECRET-KEY": self.settings.alpaca_secret_key,
        }
        connector_trace_id = f"alpaca-{uuid4()}"
        try:
            with httpx.Client(base_url=self.settings.alpaca_base_url, timeout=15.0, headers=headers) as client:
                response = client.post(self._orders_path(), json=payload)
                response.raise_for_status()
                body = response.json()
        except httpx.HTTPStatusError as exc:
            raise self._map_http_error(exc) from exc
        except httpx.RequestError as exc:
            raise BrokerConnectorError(
                "NETWORK_ERROR",
                "Unable to reach Alpaca.",
                response_body=str(exc),
                retryable=True,
            ) from exc
        return BrokerExecutionResult(
            broker_order_id=str(body.get("id") or workflow_request.request_id),
            status=str(body.get("status") or "accepted"),
            raw_response=body,
            connector_trace_id=connector_trace_id,
        )

    def _orders_path(self) -> str:
        normalized = self.settings.alpaca_base_url.rstrip("/")
        return "/orders" if normalized.endswith("/v2") else "/v2/orders"

    def get_order(self, *, broker_order_id: str | None = None, client_order_id: str | None = None) -> BrokerOrderSnapshot | None:
        if not self.settings.alpaca_api_key or not self.settings.alpaca_secret_key:
            raise BrokerConnectorError("AUTH_CONFIGURATION_MISSING", "Alpaca credentials are not configured.")
        if not broker_order_id and not client_order_id:
            raise BrokerConnectorError("LOOKUP_IDENTIFIERS_MISSING", "broker_order_id or client_order_id is required.")

        headers = {
            "APCA-API-KEY-ID": self.settings.alpaca_api_key,
            "APCA-API-SECRET-KEY": self.settings.alpaca_secret_key,
        }
        try:
            with httpx.Client(base_url=self.settings.alpaca_base_url, timeout=15.0, headers=headers) as client:
                response = client.get(self._lookup_path(broker_order_id=broker_order_id, client_order_id=client_order_id))
                if response.status_code == 404:
                    return None
                response.raise_for_status()
                body = response.json()
        except httpx.HTTPStatusError as exc:
            raise self._map_http_error(exc) from exc
        except httpx.RequestError as exc:
            raise BrokerConnectorError(
                "NETWORK_ERROR",
                "Unable to reach Alpaca.",
                response_body=str(exc),
                retryable=True,
            ) from exc

        return BrokerOrderSnapshot(
            broker_order_id=str(body.get("id") or broker_order_id or ""),
            client_order_id=body.get("client_order_id"),
            status=str(body.get("status") or "unknown"),
            raw_response=body,
        )

    def _lookup_path(self, *, broker_order_id: str | None, client_order_id: str | None) -> str:
        if broker_order_id:
            return f"{self._orders_path()}/{broker_order_id}"
        normalized = self.settings.alpaca_base_url.rstrip("/")
        if normalized.endswith("/v2"):
            return f"/orders:by_client_order_id?client_order_id={client_order_id}"
        return f"/v2/orders:by_client_order_id?client_order_id={client_order_id}"

    def cancel_order(self, *, broker_order_id: str) -> None:
        if not self.settings.alpaca_api_key or not self.settings.alpaca_secret_key:
            raise BrokerConnectorError("AUTH_CONFIGURATION_MISSING", "Alpaca credentials are not configured.")
        headers = {
            "APCA-API-KEY-ID": self.settings.alpaca_api_key,
            "APCA-API-SECRET-KEY": self.settings.alpaca_secret_key,
        }
        try:
            with httpx.Client(base_url=self.settings.alpaca_base_url, timeout=15.0, headers=headers) as client:
                response = client.delete(f"{self._orders_path()}/{broker_order_id}")
                response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            raise self._map_http_error(exc) from exc
        except httpx.RequestError as exc:
            raise BrokerConnectorError(
                "NETWORK_ERROR",
                "Unable to reach Alpaca.",
                response_body=str(exc),
                retryable=True,
            ) from exc

    def get_account_summary(self) -> dict:
        headers = self._auth_headers()
        try:
            with httpx.Client(base_url=self.settings.alpaca_base_url, timeout=15.0, headers=headers) as client:
                response = client.get(self._account_path())
                response.raise_for_status()
                return response.json()
        except httpx.HTTPStatusError as exc:
            raise self._map_http_error(exc) from exc
        except httpx.RequestError as exc:
            raise BrokerConnectorError(
                "NETWORK_ERROR",
                "Unable to reach Alpaca.",
                response_body=str(exc),
                retryable=True,
            ) from exc

    def list_positions(self) -> list[PositionSnapshot]:
        headers = self._auth_headers()
        try:
            with httpx.Client(base_url=self.settings.alpaca_base_url, timeout=15.0, headers=headers) as client:
                response = client.get(self._positions_path())
                response.raise_for_status()
                body = response.json()
        except httpx.HTTPStatusError as exc:
            raise self._map_http_error(exc) from exc
        except httpx.RequestError as exc:
            raise BrokerConnectorError(
                "NETWORK_ERROR",
                "Unable to reach Alpaca.",
                response_body=str(exc),
                retryable=True,
            ) from exc

        return [
            PositionSnapshot(
                symbol=item["symbol"],
                quantity=item.get("qty", "0"),
                market_value=item.get("market_value", "0"),
                cost_basis=item.get("cost_basis"),
                unrealized_pl=item.get("unrealized_pl"),
            )
            for item in body
        ]

    def get_latest_prices(self, symbols: list[str]) -> dict[str, Decimal]:
        headers = self._auth_headers()
        prices: dict[str, Decimal] = {}
        with httpx.Client(base_url=self.settings.alpaca_data_base_url, timeout=15.0, headers=headers) as client:
            for symbol in sorted({item.upper() for item in symbols if item.strip()}):
                try:
                    response = client.get(f"/v2/stocks/{symbol}/trades/latest")
                    response.raise_for_status()
                    body = response.json()
                    trade = body.get("trade") or {}
                    if "p" in trade:
                        prices[symbol] = Decimal(str(trade["p"]))
                except httpx.HTTPStatusError as exc:
                    raise self._map_http_error(exc) from exc
                except httpx.RequestError as exc:
                    raise BrokerConnectorError(
                        "NETWORK_ERROR",
                        "Unable to reach Alpaca market data.",
                        response_body=str(exc),
                        retryable=True,
                    ) from exc
        return prices

    def _map_http_error(self, exc: httpx.HTTPStatusError) -> BrokerConnectorError:
        status_code = exc.response.status_code
        try:
            body: dict | str | None = exc.response.json()
        except ValueError:
            body = exc.response.text

        if status_code in (401, 403):
            code = "AUTHENTICATION_FAILED"
            retryable = False
        elif status_code == 429:
            code = "RATE_LIMITED"
            retryable = True
        elif status_code in (400, 422):
            code = "ORDER_REJECTED"
            retryable = False
        else:
            code = "BROKER_HTTP_ERROR"
            retryable = status_code >= 500

        return BrokerConnectorError(
            code,
            f"Alpaca request failed with status {status_code}.",
            status_code=status_code,
            response_body=body,
            retryable=retryable,
        )

    def _auth_headers(self) -> dict[str, str]:
        if not self.settings.alpaca_api_key or not self.settings.alpaca_secret_key:
            raise BrokerConnectorError("AUTH_CONFIGURATION_MISSING", "Alpaca credentials are not configured.")
        return {
            "APCA-API-KEY-ID": self.settings.alpaca_api_key,
            "APCA-API-SECRET-KEY": self.settings.alpaca_secret_key,
        }

    def _account_path(self) -> str:
        normalized = self.settings.alpaca_base_url.rstrip("/")
        return "/account" if normalized.endswith("/v2") else "/v2/account"

    def _positions_path(self) -> str:
        normalized = self.settings.alpaca_base_url.rstrip("/")
        return "/positions" if normalized.endswith("/v2") else "/v2/positions"

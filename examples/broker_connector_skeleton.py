from __future__ import annotations

from decimal import Decimal

from finkernel.schemas.control_plane import BrokerOrderSnapshot
from finkernel.schemas.simulation import PositionSnapshot
from finkernel.schemas.trade import BrokerExecutionResult
from finkernel.storage.models import WorkflowRequestModel


class ExampleBrokerClient:
    broker_slug = "example_broker"

    def submit_order(self, workflow_request: WorkflowRequestModel) -> BrokerExecutionResult:
        raise NotImplementedError

    def get_order(self, *, broker_order_id: str | None = None, client_order_id: str | None = None) -> BrokerOrderSnapshot | None:
        raise NotImplementedError

    def cancel_order(self, *, broker_order_id: str) -> None:
        raise NotImplementedError

    def get_account_summary(self) -> dict:
        raise NotImplementedError

    def list_positions(self) -> list[PositionSnapshot]:
        raise NotImplementedError

    def get_latest_prices(self, symbols: list[str]) -> dict[str, Decimal]:
        raise NotImplementedError

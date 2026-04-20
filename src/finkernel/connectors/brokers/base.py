from __future__ import annotations

from decimal import Decimal
from typing import Protocol

from finkernel.schemas.control_plane import BrokerOrderSnapshot
from finkernel.schemas.simulation import PositionSnapshot
from finkernel.schemas.trade import BrokerExecutionResult
from finkernel.storage.models import WorkflowRequestModel


class BrokerAdapter(Protocol):
    broker_slug: str

    def submit_order(self, workflow_request: WorkflowRequestModel) -> BrokerExecutionResult: ...
    def get_order(self, *, broker_order_id: str | None = None, client_order_id: str | None = None) -> BrokerOrderSnapshot | None: ...
    def cancel_order(self, *, broker_order_id: str) -> None: ...
    def get_account_summary(self) -> dict: ...
    def list_positions(self) -> list[PositionSnapshot]: ...
    def get_latest_prices(self, symbols: list[str]) -> dict[str, Decimal]: ...

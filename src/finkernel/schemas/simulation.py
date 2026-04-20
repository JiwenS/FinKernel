from __future__ import annotations

from decimal import Decimal

from pydantic import BaseModel, Field


class PositionSnapshot(BaseModel):
    symbol: str
    quantity: Decimal
    market_value: Decimal
    cost_basis: Decimal | None = None
    unrealized_pl: Decimal | None = None


class PortfolioSnapshot(BaseModel):
    owner_id: str
    profile_id: str
    bucket_name: str | None = None
    account_ids: list[str]
    buying_power: Decimal
    cash: Decimal
    equity: Decimal
    positions: list[PositionSnapshot]
    open_request_count: int
    pending_notional: Decimal


class RiskSignal(BaseModel):
    code: str
    severity: str
    message: str


class RiskSummary(BaseModel):
    owner_id: str
    profile_id: str
    bucket_name: str | None = None
    risk_budget: str
    total_market_value: Decimal
    pending_notional: Decimal
    cash: Decimal
    buying_power: Decimal
    largest_position_pct: Decimal
    signals: list[RiskSignal]


class SimulatedTradeInput(BaseModel):
    account_id: str
    symbol: str
    side: str
    quantity: Decimal = Field(gt=0)
    limit_price: Decimal = Field(gt=0)
    market: str = "us_equities"


class ConstraintFinding(BaseModel):
    code: str
    status: str
    message: str


class TradeSimulationResult(BaseModel):
    owner_id: str
    profile_id: str
    simulated_only: bool = True
    symbol: str
    side: str
    quantity: Decimal
    limit_price: Decimal
    notional: Decimal
    current_position_qty: Decimal
    projected_position_qty: Decimal
    cash_before: Decimal
    projected_cash_after: Decimal
    assumptions: list[str]
    constraints: list[ConstraintFinding]


class CandidateTradeAction(BaseModel):
    owner_id: str
    profile_id: str
    candidate_only: bool = True
    requires_hitl_if_executed: bool = True
    summary: str
    rationale_basis: list[str]
    trade_template: SimulatedTradeInput
    simulation: TradeSimulationResult


class AlertFact(BaseModel):
    code: str
    severity: str
    message: str


class AlertFactList(BaseModel):
    owner_id: str
    profile_id: str
    alerts: list[AlertFact]

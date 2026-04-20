from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from enum import Enum

from pydantic import BaseModel, Field, field_validator

from finkernel.schemas.trade import OrderSide, TradeRequestResponse


class SuggestionStatus(str, Enum):
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    EXECUTED = "EXECUTED"
    EXPIRED = "EXPIRED"


class SuggestionType(str, Enum):
    TRADE_CANDIDATE = "trade_candidate"
    REBALANCE = "rebalance"
    EXIT = "exit"


class StrategyCreate(BaseModel):
    name: str = Field(min_length=1, max_length=128)
    mandate_summary: str = Field(min_length=1, max_length=1024)
    budget: Decimal | None = Field(default=None, gt=0)
    target_allocation: dict[str, Decimal] = Field(min_length=1)
    rebalance_threshold_pct: Decimal = Field(default=Decimal("0.05"), gt=0, le=1)
    active: bool = True

    @field_validator("target_allocation")
    @classmethod
    def normalize_target_allocation(cls, value: dict[str, Decimal]) -> dict[str, Decimal]:
        normalized = {symbol.strip().upper(): Decimal(str(weight)) for symbol, weight in value.items()}
        total = sum(normalized.values())
        if total <= 0:
            raise ValueError("target_allocation must contain a positive total weight.")
        return normalized


class StrategyFromTextCreate(BaseModel):
    text: str = Field(min_length=1, max_length=4000)
    auto_activate: bool = True


class StrategyInterpretation(BaseModel):
    detected_style: str
    detected_budget: Decimal | None = None
    selected_symbols: list[str]
    target_allocation: dict[str, Decimal]
    rebalance_threshold_pct: Decimal
    parser_notes: list[str]


class StrategyResponse(BaseModel):
    strategy_id: str
    owner_id: str
    profile_id: str
    profile_version: int
    name: str
    mandate_summary: str
    budget: Decimal | None = None
    target_allocation: dict[str, Decimal]
    rebalance_threshold_pct: Decimal
    active: bool
    created_at: datetime
    updated_at: datetime


class StrategyFromTextResponse(BaseModel):
    strategy: StrategyResponse
    interpretation: StrategyInterpretation


class SuggestedTradeAction(BaseModel):
    symbol: str
    side: OrderSide
    quantity: int = Field(gt=0)
    limit_price: Decimal = Field(gt=0)
    weight_delta_pct: Decimal | None = None


class SuggestionResponse(BaseModel):
    suggestion_id: str
    strategy_id: str | None = None
    workflow_request_id: str | None = None
    owner_id: str
    profile_id: str
    profile_version: int
    suggestion_type: SuggestionType
    status: SuggestionStatus
    summary: str
    rationale: str
    actions: list[SuggestedTradeAction]
    context_payload: dict | None = None
    expires_at: datetime | None = None
    created_at: datetime
    updated_at: datetime
    workflow_request: TradeRequestResponse | None = None


class AdvisorRunResult(BaseModel):
    profile_id: str
    strategy_id: str
    created_suggestion_id: str | None = None
    skipped_reason: str | None = None


class AdvisorRunResponse(BaseModel):
    results: list[AdvisorRunResult]
    total_strategies: int
    created_suggestions: int

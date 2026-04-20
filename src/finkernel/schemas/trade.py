from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from enum import Enum

from pydantic import BaseModel, Field, field_validator

from .identity import ActorContext
from .policy import PolicyDecision, PolicyDecisionType


class OrderSide(str, Enum):
    BUY = "buy"
    SELL = "sell"


class OrderType(str, Enum):
    LIMIT = "limit"
    MARKET = "market"
    STOP = "stop"
    STOP_LIMIT = "stop_limit"
    BRACKET = "bracket"
    TRAILING_STOP = "trailing_stop"


class SupportedMarket(str, Enum):
    US_EQUITIES = "us_equities"


class SupportedBroker(str, Enum):
    ALPACA_PAPER = "alpaca_paper"


class TradeRequestCreate(BaseModel):
    actor: ActorContext
    symbol: str = Field(min_length=1, max_length=16)
    side: OrderSide
    quantity: int = Field(gt=0, le=1000000)
    limit_price: Decimal = Field(gt=0)
    order_type: OrderType = OrderType.LIMIT
    stop_price: Decimal | None = Field(default=None, gt=0)
    take_profit: Decimal | None = Field(default=None, gt=0)
    stop_loss: Decimal | None = Field(default=None, gt=0)
    trail_percent: Decimal | None = Field(default=None, gt=0)
    trail_price: Decimal | None = Field(default=None, gt=0)
    market: SupportedMarket = SupportedMarket.US_EQUITIES
    broker: SupportedBroker = SupportedBroker.ALPACA_PAPER
    idempotency_key: str | None = Field(default=None, max_length=128)
    notes: str | None = Field(default=None, max_length=512)

    @field_validator("symbol")
    @classmethod
    def uppercase_symbol(cls, value: str) -> str:
        return value.strip().upper()


class BrokerExecutionResult(BaseModel):
    broker_order_id: str
    status: str
    raw_response: dict
    connector_trace_id: str | None = None


class TradeRequestResponse(BaseModel):
    request_id: str
    owner_id: str | None = None
    profile_id: str | None = None
    profile_version: int | None = None
    state: str
    symbol: str
    side: OrderSide
    quantity: int
    limit_price: Decimal
    order_type: OrderType
    stop_price: Decimal | None = None
    take_profit: Decimal | None = None
    stop_loss: Decimal | None = None
    trail_percent: Decimal | None = None
    trail_price: Decimal | None = None
    market: SupportedMarket
    broker: SupportedBroker
    policy_decision: PolicyDecisionType | None = None
    policy_reason_code: str | None = None
    policy_explanation: str | None = None
    request_source: str | None = None
    broker_order_id: str | None = None
    broker_status: str | None = None
    last_error_code: str | None = None
    last_error: str | None = None
    idempotency_key: str | None = None
    created_at: datetime
    updated_at: datetime


class TradeRequestEnvelope(BaseModel):
    trade_request: TradeRequestCreate
    policy_decision: PolicyDecision | None = None

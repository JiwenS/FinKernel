from __future__ import annotations

from enum import Enum

from pydantic import BaseModel


class PolicyDecisionType(str, Enum):
    ALLOW = "ALLOW"
    FILTER = "FILTER"
    BLOCK = "BLOCK"
    REQUIRE_CONFIRMATION = "REQUIRE_CONFIRMATION"


class PolicyReasonCode(str, Enum):
    REQUIRES_CONFIRMATION = "REQUIRES_CONFIRMATION"
    UNSUPPORTED_ORDER_TYPE = "UNSUPPORTED_ORDER_TYPE"
    BROKER_NOT_ALLOWED = "BROKER_NOT_ALLOWED"
    MARKET_NOT_ALLOWED = "MARKET_NOT_ALLOWED"
    SYMBOL_NOT_ALLOWED = "SYMBOL_NOT_ALLOWED"
    LIMIT_PRICE_REQUIRED = "LIMIT_PRICE_REQUIRED"
    LIMIT_EXCEEDED = "LIMIT_EXCEEDED"
    QTY_EXCEEDED = "QTY_EXCEEDED"
    MISSING_IDENTITY = "MISSING_IDENTITY"


class PolicyDecision(BaseModel):
    decision: PolicyDecisionType
    reason_code: PolicyReasonCode
    explanation: str
    filtered_scope: dict[str, str] | None = None

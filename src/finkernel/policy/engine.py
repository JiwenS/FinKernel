from __future__ import annotations

from decimal import Decimal

from finkernel.config import Settings
from finkernel.schemas.policy import PolicyDecision, PolicyDecisionType, PolicyReasonCode
from finkernel.schemas.trade import OrderType, SupportedBroker, SupportedMarket, TradeRequestCreate


class PolicyEngine:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def evaluate_trade_request(self, trade_request: TradeRequestCreate) -> PolicyDecision:
        actor = trade_request.actor
        if not actor.user_id or not actor.account_id:
            return PolicyDecision(
                decision=PolicyDecisionType.BLOCK,
                reason_code=PolicyReasonCode.MISSING_IDENTITY,
                explanation="A user_id and account_id are required for executable requests.",
            )

        if trade_request.order_type is not OrderType.LIMIT:
            return PolicyDecision(
                decision=PolicyDecisionType.BLOCK,
                reason_code=PolicyReasonCode.UNSUPPORTED_ORDER_TYPE,
                explanation="FinKernel V1 only supports limit orders.",
            )

        if trade_request.broker is not SupportedBroker.ALPACA_PAPER:
            return PolicyDecision(
                decision=PolicyDecisionType.BLOCK,
                reason_code=PolicyReasonCode.BROKER_NOT_ALLOWED,
                explanation="FinKernel V1 only supports Alpaca paper trading.",
            )

        if trade_request.market is not SupportedMarket.US_EQUITIES:
            return PolicyDecision(
                decision=PolicyDecisionType.BLOCK,
                reason_code=PolicyReasonCode.MARKET_NOT_ALLOWED,
                explanation="FinKernel V1 only supports US equities.",
            )

        if trade_request.symbol not in self.settings.allowed_symbols:
            return PolicyDecision(
                decision=PolicyDecisionType.BLOCK,
                reason_code=PolicyReasonCode.SYMBOL_NOT_ALLOWED,
                explanation=f"Symbol {trade_request.symbol} is outside the configured allowlist.",
                filtered_scope={"allowed_symbols": ",".join(sorted(self.settings.allowed_symbols))},
            )

        if trade_request.quantity > self.settings.max_limit_order_qty:
            return PolicyDecision(
                decision=PolicyDecisionType.BLOCK,
                reason_code=PolicyReasonCode.QTY_EXCEEDED,
                explanation=f"Quantity exceeds the configured maximum of {self.settings.max_limit_order_qty}.",
            )

        notional = Decimal(trade_request.quantity) * trade_request.limit_price
        if float(notional) > self.settings.max_limit_order_notional:
            return PolicyDecision(
                decision=PolicyDecisionType.BLOCK,
                reason_code=PolicyReasonCode.LIMIT_EXCEEDED,
                explanation=f"Order notional exceeds the configured maximum of {self.settings.max_limit_order_notional}.",
            )

        return PolicyDecision(
            decision=PolicyDecisionType.REQUIRE_CONFIRMATION,
            reason_code=PolicyReasonCode.REQUIRES_CONFIRMATION,
            explanation="Executable orders require human approval before broker submission.",
        )

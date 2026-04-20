from __future__ import annotations

from decimal import Decimal

from finkernel.services.interfaces import BrokerClient


class MarketDataService:
    def __init__(self, broker_client: BrokerClient) -> None:
        self.broker_client = broker_client

    def get_latest_prices(self, symbols: list[str]) -> dict[str, Decimal]:
        normalized = [symbol.upper() for symbol in symbols if symbol.strip()]
        prices = self.broker_client.get_latest_prices(normalized)
        if len(prices) == len(set(normalized)):
            return prices

        fallback_prices = prices.copy()
        for position in self.broker_client.list_positions():
            if position.symbol in normalized and position.quantity > 0 and position.symbol not in fallback_prices:
                fallback_prices[position.symbol] = (position.market_value / position.quantity).quantize(Decimal("0.01"))
        return fallback_prices

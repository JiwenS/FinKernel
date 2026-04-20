from __future__ import annotations

from decimal import Decimal

from pydantic import BaseModel

from .trade import OrderSide


class DiscordConfirmationMessage(BaseModel):
    request_id: str
    symbol: str
    side: OrderSide
    quantity: int
    limit_price: Decimal
    request_source: str | None = None
    notes_excerpt: str | None = None
    confirmation_token: str
    approve_command: str
    reject_command: str

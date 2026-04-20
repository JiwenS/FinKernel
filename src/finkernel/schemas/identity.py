from __future__ import annotations

from pydantic import BaseModel, Field


class ActorContext(BaseModel):
    user_id: str = Field(min_length=1)
    account_id: str = Field(min_length=1)
    session_id: str | None = None

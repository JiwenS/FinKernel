from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


class AuditEvent(BaseModel):
    workflow_request_id: str | None = None
    profile_id: str | None = None
    profile_version: int | None = None
    event_type: str
    actor_type: str
    actor_id: str | None = None
    state: str | None = None
    decision: str | None = None
    reason_code: str | None = None
    message: str
    payload: dict | None = None
    created_at: datetime

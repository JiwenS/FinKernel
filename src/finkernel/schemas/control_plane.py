from __future__ import annotations

from datetime import datetime
from enum import Enum

from pydantic import BaseModel

from .trade import TradeRequestResponse


class ReconciliationStatus(str, Enum):
    MATCHED = "MATCHED"
    DRIFTED = "DRIFTED"
    NOT_FOUND = "NOT_FOUND"
    BROKER_ERROR = "BROKER_ERROR"
    SKIPPED = "SKIPPED"


class BrokerOrderSnapshot(BaseModel):
    broker_order_id: str
    client_order_id: str | None = None
    status: str
    raw_response: dict


class ReconciliationResult(BaseModel):
    request_id: str
    local_state_before: str
    local_state_after: str
    reconciliation_status: ReconciliationStatus
    reconciliation_reason: str
    broker_order_id: str | None = None
    broker_status: str | None = None
    request_source: str | None = None
    reconciled_at: datetime


class WorkflowRequestSummary(TradeRequestResponse):
    reconciliation_status: str | None = None
    reconciliation_reason: str | None = None
    last_reconciled_at: datetime | None = None
    is_terminal: bool
    is_cancelable: bool


class WorkflowRequestListResponse(BaseModel):
    items: list[WorkflowRequestSummary]
    total: int


class AuditEventResponse(BaseModel):
    id: int
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


class AuditEventListResponse(BaseModel):
    items: list[AuditEventResponse]
    total: int

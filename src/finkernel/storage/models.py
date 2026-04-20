from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from typing import Any
from uuid import uuid4

from sqlalchemy import JSON, DateTime, ForeignKey, Integer, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .database import Base


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class WorkflowRequestModel(Base):
    __tablename__ = "workflow_requests"

    request_id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    user_id: Mapped[str] = mapped_column(String(64), nullable=False)
    account_id: Mapped[str] = mapped_column(String(64), nullable=False)
    owner_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    profile_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    profile_version: Mapped[int | None] = mapped_column(Integer, nullable=True)
    session_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    symbol: Mapped[str] = mapped_column(String(16), nullable=False)
    side: Mapped[str] = mapped_column(String(8), nullable=False)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    limit_price: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    order_type: Mapped[str] = mapped_column(String(16), nullable=False)
    market: Mapped[str] = mapped_column(String(32), nullable=False)
    broker: Mapped[str] = mapped_column(String(32), nullable=False)
    state: Mapped[str] = mapped_column(String(32), nullable=False)
    request_source: Mapped[str | None] = mapped_column(String(128), nullable=True)
    idempotency_key: Mapped[str | None] = mapped_column(String(128), nullable=True, unique=True)
    confirmation_token: Mapped[str | None] = mapped_column(String(128), nullable=True, unique=True)
    policy_decision: Mapped[str | None] = mapped_column(String(32), nullable=True)
    policy_reason_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    policy_explanation: Mapped[str | None] = mapped_column(Text, nullable=True)
    broker_order_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    broker_status: Mapped[str | None] = mapped_column(String(64), nullable=True)
    connector_trace_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    last_error_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    reconciliation_status: Mapped[str | None] = mapped_column(String(32), nullable=True)
    reconciliation_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    last_reconciled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False)

    audit_events: Mapped[list["AuditEventModel"]] = relationship(back_populates="workflow_request", cascade="all, delete-orphan")


class AuditEventModel(Base):
    __tablename__ = "audit_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    workflow_request_id: Mapped[str | None] = mapped_column(ForeignKey("workflow_requests.request_id"), nullable=True)
    profile_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    profile_version: Mapped[int | None] = mapped_column(Integer, nullable=True)
    event_type: Mapped[str] = mapped_column(String(64), nullable=False)
    actor_type: Mapped[str] = mapped_column(String(32), nullable=False)
    actor_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    state: Mapped[str | None] = mapped_column(String(32), nullable=True)
    decision: Mapped[str | None] = mapped_column(String(32), nullable=True)
    reason_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    payload: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)

    workflow_request: Mapped[WorkflowRequestModel | None] = relationship(back_populates="audit_events")


class ProfileVersionModel(Base):
    __tablename__ = "profile_versions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    profile_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    owner_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    display_name: Mapped[str] = mapped_column(String(128), nullable=False)
    mandate_summary: Mapped[str] = mapped_column(Text, nullable=False)
    persona_style: Mapped[str] = mapped_column(String(128), nullable=False)
    created_from: Mapped[str | None] = mapped_column(String(64), nullable=True)
    bucket_name: Mapped[str | None] = mapped_column(String(128), nullable=True)
    supersedes_profile_version: Mapped[int | None] = mapped_column(Integer, nullable=True)
    risk_budget: Mapped[str] = mapped_column(String(32), nullable=False)
    capital_allocation_pct: Mapped[Decimal] = mapped_column(Numeric(10, 6), nullable=False)
    allowed_accounts: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    allowed_markets: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    allowed_symbols: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    forbidden_symbols: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    allowed_actions: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    hitl_required_actions: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    objective_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    horizon_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    liquidity_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    stress_response_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    loss_threshold_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    constraints_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    concentration_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    interaction_style_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    review_cadence_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    payload: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False)


class ProfileContextualRuleModel(Base):
    __tablename__ = "profile_contextual_rules"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    profile_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    profile_version: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    rule_text: Mapped[str] = mapped_column(Text, nullable=False)
    reason_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    confidence: Mapped[str | None] = mapped_column(String(32), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)


class ProfileLongMemoryModel(Base):
    __tablename__ = "profile_long_memories"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    profile_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    profile_version: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    theme: Mapped[str | None] = mapped_column(String(64), nullable=True)
    content_text: Mapped[str] = mapped_column(Text, nullable=False)
    source_dimension: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    last_confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class ProfileShortMemoryModel(Base):
    __tablename__ = "profile_short_memories"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    profile_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    profile_version: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    theme: Mapped[str | None] = mapped_column(String(64), nullable=True)
    content_text: Mapped[str] = mapped_column(Text, nullable=False)
    source_dimension: Mapped[str | None] = mapped_column(String(64), nullable=True)
    effective_from: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)


class DiscoverySessionModel(Base):
    __tablename__ = "profile_discovery_sessions"

    session_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    owner_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    payload: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False)


class ProfileDraftModel(Base):
    __tablename__ = "profile_drafts"

    draft_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    session_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    owner_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    payload: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False)


class StrategyModel(Base):
    __tablename__ = "strategies"

    strategy_id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    owner_id: Mapped[str] = mapped_column(String(64), nullable=False)
    profile_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    profile_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    mandate_summary: Mapped[str] = mapped_column(Text, nullable=False)
    budget: Mapped[Decimal | None] = mapped_column(Numeric(18, 6), nullable=True)
    target_allocation: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    rebalance_threshold_pct: Mapped[Decimal] = mapped_column(Numeric(10, 6), nullable=False, default=Decimal("0.05"))
    active: Mapped[bool] = mapped_column(nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False)


class SuggestionModel(Base):
    __tablename__ = "suggestions"

    suggestion_id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    strategy_id: Mapped[str | None] = mapped_column(ForeignKey("strategies.strategy_id"), nullable=True, index=True)
    workflow_request_id: Mapped[str | None] = mapped_column(ForeignKey("workflow_requests.request_id"), nullable=True, index=True)
    owner_id: Mapped[str] = mapped_column(String(64), nullable=False)
    profile_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    profile_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    suggestion_type: Mapped[str] = mapped_column(String(32), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    rationale: Mapped[str] = mapped_column(Text, nullable=False)
    actions: Mapped[list[dict[str, Any]]] = mapped_column(JSON, nullable=False)
    context_payload: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False)

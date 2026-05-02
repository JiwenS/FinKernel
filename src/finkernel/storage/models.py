from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy import JSON, DateTime, Integer, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from .database import Base


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


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
    supersedes_profile_version: Mapped[int | None] = mapped_column(Integer, nullable=True)
    risk_budget: Mapped[str] = mapped_column(String(32), nullable=False)
    forbidden_symbols: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    objective_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    horizon_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    liquidity_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    stress_response_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    loss_threshold_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    constraints_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    concentration_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    interaction_style_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    review_cadence_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    target_annual_return_pct: Mapped[float | None] = mapped_column(Numeric(18, 4), nullable=True)
    investment_horizon_years: Mapped[int | None] = mapped_column(Integer, nullable=True)
    annual_liquidity_need: Mapped[float | None] = mapped_column(Numeric(18, 2), nullable=True)
    liquidity_frequency: Mapped[str | None] = mapped_column(String(32), nullable=True)
    max_drawdown_limit_pct: Mapped[float | None] = mapped_column(Numeric(18, 4), nullable=True)
    max_annual_volatility_pct: Mapped[float | None] = mapped_column(Numeric(18, 4), nullable=True)
    max_leverage_ratio: Mapped[float | None] = mapped_column(Numeric(18, 4), nullable=True)
    single_asset_cap_pct: Mapped[float | None] = mapped_column(Numeric(18, 4), nullable=True)
    blocked_sectors: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    blocked_tickers: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    base_currency: Mapped[str | None] = mapped_column(String(16), nullable=True)
    tax_residency: Mapped[str | None] = mapped_column(String(64), nullable=True)
    account_entity_type: Mapped[str | None] = mapped_column(String(32), nullable=True)
    aum_allocated: Mapped[float | None] = mapped_column(Numeric(18, 2), nullable=True)
    execution_mode: Mapped[str | None] = mapped_column(String(32), nullable=True)
    financial_literacy_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    wealth_origin_dna_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    behavioral_risk_profile_text: Mapped[str | None] = mapped_column(Text, nullable=True)
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


class DiscoveryConversationTurnModel(Base):
    __tablename__ = "profile_discovery_turns"

    turn_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    session_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    owner_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    section: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    payload: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    answered_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)


class DiscoveryInterpretationModel(Base):
    __tablename__ = "profile_discovery_interpretations"

    interpretation_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    session_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    owner_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    section: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    payload: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    stored_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)


class ProfileDraftModel(Base):
    __tablename__ = "profile_drafts"

    draft_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    session_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    owner_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    payload: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False)

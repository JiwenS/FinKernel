from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class ProfileAction(str, Enum):
    OBSERVE = "observe"
    SIMULATE = "simulate"
    REQUEST_EXECUTION = "request_execution"
    REFRESH = "refresh"
    RECONCILE = "reconcile"
    CANCEL = "cancel"


class RiskBudget(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class ProfileLifecycleStatus(str, Enum):
    DRAFT = "draft"
    DISCOVERY_IN_PROGRESS = "discovery_in_progress"
    PENDING_USER_CONFIRMATION = "pending_user_confirmation"
    ACTIVE = "active"
    UNDER_REVIEW = "under_review"
    SUPERSEDED = "superseded"
    ARCHIVED = "archived"


class MemoryKind(str, Enum):
    LONG_TERM = "long_term"
    SHORT_TERM = "short_term"


class PersonaProfile(BaseModel):
    profile_id: str = Field(min_length=1)
    owner_id: str = Field(min_length=1)
    version: int = Field(default=1, ge=1)
    status: ProfileLifecycleStatus = ProfileLifecycleStatus.ACTIVE
    display_name: str = Field(min_length=1)
    mandate_summary: str = Field(min_length=1)
    persona_style: str = Field(min_length=1)
    created_from: str | None = None
    supersedes_profile_version: int | None = Field(default=None, ge=1)
    bucket_name: str | None = None
    risk_budget: RiskBudget
    capital_allocation_pct: Decimal = Field(gt=0, le=1)
    allowed_accounts: list[str] = Field(min_length=1)
    allowed_markets: list[str] = Field(default_factory=list)
    allowed_symbols: list[str] = Field(default_factory=list)
    forbidden_symbols: list[str] = Field(default_factory=list)
    allowed_actions: list[ProfileAction] = Field(default_factory=list)
    hitl_required_actions: list[ProfileAction] = Field(default_factory=list)
    hard_rules: dict[str, Any] = Field(default_factory=dict)
    contextual_rules: list[dict[str, Any]] = Field(default_factory=list)
    long_term_memories: list[dict[str, Any]] = Field(default_factory=list)
    short_term_memories: list[dict[str, Any]] = Field(default_factory=list)
    persona_evidence: list[dict[str, Any]] = Field(default_factory=list)
    persona_markdown: str | None = None

    def allows_account(self, account_id: str) -> bool:
        return account_id in self.allowed_accounts

    def allows_market(self, market: str) -> bool:
        return not self.allowed_markets or market in self.allowed_markets

    def allows_symbol(self, symbol: str) -> bool:
        normalized = symbol.upper()
        if normalized in {s.upper() for s in self.forbidden_symbols}:
            return False
        if not self.allowed_symbols:
            return True
        return normalized in {s.upper() for s in self.allowed_symbols}

    def allows_action(self, action: ProfileAction) -> bool:
        return action in self.allowed_actions

    @property
    def is_active(self) -> bool:
        return self.status is ProfileLifecycleStatus.ACTIVE


class ProfileOnboardingStatus(BaseModel):
    owner_id: str | None = None
    onboarding_required: bool
    total_profile_count: int
    active_profile_count: int
    active_profile_ids: list[str] = Field(default_factory=list)
    available_profile_ids: list[str] = Field(default_factory=list)
    next_step: str


class AppendProfileMemoryRequest(BaseModel):
    memory_kind: MemoryKind
    theme: str = Field(min_length=1)
    content_text: str = Field(min_length=1)
    source_dimension: str | None = None
    expires_at: datetime | None = None


class ProfileMemorySearchResponse(BaseModel):
    items: list[dict[str, Any]] = Field(default_factory=list)


class DistilledProfileMemoryResponse(BaseModel):
    profile_id: str
    version: int
    long_term_summary: list[str] = Field(default_factory=list)
    short_term_summary: list[str] = Field(default_factory=list)


class SavePersonaMarkdownRequest(BaseModel):
    persona_markdown: str = Field(min_length=1)
    version: int | None = Field(default=None, ge=1)


class PersonaSourcePacket(BaseModel):
    profile_id: str
    version: int
    display_name: str
    mandate_summary: str
    persona_markdown: str | None = None
    persona_evidence: list[dict[str, Any]] = Field(default_factory=list)
    long_term_memories: list[dict[str, Any]] = Field(default_factory=list)
    short_term_memories: list[dict[str, Any]] = Field(default_factory=list)
    contextual_rules: list[dict[str, Any]] = Field(default_factory=list)

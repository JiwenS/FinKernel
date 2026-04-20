from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


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
    risk_budget: RiskBudget
    forbidden_symbols: list[str] = Field(default_factory=list)
    hard_rules: dict[str, Any] = Field(default_factory=dict)
    contextual_rules: list[dict[str, Any]] = Field(default_factory=list)
    long_term_memories: list[dict[str, Any]] = Field(default_factory=list)
    short_term_memories: list[dict[str, Any]] = Field(default_factory=list)
    persona_evidence: list[dict[str, Any]] = Field(default_factory=list)
    persona_markdown: str | None = None

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


class RiskProfileSummary(BaseModel):
    profile_id: str
    owner_id: str
    version: int
    display_name: str
    mandate_summary: str
    risk_budget: RiskBudget
    objective: str | None = None
    time_horizon: str | None = None
    liquidity_needs: str | None = None
    stress_response: str | None = None
    loss_threshold: str | None = None
    concentration_guidance: str | None = None
    interaction_style: str | None = None
    review_cadence: str | None = None
    hard_constraints: list[str] = Field(default_factory=list)
    contextual_rule_highlights: list[str] = Field(default_factory=list)
    long_term_memory_highlights: list[str] = Field(default_factory=list)
    short_term_memory_highlights: list[str] = Field(default_factory=list)


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

from __future__ import annotations

from decimal import Decimal
from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class RiskBudget(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class LiquidityFrequency(str, Enum):
    NONE = "none"
    MONTHLY = "monthly"
    QUARTERLY = "quarterly"
    ANNUAL = "annual"


class AccountEntityType(str, Enum):
    INDIVIDUAL = "individual"
    TRUST = "trust"
    CORPORATE = "corporate"


class ExecutionMode(str, Enum):
    DISCRETIONARY = "discretionary"
    ADVISORY = "advisory"


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


class FinancialObjectives(BaseModel):
    target_annual_return_pct: Decimal | None = Field(default=None, ge=0)
    investment_horizon_years: int | None = Field(default=None, ge=0)
    annual_liquidity_need: Decimal | None = Field(default=None, ge=0)
    liquidity_frequency: LiquidityFrequency | None = None


class RiskBoundaries(BaseModel):
    max_drawdown_limit_pct: Decimal | None = Field(default=None, ge=0, le=100)
    max_annual_volatility_pct: Decimal | None = Field(default=None, ge=0, le=100)
    max_leverage_ratio: Decimal | None = Field(default=None, ge=0)
    single_asset_cap_pct: Decimal | None = Field(default=None, ge=0, le=100)


class InvestmentConstraints(BaseModel):
    blocked_sectors: list[str] = Field(default_factory=list)
    blocked_tickers: list[str] = Field(default_factory=list)
    base_currency: str | None = None
    tax_residency: str | None = None


class AccountBackground(BaseModel):
    account_entity_type: AccountEntityType | None = None
    aum_allocated: Decimal | None = Field(default=None, ge=0)
    execution_mode: ExecutionMode | None = None


class PersonaTraits(BaseModel):
    financial_literacy: str | None = None
    wealth_origin_dna: str | None = None
    behavioral_risk_profile: str | None = None


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
    financial_objectives: FinancialObjectives = Field(default_factory=FinancialObjectives)
    risk_boundaries: RiskBoundaries = Field(default_factory=RiskBoundaries)
    investment_constraints: InvestmentConstraints = Field(default_factory=InvestmentConstraints)
    account_background: AccountBackground = Field(default_factory=AccountBackground)
    persona_traits: PersonaTraits = Field(default_factory=PersonaTraits)
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
    persona_style: str
    target_annual_return_pct: Decimal | None = None
    investment_horizon_years: int | None = None
    annual_liquidity_need: Decimal | None = None
    liquidity_frequency: LiquidityFrequency | None = None
    max_drawdown_limit_pct: Decimal | None = None
    max_annual_volatility_pct: Decimal | None = None
    max_leverage_ratio: Decimal | None = None
    single_asset_cap_pct: Decimal | None = None
    blocked_sectors: list[str] = Field(default_factory=list)
    blocked_tickers: list[str] = Field(default_factory=list)
    base_currency: str | None = None
    tax_residency: str | None = None
    account_entity_type: AccountEntityType | None = None
    aum_allocated: Decimal | None = None
    execution_mode: ExecutionMode | None = None
    financial_literacy: str | None = None
    wealth_origin_dna: str | None = None
    behavioral_risk_profile: str | None = None
    contextual_rule_highlights: list[str] = Field(default_factory=list)
    long_term_memory_highlights: list[str] = Field(default_factory=list)
    short_term_memory_highlights: list[str] = Field(default_factory=list)


class SavePersonaMarkdownRequest(BaseModel):
    persona_markdown: str = Field(min_length=1)
    version: int | None = Field(default=None, ge=1)


class SaveProfileMarkdownRequest(BaseModel):
    profile_markdown: str = Field(min_length=1)
    version: int | None = Field(default=None, ge=1)


class PersonaSourcePacket(BaseModel):
    profile_id: str
    version: int
    display_name: str
    mandate_summary: str
    persona_style: str
    risk_budget: RiskBudget
    financial_objectives: FinancialObjectives = Field(default_factory=FinancialObjectives)
    risk_boundaries: RiskBoundaries = Field(default_factory=RiskBoundaries)
    investment_constraints: InvestmentConstraints = Field(default_factory=InvestmentConstraints)
    account_background: AccountBackground = Field(default_factory=AccountBackground)
    persona_traits: PersonaTraits = Field(default_factory=PersonaTraits)
    persona_markdown: str | None = None
    persona_evidence: list[dict[str, Any]] = Field(default_factory=list)
    long_term_memories: list[dict[str, Any]] = Field(default_factory=list)
    short_term_memories: list[dict[str, Any]] = Field(default_factory=list)
    contextual_rules: list[dict[str, Any]] = Field(default_factory=list)

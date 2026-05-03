from __future__ import annotations

from datetime import UTC, datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field, model_validator

from finkernel.schemas.profile import (
    AccountBackground,
    FinancialObjectives,
    InvestmentConstraints,
    PersonaProfile,
    PersonaTraits,
    RiskBoundaries,
)


class DiscoverySessionStatus(str, Enum):
    DISCOVERY_IN_PROGRESS = "discovery_in_progress"
    DRAFT_READY = "draft_ready"
    COMPLETED = "completed"


class DiscoveryWorkflowKind(str, Enum):
    ADD = "add"
    UPDATE = "update"


class DiscoveryPillar(str, Enum):
    FINANCIAL_OBJECTIVES = "financial_objectives"
    RISK = "risk"
    CONSTRAINTS = "constraints"
    BACKGROUND = "background"


class DiscoveryDimension(str, Enum):
    TARGET_ANNUAL_RETURN = "target_annual_return"
    INVESTMENT_HORIZON = "investment_horizon"
    ANNUAL_LIQUIDITY_NEED = "annual_liquidity_need"
    LIQUIDITY_FREQUENCY = "liquidity_frequency"
    MAX_DRAWDOWN_LIMIT = "max_drawdown_limit"
    MAX_ANNUAL_VOLATILITY = "max_annual_volatility"
    MAX_LEVERAGE_RATIO = "max_leverage_ratio"
    SINGLE_ASSET_CAP = "single_asset_cap"
    BLOCKED_SECTORS = "blocked_sectors"
    BLOCKED_TICKERS = "blocked_tickers"
    BASE_CURRENCY = "base_currency"
    TAX_RESIDENCY = "tax_residency"
    ACCOUNT_ENTITY_TYPE = "account_entity_type"
    AUM_ALLOCATED = "aum_allocated"
    EXECUTION_MODE = "execution_mode"
    FINANCIAL_LITERACY = "financial_literacy"
    WEALTH_ORIGIN_DNA = "wealth_origin_dna"
    BEHAVIORAL_RISK_PROFILE = "behavioral_risk_profile"


PILLAR_DIMENSIONS: dict["DiscoveryPillar", list["DiscoveryDimension"]] = {
    DiscoveryPillar.FINANCIAL_OBJECTIVES: [
        DiscoveryDimension.TARGET_ANNUAL_RETURN,
        DiscoveryDimension.INVESTMENT_HORIZON,
        DiscoveryDimension.ANNUAL_LIQUIDITY_NEED,
        DiscoveryDimension.LIQUIDITY_FREQUENCY,
    ],
    DiscoveryPillar.RISK: [
        DiscoveryDimension.MAX_DRAWDOWN_LIMIT,
        DiscoveryDimension.MAX_ANNUAL_VOLATILITY,
        DiscoveryDimension.MAX_LEVERAGE_RATIO,
        DiscoveryDimension.SINGLE_ASSET_CAP,
    ],
    DiscoveryPillar.CONSTRAINTS: [
        DiscoveryDimension.BLOCKED_SECTORS,
        DiscoveryDimension.BLOCKED_TICKERS,
        DiscoveryDimension.BASE_CURRENCY,
        DiscoveryDimension.TAX_RESIDENCY,
    ],
    DiscoveryPillar.BACKGROUND: [
        DiscoveryDimension.ACCOUNT_ENTITY_TYPE,
        DiscoveryDimension.AUM_ALLOCATED,
        DiscoveryDimension.EXECUTION_MODE,
        DiscoveryDimension.FINANCIAL_LITERACY,
        DiscoveryDimension.WEALTH_ORIGIN_DNA,
        DiscoveryDimension.BEHAVIORAL_RISK_PROFILE,
    ],
}

DIMENSION_TO_PILLAR: dict["DiscoveryDimension", "DiscoveryPillar"] = {
    dimension: pillar
    for pillar, dimensions in PILLAR_DIMENSIONS.items()
    for dimension in dimensions
}

ALL_REQUIRED_DIMENSIONS: list["DiscoveryDimension"] = [
    dimension
    for pillar in DiscoveryPillar
    for dimension in PILLAR_DIMENSIONS[pillar]
]


class DiscoveryQuestionType(str, Enum):
    STARTER = "starter"
    CLARIFICATION = "clarification"
    DEEPENING = "deepening"
    CONFLICT_RESOLUTION = "conflict_resolution"
    COVERAGE_RECOVERY = "coverage_recovery"


class DiscoveryQuestionSource(str, Enum):
    STARTER_BANK = "starter_bank"
    RULE_TRIGGER = "rule_trigger"
    MODEL_GENERATED = "model_generated"
    COVERAGE_GAP = "coverage_gap"


class ExpectedAnswerShape(str, Enum):
    OPEN_TEXT = "open_text"
    NUMBER = "number"
    CHOICE = "choice"
    DATE_OR_WINDOW = "date_or_window"
    MONEY_RANGE = "money_range"
    LIST = "list"


class DiscoveryQuestion(BaseModel):
    question_id: str
    session_id: str
    dimension: DiscoveryDimension
    pillar: DiscoveryPillar
    question_type: DiscoveryQuestionType
    source_type: DiscoveryQuestionSource
    prompt_text: str
    why_this_matters: str
    expected_answer_shape: ExpectedAnswerShape = ExpectedAnswerShape.OPEN_TEXT
    priority_score: int = 0
    trigger_context: dict[str, str] = Field(default_factory=dict)
    generated_from_answer_id: str | None = None
    stop_condition_target: str | None = None
    asked_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class DimensionState(BaseModel):
    dimension: DiscoveryDimension
    coverage_score: int = Field(default=0, ge=0, le=3)
    confidence_score: int = Field(default=0, ge=0, le=3)
    evidence_score: int = Field(default=0, ge=0, le=3)
    depth_score: int = Field(default=0, ge=0, le=3)
    conflict_flag: bool = False
    last_updated_at: datetime | None = None
    extracted_facts: list[str] = Field(default_factory=list)
    pending_gaps: list[str] = Field(default_factory=list)
    normalized_value: Any | None = None


class DraftReadinessAssessment(BaseModel):
    ready: bool
    unmet_dimensions: list[DiscoveryDimension] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)


class ConfidenceLabel(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class EvidenceQualityLabel(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class SectionCoverageStatus(str, Enum):
    NOT_STARTED = "not_started"
    IN_PROGRESS = "in_progress"
    COVERED = "covered"


class DiscoveryConversationTurn(BaseModel):
    turn_id: str
    session_id: str
    section: DiscoveryPillar
    question_text: str | None = None
    answer_text: str = Field(min_length=1)
    answered_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class StructuredFieldUpdate(BaseModel):
    dimension: DiscoveryDimension
    value: Any | None = None


class NarrativeDimensionUpdate(BaseModel):
    dimension: DiscoveryDimension
    text: str = Field(min_length=1)


class EvidenceSnippet(BaseModel):
    excerpt: str = Field(min_length=1)
    dimension: DiscoveryDimension | None = None
    rationale: str | None = None


class ShortTermMemoryCandidate(BaseModel):
    summary: str = Field(min_length=1)
    theme: str = Field(min_length=1)
    source_dimension: DiscoveryDimension | None = None


class DimensionIssue(BaseModel):
    dimension: DiscoveryDimension | None = None
    note: str = Field(min_length=1)


class SectionCoverageSnapshot(BaseModel):
    section: DiscoveryPillar
    status: SectionCoverageStatus
    target_dimensions: list[DiscoveryDimension] = Field(default_factory=list)
    outstanding_dimensions: list[DiscoveryDimension] = Field(default_factory=list)
    covered_dimensions: list[DiscoveryDimension] = Field(default_factory=list)
    covered_dimension_count: int = Field(default=0, ge=0)
    total_dimension_count: int = Field(default=0, ge=0)
    progress_percent: int = Field(default=0, ge=0, le=100)
    remaining_gaps: list[str] = Field(default_factory=list)
    conflict_notes: list[str] = Field(default_factory=list)
    confidence_label: ConfidenceLabel = ConfidenceLabel.MEDIUM
    evidence_quality_label: EvidenceQualityLabel = EvidenceQualityLabel.LOW
    blocked_by_conflicts: bool = False
    last_updated_at: datetime | None = None


class WorkingProfileSnapshot(BaseModel):
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


class DiscoveryInterpretationPacket(BaseModel):
    section: DiscoveryPillar
    question_text: str | None = None
    answer_text: str = Field(min_length=1)
    covered_dimensions: list[DiscoveryDimension] = Field(default_factory=list)
    structured_field_updates: list[StructuredFieldUpdate] = Field(default_factory=list)
    narrative_dimension_updates: list[NarrativeDimensionUpdate] = Field(default_factory=list)
    long_term_memory_candidates: list[NarrativeMemoryCandidate] = Field(default_factory=list)
    short_term_memory_candidates: list[ShortTermMemoryCandidate] = Field(default_factory=list)
    evidence_snippets: list[EvidenceSnippet] = Field(default_factory=list)
    contextual_rule_candidates: list[ContextualRuleCandidate] = Field(default_factory=list)
    remaining_gaps: list[str] = Field(default_factory=list)
    dimension_remaining_gaps: list[DimensionIssue] = Field(default_factory=list)
    conflict_notes: list[str] = Field(default_factory=list)
    dimension_conflict_notes: list[DimensionIssue] = Field(default_factory=list)
    confidence_label: ConfidenceLabel = ConfidenceLabel.MEDIUM
    section_complete: bool = False


class AcceptedInterpretationPacket(BaseModel):
    interpretation_id: str
    session_id: str
    packet: DiscoveryInterpretationPacket
    stored_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class ProfileDiscoveryState(BaseModel):
    session_id: str
    owner_id: str
    workflow_kind: DiscoveryWorkflowKind
    status: DiscoverySessionStatus
    source_profile_id: str | None = None
    current_section: DiscoveryPillar | None = None
    starter_question: DiscoveryQuestion | None = None
    target_dimensions: list[DiscoveryDimension] = Field(default_factory=list)
    section_coverage: list[SectionCoverageSnapshot] = Field(default_factory=list)
    working_profile_snapshot: WorkingProfileSnapshot = Field(default_factory=WorkingProfileSnapshot)
    recent_turns: list[DiscoveryConversationTurn] = Field(default_factory=list)
    recent_interpretations: list[AcceptedInterpretationPacket] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)


class PersonaUpdateChoice(str, Enum):
    FULL_REASSESSMENT = "full_reassessment"
    FINANCIAL_OBJECTIVES = "financial_objectives"
    RISK_BOUNDARIES = "risk_boundaries"
    INVESTMENT_CONSTRAINTS = "investment_constraints"
    ACCOUNT_FOUNDATION_AND_TRAITS = "account_foundation_and_traits"
    NO_CHANGES = "no_changes"


class DiscoverySession(BaseModel):
    session_id: str
    owner_id: str
    preferred_profile_name: str | None = None
    workflow_kind: DiscoveryWorkflowKind = DiscoveryWorkflowKind.ADD
    source_profile_id: str | None = None
    update_choice: PersonaUpdateChoice | None = None
    update_notes: str | None = None
    target_dimensions: list[DiscoveryDimension] = Field(default_factory=list)
    status: DiscoverySessionStatus = DiscoverySessionStatus.DISCOVERY_IN_PROGRESS
    conversation_turns: list[DiscoveryConversationTurn] = Field(default_factory=list)
    interpretation_history: list[AcceptedInterpretationPacket] = Field(default_factory=list)
    dimension_states: list[DimensionState] = Field(default_factory=list)
    section_coverage: list[SectionCoverageSnapshot] = Field(default_factory=list)
    working_profile_snapshot: WorkingProfileSnapshot | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class ContextualRuleCandidate(BaseModel):
    rule_text: str
    reason: str
    confidence: str = "medium"


class NarrativeMemoryCandidate(BaseModel):
    summary: str
    theme: str
    source_dimension: DiscoveryDimension


class ProfileDraftFieldSource(BaseModel):
    field_path: str
    dimensions: list[DiscoveryDimension] = Field(default_factory=list)
    interpretation_ids: list[str] = Field(default_factory=list)
    evidence_excerpts: list[str] = Field(default_factory=list)


class ProfileDraftSourcePacket(BaseModel):
    session_id: str
    owner_id: str
    workflow_kind: DiscoveryWorkflowKind
    source_profile_id: str | None = None
    readiness: DraftReadinessAssessment
    section_coverage: list[SectionCoverageSnapshot] = Field(default_factory=list)
    working_profile_snapshot: WorkingProfileSnapshot = Field(default_factory=WorkingProfileSnapshot)
    conversation_turns: list[DiscoveryConversationTurn] = Field(default_factory=list)
    accepted_interpretations: list[AcceptedInterpretationPacket] = Field(default_factory=list)
    field_sources: list[ProfileDraftFieldSource] = Field(default_factory=list)
    evidence_count: int = Field(default=0, ge=0)
    long_term_memory_count: int = Field(default=0, ge=0)
    short_term_memory_count: int = Field(default=0, ge=0)
    contextual_rule_count: int = Field(default=0, ge=0)


class ProfileDraft(BaseModel):
    draft_id: str
    session_id: str
    owner_id: str
    readiness: DraftReadinessAssessment
    suggested_profile: PersonaProfile
    draft_source: ProfileDraftSourcePacket | None = None
    contextual_rules: list[ContextualRuleCandidate] = Field(default_factory=list)
    narrative_memories: list[NarrativeMemoryCandidate] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class StartDiscoveryRequest(BaseModel):
    owner_id: str = Field(min_length=1)
    preferred_profile_name: str | None = None


class ConfirmProfileDraftRequest(BaseModel):
    profile_id: str | None = None
    display_name: str | None = None
    persona_markdown: str | None = Field(default=None, min_length=1)
    profile_markdown: str | None = Field(default=None, min_length=1)
    user_confirmed: bool = False

    @model_validator(mode="after")
    def require_markdown(self) -> "ConfirmProfileDraftRequest":
        if not self.persona_markdown and not self.profile_markdown:
            raise ValueError("Either profile_markdown or persona_markdown is required.")
        return self


class ReviewProfileRequest(BaseModel):
    trigger: str = Field(min_length=1)
    notes: str | None = None


class PersonaAssessmentStatus(str, Enum):
    QUESTION_PENDING = "question_pending"
    DRAFT_READY = "draft_ready"
    AWAITING_UPDATE_SELECTION = "awaiting_update_selection"
    PERSONA_COMPLETE = "persona_complete"


class PersonaAssessmentReason(str, Enum):
    NO_ACTIVE_PERSONA = "no_active_persona"
    ADD_IN_PROGRESS = "add_in_progress"
    INCOMPLETE_ACTIVE_PERSONA = "incomplete_active_persona"
    UPDATE_IN_PROGRESS = "update_in_progress"
    COMPLETE_ACTIVE_PERSONA = "complete_active_persona"
    NO_CHANGES_CONFIRMED = "no_changes_confirmed"
    PERSONA_READY_FOR_CONFIRMATION = "persona_ready_for_confirmation"


class PersonaUpdateOption(BaseModel):
    choice: PersonaUpdateChoice
    label: str
    description: str


class AssessPersonaRequest(BaseModel):
    owner_id: str = Field(min_length=1)
    profile_id: str | None = None
    preferred_profile_name: str | None = None
    update_choice: PersonaUpdateChoice | None = None
    update_notes: str | None = None


class PersonaAssessmentState(BaseModel):
    owner_id: str
    action: DiscoveryWorkflowKind
    status: PersonaAssessmentStatus
    reason: PersonaAssessmentReason
    recommended_next_action: str
    prompt_template_id: str
    active_profile_id: str | None = None
    active_profile_version: int | None = None
    persona_markdown_missing: bool = False
    discovery_session_id: str | None = None
    profile_draft_id: str | None = None
    selected_update_choice: PersonaUpdateChoice | None = None
    update_options: list[PersonaUpdateOption] = Field(default_factory=list)
    missing_dimensions: list[DiscoveryDimension] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)
    discovery_state: ProfileDiscoveryState | None = None

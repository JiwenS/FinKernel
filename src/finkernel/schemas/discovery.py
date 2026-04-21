from __future__ import annotations

from datetime import UTC, datetime
from enum import Enum

from pydantic import BaseModel, Field

from finkernel.schemas.profile import PersonaProfile


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
    OBJECTIVE = "objective"
    LIQUIDITY = "liquidity"
    HORIZON = "horizon"
    RISK_RESPONSE = "risk_response"
    LOSS_THRESHOLD = "loss_threshold"
    CONSTRAINTS = "constraints"
    CONCENTRATION = "concentration"
    BACKGROUND = "background"
    INTERACTION_STYLE = "interaction_style"
    REVIEW_CADENCE = "review_cadence"


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


class DiscoveryAnswer(BaseModel):
    answer_id: str
    session_id: str
    question_id: str
    dimension: DiscoveryDimension
    answer_text: str = Field(min_length=1)
    question_type: DiscoveryQuestionType
    source_type: DiscoveryQuestionSource
    answered_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    extracted_signals: list[str] = Field(default_factory=list)


class DimensionState(BaseModel):
    dimension: DiscoveryDimension
    coverage_score: int = Field(default=0, ge=0, le=3)
    confidence_score: int = Field(default=0, ge=0, le=3)
    depth_score: int = Field(default=0, ge=0, le=3)
    conflict_flag: bool = False
    last_question_id: str | None = None
    last_updated_at: datetime | None = None
    extracted_facts: list[str] = Field(default_factory=list)
    pending_gaps: list[str] = Field(default_factory=list)


class DraftReadinessAssessment(BaseModel):
    ready: bool
    unmet_dimensions: list[DiscoveryDimension] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)


class PersonaUpdateChoice(str, Enum):
    FULL_REASSESSMENT = "full_reassessment"
    OBJECTIVES_AND_HORIZON = "objectives_and_horizon"
    LIQUIDITY_NEEDS = "liquidity_needs"
    RISK_TOLERANCE = "risk_tolerance"
    CONSTRAINTS_AND_EXCLUSIONS = "constraints_and_exclusions"
    CONCENTRATION_LIMITS = "concentration_limits"
    COMMUNICATION_PREFERENCES = "communication_preferences"
    BACKGROUND_CONTEXT = "background_context"
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
    current_question_id: str | None = None
    current_question: DiscoveryQuestion | None = None
    asked_question_ids: list[str] = Field(default_factory=list)
    answers: list[DiscoveryAnswer] = Field(default_factory=list)
    dimension_states: list[DimensionState] = Field(default_factory=list)
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


class ProfileDraft(BaseModel):
    draft_id: str
    session_id: str
    owner_id: str
    readiness: DraftReadinessAssessment
    suggested_profile: PersonaProfile
    hard_rules: dict = Field(default_factory=dict)
    contextual_rules: list[ContextualRuleCandidate] = Field(default_factory=list)
    narrative_memories: list[NarrativeMemoryCandidate] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class StartDiscoveryRequest(BaseModel):
    owner_id: str = Field(min_length=1)
    preferred_profile_name: str | None = None


class SubmitDiscoveryAnswerRequest(BaseModel):
    answer: str = Field(min_length=1)
    question_id: str | None = None


class ConfirmProfileDraftRequest(BaseModel):
    profile_id: str | None = None
    display_name: str | None = None
    persona_markdown: str | None = None


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
    next_question: DiscoveryQuestion | None = None

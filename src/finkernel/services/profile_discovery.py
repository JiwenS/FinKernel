from __future__ import annotations

from contextlib import contextmanager
from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation
import re
from typing import Any, Iterator
from uuid import uuid4

from sqlalchemy.orm import Session, sessionmaker

from finkernel.config import Settings
from finkernel.schemas.discovery import (
    AcceptedInterpretationPacket,
    ALL_REQUIRED_DIMENSIONS,
    ConfirmProfileDraftRequest,
    ConfidenceLabel,
    ContextualRuleCandidate,
    DimensionIssue,
    DiscoveryConversationTurn,
    DiscoveryDimension,
    DiscoveryInterpretationPacket,
    NarrativeDimensionUpdate,
    DiscoveryPillar,
    DiscoveryQuestion,
    DiscoveryQuestionSource,
    DiscoveryQuestionType,
    EvidenceQualityLabel,
    ExpectedAnswerShape,
    PILLAR_DIMENSIONS,
    DiscoverySession,
    DiscoverySessionStatus,
    DiscoveryWorkflowKind,
    DimensionState,
    DraftReadinessAssessment,
    EvidenceSnippet,
    NarrativeMemoryCandidate,
    PersonaAssessmentReason,
    PersonaAssessmentState,
    PersonaAssessmentStatus,
    PersonaUpdateChoice,
    PersonaUpdateOption,
    ProfileDiscoveryState,
    ProfileDraft,
    ProfileDraftFieldSource,
    ProfileDraftSourcePacket,
    ReviewProfileRequest,
    SectionCoverageStatus,
    SectionCoverageSnapshot,
    ShortTermMemoryCandidate,
    StructuredFieldUpdate,
    WorkingProfileSnapshot,
)
from finkernel.schemas.profile import (
    AccountBackground,
    AccountEntityType,
    DistilledProfileMemoryResponse,
    ExecutionMode,
    FinancialObjectives,
    InvestmentConstraints,
    LiquidityFrequency,
    MemoryKind,
    PersonaProfile,
    PersonaSourcePacket,
    ProfileLifecycleStatus,
    RiskBoundaries,
    RiskBudget,
    RiskProfileSummary,
)
from finkernel.services.profiles import ProfileStore
from finkernel.storage.models import (
    DiscoveryConversationTurnModel,
    DiscoveryInterpretationModel,
    DiscoverySessionModel,
    ProfileDraftModel,
)
from finkernel.storage.repositories import (
    DiscoveryConversationTurnRepository,
    DiscoveryInterpretationRepository,
    DiscoverySessionRepository,
    ProfileDraftRepository,
)

PROMPT_TEMPLATE_ADD_QUESTION = "persona_assessment.add_question"
PROMPT_TEMPLATE_UPDATE_QUESTION = "persona_assessment.update_question"
PROMPT_TEMPLATE_DRAFT_READY = "persona_assessment.draft_ready"
PROMPT_TEMPLATE_UPDATE_SELECTION = "persona_assessment.update_selection"
PROMPT_TEMPLATE_COMPLETE = "persona_assessment.complete"

UPDATE_OPTION_DEFINITIONS: tuple[PersonaUpdateOption, ...] = (
    PersonaUpdateOption(
        choice=PersonaUpdateChoice.FULL_REASSESSMENT,
        label="Reassess everything",
        description="Run the full persona assessment again before creating a refreshed profile version.",
    ),
    PersonaUpdateOption(
        choice=PersonaUpdateChoice.FINANCIAL_OBJECTIVES,
        label="Financial objectives",
        description="Refresh return target, horizon, and recurring liquidity needs.",
    ),
    PersonaUpdateOption(
        choice=PersonaUpdateChoice.RISK_BOUNDARIES,
        label="Risk boundaries",
        description="Refresh drawdown, volatility, leverage, and single-asset concentration limits.",
    ),
    PersonaUpdateOption(
        choice=PersonaUpdateChoice.INVESTMENT_CONSTRAINTS,
        label="Investment constraints",
        description="Refresh blocked sectors, blocked tickers, base currency, and tax residency assumptions.",
    ),
    PersonaUpdateOption(
        choice=PersonaUpdateChoice.ACCOUNT_FOUNDATION_AND_TRAITS,
        label="Account foundation and traits",
        description="Refresh entity type, AUM, execution mode, financial literacy, wealth origin DNA, and behavioral risk profile.",
    ),
    PersonaUpdateOption(
        choice=PersonaUpdateChoice.NO_CHANGES,
        label="No changes",
        description="Keep the current active persona as-is and continue using it without a new assessment pass.",
    ),
)

UPDATE_CHOICE_DIMENSIONS: dict[PersonaUpdateChoice, list[DiscoveryDimension]] = {
    PersonaUpdateChoice.FULL_REASSESSMENT: list(ALL_REQUIRED_DIMENSIONS),
    PersonaUpdateChoice.FINANCIAL_OBJECTIVES: [
        DiscoveryDimension.TARGET_ANNUAL_RETURN,
        DiscoveryDimension.INVESTMENT_HORIZON,
        DiscoveryDimension.ANNUAL_LIQUIDITY_NEED,
        DiscoveryDimension.LIQUIDITY_FREQUENCY,
    ],
    PersonaUpdateChoice.RISK_BOUNDARIES: [
        DiscoveryDimension.MAX_DRAWDOWN_LIMIT,
        DiscoveryDimension.MAX_ANNUAL_VOLATILITY,
        DiscoveryDimension.MAX_LEVERAGE_RATIO,
        DiscoveryDimension.SINGLE_ASSET_CAP,
    ],
    PersonaUpdateChoice.INVESTMENT_CONSTRAINTS: [
        DiscoveryDimension.BLOCKED_SECTORS,
        DiscoveryDimension.BLOCKED_TICKERS,
        DiscoveryDimension.BASE_CURRENCY,
        DiscoveryDimension.TAX_RESIDENCY,
    ],
    PersonaUpdateChoice.ACCOUNT_FOUNDATION_AND_TRAITS: [
        DiscoveryDimension.ACCOUNT_ENTITY_TYPE,
        DiscoveryDimension.AUM_ALLOCATED,
        DiscoveryDimension.EXECUTION_MODE,
        DiscoveryDimension.FINANCIAL_LITERACY,
        DiscoveryDimension.WEALTH_ORIGIN_DNA,
        DiscoveryDimension.BEHAVIORAL_RISK_PROFILE,
    ],
}

SECTION_STARTER_QUESTIONS: dict[DiscoveryPillar, tuple[str, str]] = {
    DiscoveryPillar.FINANCIAL_OBJECTIVES: (
        "If this capital is meant to serve real life goals, what do you want it to accomplish for you, and are there any time horizons or cash needs that already matter?",
        "This opens the section by surfacing target return, time horizon, and liquidity context in the user's own words.",
    ),
    DiscoveryPillar.RISK: (
        "When investments fluctuate or lose money, what actually becomes unacceptable for you, and how do you recognize that line in practice?",
        "This opens the section by surfacing loss boundaries, volatility tolerance, leverage limits, and behavioral stress signals.",
    ),
    DiscoveryPillar.CONSTRAINTS: (
        "Are there any investments, sectors, currencies, tax realities, or mandate rules that you already know should be excluded or treated as hard limits?",
        "This opens the section by surfacing hard filters, concentration constraints, and tax or currency anchors.",
    ),
    DiscoveryPillar.BACKGROUND: (
        "What context about the account, the capital behind it, and the way you want decisions handled would help an agent operate appropriately for you?",
        "This opens the section by surfacing account structure, delegated-versus-advisory execution, and durable persona traits.",
    ),
}


def build_empty_dimension_states() -> list[DimensionState]:
    return [DimensionState(dimension=dimension) for dimension in ALL_REQUIRED_DIMENSIONS]


class DiscoveryNotReadyError(ValueError):
    pass


class InvalidDiscoveryInterpretationError(ValueError):
    pass


class ProfileDiscoveryService:
    def __init__(
        self,
        *,
        settings: Settings,
        session_factory: sessionmaker[Session],
        profile_store: ProfileStore,
        session_repository: DiscoverySessionRepository | None = None,
        turn_repository: DiscoveryConversationTurnRepository | None = None,
        interpretation_repository: DiscoveryInterpretationRepository | None = None,
        draft_repository: ProfileDraftRepository | None = None,
    ) -> None:
        self.settings = settings
        self.session_factory = session_factory
        self.profile_store = profile_store
        self.session_repository = session_repository or DiscoverySessionRepository()
        self.turn_repository = turn_repository or DiscoveryConversationTurnRepository()
        self.interpretation_repository = interpretation_repository or DiscoveryInterpretationRepository()
        self.draft_repository = draft_repository or ProfileDraftRepository()

    def start_discovery(self, *, owner_id: str, preferred_profile_name: str | None = None) -> DiscoverySession:
        session = DiscoverySession(
            session_id=str(uuid4()),
            owner_id=owner_id,
            preferred_profile_name=preferred_profile_name,
            workflow_kind=DiscoveryWorkflowKind.ADD,
            target_dimensions=list(ALL_REQUIRED_DIMENSIONS),
            dimension_states=build_empty_dimension_states(),
            working_profile_snapshot=WorkingProfileSnapshot(),
        )
        session.section_coverage = self._build_section_coverage_from_session(session)
        self._save_session(session)
        return session

    def start_update(
        self,
        *,
        profile_id: str,
        update_choice: PersonaUpdateChoice | None = None,
        update_notes: str | None = None,
        target_dimensions: list[DiscoveryDimension] | None = None,
    ) -> DiscoverySession:
        profile = self.profile_store.get(profile_id, require_active=False)
        session_id = str(uuid4())
        selected_dimensions = self._normalize_dimensions(target_dimensions or self._dimensions_for_update_choice(update_choice))
        if not selected_dimensions and update_choice is None and target_dimensions is None:
            selected_dimensions = list(ALL_REQUIRED_DIMENSIONS)
        session = DiscoverySession(
            session_id=session_id,
            owner_id=profile.owner_id,
            preferred_profile_name=profile.display_name,
            workflow_kind=DiscoveryWorkflowKind.UPDATE,
            source_profile_id=profile.profile_id,
            update_choice=update_choice,
            update_notes=update_notes,
            target_dimensions=selected_dimensions,
            dimension_states=self._seed_dimension_states_from_profile(profile),
            working_profile_snapshot=self._build_working_snapshot_from_profile(profile),
        )
        self._mark_dimensions_for_refresh(session, selected_dimensions)
        session.updated_at = datetime.now(UTC)
        session.section_coverage = self._build_section_coverage_from_session(session)
        readiness = self._build_readiness(session)
        session.status = DiscoverySessionStatus.DRAFT_READY if readiness.ready else DiscoverySessionStatus.DISCOVERY_IN_PROGRESS
        self._save_session(session)
        return session

    def get_session(self, session_id: str) -> DiscoverySession:
        with self._session_scope() as session:
            model = self.session_repository.get(session, session_id)
            if model is None:
                raise KeyError(f"Unknown discovery_session_id: {session_id}")
            payload = dict(model.payload)
            payload["conversation_turns"] = [
                turn_model.payload
                for turn_model in self.turn_repository.list_for_session(session, session_id)
            ]
            payload["interpretation_history"] = [
                interpretation_model.payload
                for interpretation_model in self.interpretation_repository.list_for_session(session, session_id)
            ]
            return DiscoverySession.model_validate(payload)

    def get_discovery_state(self, session_id: str) -> ProfileDiscoveryState:
        session = self.get_session(session_id)
        if not session.section_coverage:
            session.section_coverage = self._build_section_coverage_from_session(session)
        if session.working_profile_snapshot is None:
            session.working_profile_snapshot = WorkingProfileSnapshot()
        return self._build_discovery_state(session)

    def submit_interpretation(self, *, session_id: str, packet: DiscoveryInterpretationPacket) -> ProfileDiscoveryState:
        session = self.get_session(session_id)
        allowed_dimensions = self._validate_interpretation_packet(session, packet)
        snapshot = session.working_profile_snapshot or WorkingProfileSnapshot()
        now = datetime.now(UTC)

        turn = DiscoveryConversationTurn(
            turn_id=str(uuid4()),
            session_id=session_id,
            section=packet.section,
            question_text=packet.question_text,
            answer_text=packet.answer_text.strip(),
            answered_at=now,
        )
        session.conversation_turns.append(turn)

        confidence_score = self._confidence_score_from_label(packet.confidence_label)
        touched_dimensions = set(packet.covered_dimensions)

        for update in packet.structured_field_updates:
            normalized_value = self._apply_structured_field_update(snapshot, update)
            self._get_dimension_state(session, update.dimension).normalized_value = normalized_value
            touched_dimensions.add(update.dimension)

        for update in packet.narrative_dimension_updates:
            self._apply_narrative_dimension_update(snapshot, update)
            self._get_dimension_state(session, update.dimension).normalized_value = update.text.strip()
            touched_dimensions.add(update.dimension)

        evidence_dimensions: set[DiscoveryDimension] = set()
        if packet.evidence_snippets:
            for snippet in packet.evidence_snippets:
                self._append_evidence_snippet(snapshot, snippet)
                if snippet.dimension in allowed_dimensions:
                    evidence_dimensions.add(snippet.dimension)
        else:
            default_evidence_dimension = self._default_evidence_dimension(packet, touched_dimensions)
            self._append_evidence_snippet(
                snapshot,
                EvidenceSnippet(
                    excerpt=packet.answer_text.strip(),
                    dimension=default_evidence_dimension,
                ),
            )
            if default_evidence_dimension in allowed_dimensions:
                evidence_dimensions.add(default_evidence_dimension)

        for candidate in packet.long_term_memory_candidates:
            self._append_long_term_memory(snapshot, candidate)
        for candidate in packet.short_term_memory_candidates:
            self._append_short_term_memory(snapshot, candidate)
        for candidate in packet.contextual_rule_candidates:
            self._append_contextual_rule(snapshot, candidate)

        covered_in_section = set(packet.covered_dimensions).intersection(allowed_dimensions)
        for dimension in touched_dimensions.intersection(allowed_dimensions):
            state = self._get_dimension_state(session, dimension)
            state.last_updated_at = now
            state.extracted_facts.append(packet.answer_text.strip())
            if dimension in evidence_dimensions:
                state.evidence_score = max(state.evidence_score, confidence_score)
            if dimension in covered_in_section:
                state.coverage_score = 3
                state.confidence_score = confidence_score
                state.depth_score = max(state.depth_score, 2)
                state.pending_gaps = []
            else:
                state.coverage_score = max(state.coverage_score, 1)
                state.confidence_score = max(state.confidence_score, confidence_score)

        dimension_remaining_gaps = self._dimension_issue_notes(packet.dimension_remaining_gaps)
        dimension_conflict_notes = self._dimension_issue_notes(packet.dimension_conflict_notes)
        generic_remaining_gaps = self._clean_issue_notes(packet.remaining_gaps) + self._section_issue_notes(packet.dimension_remaining_gaps)
        generic_remaining_gaps = list(dict.fromkeys(generic_remaining_gaps))
        generic_conflict_notes = self._clean_issue_notes(packet.conflict_notes) + self._section_issue_notes(packet.dimension_conflict_notes)
        generic_conflict_notes = list(dict.fromkeys(generic_conflict_notes))

        uncovered_in_section = [
            dimension
            for dimension in allowed_dimensions
            if dimension not in covered_in_section
        ]
        for dimension in uncovered_in_section:
            state = self._get_dimension_state(session, dimension)
            state.pending_gaps = list(dimension_remaining_gaps.get(dimension, generic_remaining_gaps))
            state.confidence_score = max(state.confidence_score, confidence_score)
            state.last_updated_at = now
            if state.coverage_score == 0:
                state.coverage_score = 1

        for dimension in allowed_dimensions:
            state = self._get_dimension_state(session, dimension)
            if packet.section_complete and dimension in covered_in_section:
                state.pending_gaps = []
                state.conflict_flag = False
            elif dimension_conflict_notes.get(dimension):
                state.pending_gaps = list(dict.fromkeys(state.pending_gaps + dimension_conflict_notes[dimension]))
                state.conflict_flag = True
            elif generic_conflict_notes and dimension in covered_in_section:
                state.conflict_flag = True

        if packet.section_complete:
            incomplete_after_update = [
                dimension
                for dimension in allowed_dimensions
                if self._dimension_requires_more_work(self._get_dimension_state(session, dimension))
            ]
            if incomplete_after_update:
                raise InvalidDiscoveryInterpretationError(
                    "section_complete was set to true before the current section had enough confirmed coverage."
                )

        accepted_interpretation = AcceptedInterpretationPacket(
            interpretation_id=str(uuid4()),
            session_id=session_id,
            packet=packet,
            stored_at=now,
        )
        session.interpretation_history.append(accepted_interpretation)

        session.working_profile_snapshot = snapshot
        session.section_coverage = self._build_section_coverage_from_session(session)
        session.updated_at = now
        readiness = self._build_readiness(session)
        session.status = DiscoverySessionStatus.DRAFT_READY if readiness.ready else DiscoverySessionStatus.DISCOVERY_IN_PROGRESS
        self._save_session(session, new_turn=turn, new_interpretation=accepted_interpretation)
        return self._build_discovery_state(session)

    def generate_draft(self, session_id: str) -> ProfileDraft:
        session = self.get_session(session_id)
        readiness = self._build_readiness(session)
        if not readiness.ready:
            raise DiscoveryNotReadyError(f"Discovery session {session_id} is not ready for draft generation.")

        draft = self._build_draft(session, readiness)
        self._save_draft(draft)
        session.status = DiscoverySessionStatus.DRAFT_READY
        self._save_session(session)
        return draft

    def get_draft(self, draft_id: str) -> ProfileDraft:
        with self._session_scope() as session:
            model = self.draft_repository.get(session, draft_id)
            if model is None:
                raise KeyError(f"Unknown profile_draft_id: {draft_id}")
            return ProfileDraft.model_validate(model.payload)

    def get_profile(self, profile_id: str, *, version: int | None = None) -> PersonaProfile:
        return self.profile_store.get(profile_id, version=version, require_active=version is None)

    def get_persona_source_packet(self, profile_id: str, *, version: int | None = None) -> PersonaSourcePacket:
        profile = self.get_profile(profile_id, version=version)
        return PersonaSourcePacket(
            profile_id=profile.profile_id,
            version=profile.version,
            display_name=profile.display_name,
            mandate_summary=profile.mandate_summary,
            persona_style=profile.persona_style,
            risk_budget=profile.risk_budget,
            financial_objectives=profile.financial_objectives,
            risk_boundaries=profile.risk_boundaries,
            investment_constraints=profile.investment_constraints,
            account_background=profile.account_background,
            persona_traits=profile.persona_traits,
            persona_markdown=profile.persona_markdown,
            persona_evidence=profile.persona_evidence,
            long_term_memories=profile.long_term_memories,
            short_term_memories=profile.short_term_memories,
            contextual_rules=profile.contextual_rules,
        )

    def get_risk_profile_summary(self, profile_id: str, *, version: int | None = None) -> RiskProfileSummary:
        profile = self.get_profile(profile_id, version=version)
        return RiskProfileSummary(
            profile_id=profile.profile_id,
            owner_id=profile.owner_id,
            version=profile.version,
            display_name=profile.display_name,
            mandate_summary=profile.mandate_summary,
            risk_budget=profile.risk_budget,
            persona_style=profile.persona_style,
            target_annual_return_pct=profile.financial_objectives.target_annual_return_pct,
            investment_horizon_years=profile.financial_objectives.investment_horizon_years,
            annual_liquidity_need=profile.financial_objectives.annual_liquidity_need,
            liquidity_frequency=profile.financial_objectives.liquidity_frequency,
            max_drawdown_limit_pct=profile.risk_boundaries.max_drawdown_limit_pct,
            max_annual_volatility_pct=profile.risk_boundaries.max_annual_volatility_pct,
            max_leverage_ratio=profile.risk_boundaries.max_leverage_ratio,
            single_asset_cap_pct=profile.risk_boundaries.single_asset_cap_pct,
            blocked_sectors=profile.investment_constraints.blocked_sectors,
            blocked_tickers=profile.investment_constraints.blocked_tickers,
            base_currency=profile.investment_constraints.base_currency,
            tax_residency=profile.investment_constraints.tax_residency,
            account_entity_type=profile.account_background.account_entity_type,
            aum_allocated=profile.account_background.aum_allocated,
            execution_mode=profile.account_background.execution_mode,
            financial_literacy=profile.persona_traits.financial_literacy,
            wealth_origin_dna=profile.persona_traits.wealth_origin_dna,
            behavioral_risk_profile=profile.persona_traits.behavioral_risk_profile,
            contextual_rule_highlights=[
                str(item.get("rule_text") or item.get("rule") or "").strip()
                for item in profile.contextual_rules
                if str(item.get("rule_text") or item.get("rule") or "").strip()
            ],
            long_term_memory_highlights=[
                str(item.get("summary") or item.get("content_text") or "").strip()
                for item in profile.long_term_memories
                if str(item.get("summary") or item.get("content_text") or "").strip()
            ][:3],
            short_term_memory_highlights=[
                str(item.get("summary") or item.get("content_text") or "").strip()
                for item in profile.short_term_memories
                if str(item.get("summary") or item.get("content_text") or "").strip()
            ][:3],
        )

    def list_profile_versions(self, profile_id: str) -> list[PersonaProfile]:
        return self.profile_store.list_versions(profile_id)

    def append_memory(
        self,
        *,
        profile_id: str,
        memory_kind: MemoryKind,
        theme: str,
        content_text: str,
        source_dimension: str | None = None,
        expires_at=None,
    ) -> PersonaProfile:
        return self.profile_store.append_memory(
            profile_id=profile_id,
            memory_kind=memory_kind,
            theme=theme,
            content_text=content_text,
            source_dimension=source_dimension,
            expires_at=expires_at,
        )

    def search_memory(self, *, profile_id: str, query: str, memory_kind: MemoryKind | None = None, include_expired: bool = False) -> list[dict]:
        return self.profile_store.search_memory(
            profile_id=profile_id,
            query=query,
            memory_kind=memory_kind,
            include_expired=include_expired,
        )

    def distill_memory(self, *, profile_id: str) -> DistilledProfileMemoryResponse:
        return self.profile_store.distill_memory(profile_id=profile_id)

    def save_persona_markdown(self, *, profile_id: str, persona_markdown: str, version: int | None = None) -> PersonaProfile:
        return self.profile_store.save_persona_markdown(profile_id=profile_id, persona_markdown=persona_markdown, version=version)

    def save_profile_markdown(self, *, profile_id: str, profile_markdown: str, version: int | None = None) -> PersonaProfile:
        return self.save_persona_markdown(profile_id=profile_id, persona_markdown=profile_markdown, version=version)

    def start_review(self, *, profile_id: str, payload: ReviewProfileRequest) -> DiscoverySession:
        return self.start_update(
            profile_id=profile_id,
            update_choice=PersonaUpdateChoice.FULL_REASSESSMENT,
            update_notes=payload.notes,
            target_dimensions=list(ALL_REQUIRED_DIMENSIONS),
        )

    def assess_profile_completeness(self, profile_id: str, *, version: int | None = None) -> DraftReadinessAssessment:
        profile = self.get_profile(profile_id, version=version)
        session = DiscoverySession(
            session_id=f"assessment-{profile.profile_id}-{profile.version}",
            owner_id=profile.owner_id,
            preferred_profile_name=profile.display_name,
            workflow_kind=DiscoveryWorkflowKind.UPDATE,
            source_profile_id=profile.profile_id,
            target_dimensions=list(ALL_REQUIRED_DIMENSIONS),
            dimension_states=self._seed_dimension_states_from_profile(profile),
            section_coverage=[],
            working_profile_snapshot=self._build_working_snapshot_from_profile(profile),
        )
        session.section_coverage = self._build_section_coverage_from_session(session)
        readiness = self._build_readiness(session)
        if not profile.persona_markdown:
            readiness.notes.append("Persona markdown is still missing.")
        return readiness

    def assess_persona(
        self,
        *,
        owner_id: str,
        profile_id: str | None = None,
        preferred_profile_name: str | None = None,
        update_choice: PersonaUpdateChoice | None = None,
        update_notes: str | None = None,
    ) -> PersonaAssessmentState:
        active_profile = self._select_active_profile(owner_id=owner_id, profile_id=profile_id)
        if active_profile is None:
            session = self._find_open_session(
                owner_id=owner_id,
                workflow_kind=DiscoveryWorkflowKind.ADD,
                source_profile_id=None,
            )
            if session is None:
                session = self.start_discovery(owner_id=owner_id, preferred_profile_name=preferred_profile_name)
                reason = PersonaAssessmentReason.NO_ACTIVE_PERSONA
            else:
                reason = PersonaAssessmentReason.ADD_IN_PROGRESS
            return self._build_assessment_state_from_session(
                session,
                action=DiscoveryWorkflowKind.ADD,
                reason=reason,
                active_profile=None,
            )

        readiness = self.assess_profile_completeness(active_profile.profile_id, version=active_profile.version)
        profile_is_complete = readiness.ready and bool(active_profile.persona_markdown)
        open_update_session = self._find_open_session(
            owner_id=owner_id,
            workflow_kind=DiscoveryWorkflowKind.UPDATE,
            source_profile_id=active_profile.profile_id,
        )

        if not profile_is_complete:
            if open_update_session is None:
                open_update_session = self.start_update(
                    profile_id=active_profile.profile_id,
                    update_notes=update_notes,
                    target_dimensions=list(readiness.unmet_dimensions),
                )
            return self._build_assessment_state_from_session(
                open_update_session,
                action=DiscoveryWorkflowKind.UPDATE,
                reason=PersonaAssessmentReason.INCOMPLETE_ACTIVE_PERSONA,
                active_profile=active_profile,
            )

        if update_choice is PersonaUpdateChoice.NO_CHANGES:
            self._close_open_sessions(
                owner_id=owner_id,
                workflow_kind=DiscoveryWorkflowKind.UPDATE,
                source_profile_id=active_profile.profile_id,
            )
            return PersonaAssessmentState(
                owner_id=owner_id,
                action=DiscoveryWorkflowKind.UPDATE,
                status=PersonaAssessmentStatus.PERSONA_COMPLETE,
                reason=PersonaAssessmentReason.NO_CHANGES_CONFIRMED,
                recommended_next_action="continue_using_the_current_active_persona",
                prompt_template_id=PROMPT_TEMPLATE_COMPLETE,
                active_profile_id=active_profile.profile_id,
                active_profile_version=active_profile.version,
                persona_markdown_missing=False,
                notes=["The current active persona remains in force with no requested changes."],
            )

        if open_update_session is not None:
            if update_choice is None or open_update_session.update_choice == update_choice:
                return self._build_assessment_state_from_session(
                    open_update_session,
                    action=DiscoveryWorkflowKind.UPDATE,
                    reason=PersonaAssessmentReason.UPDATE_IN_PROGRESS,
                    active_profile=active_profile,
                )
            self._close_open_sessions(
                owner_id=owner_id,
                workflow_kind=DiscoveryWorkflowKind.UPDATE,
                source_profile_id=active_profile.profile_id,
            )

        if update_choice is None:
            return PersonaAssessmentState(
                owner_id=owner_id,
                action=DiscoveryWorkflowKind.UPDATE,
                status=PersonaAssessmentStatus.AWAITING_UPDATE_SELECTION,
                reason=PersonaAssessmentReason.COMPLETE_ACTIVE_PERSONA,
                recommended_next_action="ask_whether_to_keep_reassess_or_update_the_persona",
                prompt_template_id=PROMPT_TEMPLATE_UPDATE_SELECTION,
                active_profile_id=active_profile.profile_id,
                active_profile_version=active_profile.version,
                persona_markdown_missing=False,
                update_options=list(UPDATE_OPTION_DEFINITIONS),
                notes=[
                    "The active persona is complete.",
                    "Ask whether the user wants a full reassessment, a targeted update, or no changes.",
                ],
            )

        session = self.start_update(
            profile_id=active_profile.profile_id,
            update_choice=update_choice,
            update_notes=update_notes,
        )
        return self._build_assessment_state_from_session(
            session,
            action=DiscoveryWorkflowKind.UPDATE,
            reason=PersonaAssessmentReason.UPDATE_IN_PROGRESS,
            active_profile=active_profile,
        )

    def confirm_draft(self, *, draft_id: str, payload: ConfirmProfileDraftRequest) -> PersonaProfile:
        draft = self.get_draft(draft_id)
        suggested = draft.suggested_profile.model_copy(deep=True)
        profile_id = payload.profile_id or suggested.profile_id
        existing_versions = [profile for profile in self.profile_store.load_all_versions() if profile.profile_id == profile_id]
        next_version = max((profile.version for profile in existing_versions), default=0) + 1
        final_profile = suggested.model_copy(
            update={
                "profile_id": profile_id,
                "display_name": payload.display_name or suggested.display_name,
                "version": next_version,
                "status": ProfileLifecycleStatus.ACTIVE,
                "supersedes_profile_version": max((profile.version for profile in existing_versions if profile.is_active), default=None),
                "persona_markdown": payload.profile_markdown or payload.persona_markdown or suggested.persona_markdown,
            }
        )
        self.profile_store.append_profile(final_profile)
        self._mark_session_completed(draft.session_id)
        return final_profile

    def _seed_dimension_states_from_profile(self, profile: PersonaProfile) -> list[DimensionState]:
        states = build_empty_dimension_states()
        state_map = {state.dimension: state for state in states}

        def mark(dimension: DiscoveryDimension, value: Any) -> None:
            if value in (None, "", {}):
                return
            if isinstance(value, list) and not value and dimension not in {
                DiscoveryDimension.BLOCKED_SECTORS,
                DiscoveryDimension.BLOCKED_TICKERS,
            }:
                return
            state = state_map[dimension]
            state.coverage_score = 3
            state.confidence_score = 3
            state.evidence_score = 2
            state.depth_score = 2
            state.last_updated_at = datetime.now(UTC)
            state.normalized_value = value
            state.extracted_facts = [str(value)]

        financial = profile.financial_objectives
        risk = profile.risk_boundaries
        constraints = profile.investment_constraints
        background = profile.account_background
        traits = profile.persona_traits

        mark(DiscoveryDimension.TARGET_ANNUAL_RETURN, financial.target_annual_return_pct)
        mark(DiscoveryDimension.INVESTMENT_HORIZON, financial.investment_horizon_years)
        mark(DiscoveryDimension.ANNUAL_LIQUIDITY_NEED, financial.annual_liquidity_need)
        mark(DiscoveryDimension.LIQUIDITY_FREQUENCY, financial.liquidity_frequency.value if financial.liquidity_frequency else None)
        mark(DiscoveryDimension.MAX_DRAWDOWN_LIMIT, risk.max_drawdown_limit_pct)
        mark(DiscoveryDimension.MAX_ANNUAL_VOLATILITY, risk.max_annual_volatility_pct)
        mark(DiscoveryDimension.MAX_LEVERAGE_RATIO, risk.max_leverage_ratio)
        mark(DiscoveryDimension.SINGLE_ASSET_CAP, risk.single_asset_cap_pct)
        mark(DiscoveryDimension.BLOCKED_SECTORS, constraints.blocked_sectors)
        mark(DiscoveryDimension.BLOCKED_TICKERS, constraints.blocked_tickers)
        mark(DiscoveryDimension.BASE_CURRENCY, constraints.base_currency)
        mark(DiscoveryDimension.TAX_RESIDENCY, constraints.tax_residency)
        mark(DiscoveryDimension.ACCOUNT_ENTITY_TYPE, background.account_entity_type.value if background.account_entity_type else None)
        mark(DiscoveryDimension.AUM_ALLOCATED, background.aum_allocated)
        mark(DiscoveryDimension.EXECUTION_MODE, background.execution_mode.value if background.execution_mode else None)
        mark(DiscoveryDimension.FINANCIAL_LITERACY, traits.financial_literacy)
        mark(DiscoveryDimension.WEALTH_ORIGIN_DNA, traits.wealth_origin_dna)
        mark(DiscoveryDimension.BEHAVIORAL_RISK_PROFILE, traits.behavioral_risk_profile)
        return states

    def _build_working_snapshot_from_profile(self, profile: PersonaProfile) -> WorkingProfileSnapshot:
        return WorkingProfileSnapshot(
            financial_objectives=profile.financial_objectives.model_copy(deep=True),
            risk_boundaries=profile.risk_boundaries.model_copy(deep=True),
            investment_constraints=profile.investment_constraints.model_copy(deep=True),
            account_background=profile.account_background.model_copy(deep=True),
            persona_traits=profile.persona_traits.model_copy(deep=True),
            contextual_rules=[dict(item) for item in profile.contextual_rules],
            long_term_memories=[dict(item) for item in profile.long_term_memories],
            short_term_memories=[dict(item) for item in profile.short_term_memories],
            persona_evidence=[dict(item) for item in profile.persona_evidence],
            persona_markdown=profile.persona_markdown,
        )

    def _select_active_profile(self, *, owner_id: str, profile_id: str | None) -> PersonaProfile | None:
        if profile_id is not None:
            profile = self.profile_store.get(profile_id, require_active=False)
            if profile.owner_id != owner_id or not profile.is_active:
                return None
            return profile
        active_profiles = self.profile_store.list_active(owner_id=owner_id)
        return active_profiles[0] if active_profiles else None

    def _list_open_sessions(
        self,
        *,
        owner_id: str,
        workflow_kind: DiscoveryWorkflowKind,
        source_profile_id: str | None,
    ) -> list[DiscoverySession]:
        with self._session_scope() as session:
            models = self.session_repository.list_for_owner(
                session,
                owner_id,
                statuses=[
                    DiscoverySessionStatus.DISCOVERY_IN_PROGRESS.value,
                    DiscoverySessionStatus.DRAFT_READY.value,
                ],
            )
        candidates: list[DiscoverySession] = []
        for model in models:
            candidate = DiscoverySession.model_validate(model.payload)
            if candidate.workflow_kind != workflow_kind:
                continue
            if candidate.source_profile_id != source_profile_id:
                continue
            candidates.append(candidate)
        return candidates

    def _find_open_session(
        self,
        *,
        owner_id: str,
        workflow_kind: DiscoveryWorkflowKind,
        source_profile_id: str | None,
    ) -> DiscoverySession | None:
        sessions = self._list_open_sessions(
            owner_id=owner_id,
            workflow_kind=workflow_kind,
            source_profile_id=source_profile_id,
        )
        return sessions[0] if sessions else None

    def _close_open_sessions(
        self,
        *,
        owner_id: str,
        workflow_kind: DiscoveryWorkflowKind,
        source_profile_id: str | None,
    ) -> None:
        for session in self._list_open_sessions(
            owner_id=owner_id,
            workflow_kind=workflow_kind,
            source_profile_id=source_profile_id,
        ):
            self._mark_session_completed(session.session_id)

    def _get_or_create_draft_for_session(self, session_id: str) -> ProfileDraft:
        with self._session_scope() as session:
            models = self.draft_repository.list_for_session(session, session_id)
        if models:
            return ProfileDraft.model_validate(models[0].payload)
        return self.generate_draft(session_id)

    def _build_assessment_state_from_session(
        self,
        session: DiscoverySession,
        *,
        action: DiscoveryWorkflowKind,
        reason: PersonaAssessmentReason,
        active_profile: PersonaProfile | None,
    ) -> PersonaAssessmentState:
        session = self.get_session(session.session_id)
        if session.status is DiscoverySessionStatus.DRAFT_READY:
            draft = self._get_or_create_draft_for_session(session.session_id)
            notes = list(draft.readiness.notes)
            if action is DiscoveryWorkflowKind.ADD:
                notes.insert(0, "All required profile sections are covered. Write the final profile markdown and confirm the draft.")
            else:
                notes.insert(0, "This update pass has enough evidence to write refreshed profile markdown and confirm a new version.")
            return PersonaAssessmentState(
                owner_id=session.owner_id,
                action=action,
                status=PersonaAssessmentStatus.DRAFT_READY,
                reason=PersonaAssessmentReason.PERSONA_READY_FOR_CONFIRMATION,
                recommended_next_action="write_or_refresh_profile_markdown_then_confirm_profile_draft",
                prompt_template_id=PROMPT_TEMPLATE_DRAFT_READY,
                active_profile_id=active_profile.profile_id if active_profile else draft.suggested_profile.profile_id,
                active_profile_version=active_profile.version if active_profile else None,
                persona_markdown_missing=not bool(active_profile.persona_markdown) if active_profile else True,
                discovery_session_id=session.session_id,
                profile_draft_id=draft.draft_id,
                selected_update_choice=session.update_choice,
                missing_dimensions=draft.readiness.unmet_dimensions,
                notes=notes,
                discovery_state=self._build_discovery_state(session),
            )

        readiness = self._build_readiness(session)
        notes = list(readiness.notes)
        if active_profile is not None and not active_profile.persona_markdown:
            notes.append("Persona markdown is still missing.")
        if action is DiscoveryWorkflowKind.UPDATE and session.target_dimensions:
            notes.append(
                "Focused update sections: "
                + ", ".join(dimension.value for dimension in session.target_dimensions)
                + "."
            )
        discovery_state = self._build_discovery_state(session)
        return PersonaAssessmentState(
            owner_id=session.owner_id,
            action=action,
            status=PersonaAssessmentStatus.QUESTION_PENDING,
            reason=reason,
            recommended_next_action="inspect_discovery_state_then_generate_or_ask_the_current_section_question",
            prompt_template_id=PROMPT_TEMPLATE_ADD_QUESTION if action is DiscoveryWorkflowKind.ADD else PROMPT_TEMPLATE_UPDATE_QUESTION,
            active_profile_id=active_profile.profile_id if active_profile else None,
            active_profile_version=active_profile.version if active_profile else None,
            persona_markdown_missing=not bool(active_profile.persona_markdown) if active_profile else False,
            discovery_session_id=session.session_id,
            selected_update_choice=session.update_choice,
            missing_dimensions=readiness.unmet_dimensions,
            notes=notes,
            discovery_state=discovery_state,
        )

    def _build_draft(self, session: DiscoverySession, readiness: DraftReadinessAssessment) -> ProfileDraft:
        snapshot = session.working_profile_snapshot or WorkingProfileSnapshot()
        return self._build_draft_from_snapshot(session, readiness, snapshot)

    def _build_draft_from_snapshot(
        self,
        session: DiscoverySession,
        readiness: DraftReadinessAssessment,
        snapshot: WorkingProfileSnapshot,
    ) -> ProfileDraft:
        preferred_name = session.preferred_profile_name or "Primary Risk Profile"
        profile_id = session.source_profile_id or self._slugify_profile_id(preferred_name, session.owner_id)
        risk_budget = self._derive_risk_budget(snapshot.risk_boundaries)
        mandate_summary = self._build_mandate_summary(
            snapshot.financial_objectives,
            snapshot.risk_boundaries,
            snapshot.investment_constraints,
            snapshot.account_background,
            risk_budget,
        )
        suggested_profile = PersonaProfile(
            profile_id=profile_id,
            owner_id=session.owner_id,
            version=1,
            status=ProfileLifecycleStatus.PENDING_USER_CONFIRMATION,
            display_name=preferred_name,
            mandate_summary=mandate_summary,
            persona_style=self._derive_persona_style(risk_budget, snapshot.financial_objectives, snapshot.account_background),
            created_from="guided_discovery" if session.workflow_kind is DiscoveryWorkflowKind.ADD else "profile_update",
            risk_budget=risk_budget,
            financial_objectives=snapshot.financial_objectives,
            risk_boundaries=snapshot.risk_boundaries,
            investment_constraints=snapshot.investment_constraints,
            account_background=snapshot.account_background,
            persona_traits=snapshot.persona_traits,
            contextual_rules=list(snapshot.contextual_rules),
            long_term_memories=list(snapshot.long_term_memories),
            short_term_memories=list(snapshot.short_term_memories),
            persona_evidence=list(snapshot.persona_evidence),
            persona_markdown=snapshot.persona_markdown,
        )
        contextual_rules = [ContextualRuleCandidate.model_validate(item) for item in snapshot.contextual_rules]
        narrative_memories = [
            NarrativeMemoryCandidate.model_validate(item)
            for item in snapshot.long_term_memories
            if isinstance(item, dict) and item.get("summary") and item.get("theme")
        ]
        return ProfileDraft(
            draft_id=str(uuid4()),
            session_id=session.session_id,
            owner_id=session.owner_id,
            readiness=readiness,
            suggested_profile=suggested_profile,
            draft_source=self._build_draft_source_packet(session, readiness, snapshot),
            contextual_rules=contextual_rules,
            narrative_memories=narrative_memories,
        )

    def _build_draft_source_packet(
        self,
        session: DiscoverySession,
        readiness: DraftReadinessAssessment,
        snapshot: WorkingProfileSnapshot,
    ) -> ProfileDraftSourcePacket:
        return ProfileDraftSourcePacket(
            session_id=session.session_id,
            owner_id=session.owner_id,
            workflow_kind=session.workflow_kind,
            source_profile_id=session.source_profile_id,
            readiness=readiness,
            section_coverage=session.section_coverage or self._build_section_coverage_from_session(session),
            working_profile_snapshot=snapshot,
            conversation_turns=list(session.conversation_turns),
            accepted_interpretations=list(session.interpretation_history),
            field_sources=self._build_draft_field_sources(session.interpretation_history),
            evidence_count=len(snapshot.persona_evidence),
            long_term_memory_count=len(snapshot.long_term_memories),
            short_term_memory_count=len(snapshot.short_term_memories),
            contextual_rule_count=len(snapshot.contextual_rules),
        )

    def _build_draft_field_sources(
        self,
        interpretations: list[AcceptedInterpretationPacket],
    ) -> list[ProfileDraftFieldSource]:
        sources_by_path: dict[str, ProfileDraftFieldSource] = {}
        for interpretation in interpretations:
            packet = interpretation.packet
            evidence_by_dimension: dict[DiscoveryDimension, list[str]] = {}
            generic_evidence: list[str] = []
            for snippet in packet.evidence_snippets:
                excerpt = snippet.excerpt.strip()
                if not excerpt:
                    continue
                if snippet.dimension is None:
                    generic_evidence.append(excerpt)
                else:
                    evidence_by_dimension.setdefault(snippet.dimension, []).append(excerpt)

            dimensions = [update.dimension for update in packet.structured_field_updates]
            dimensions.extend(update.dimension for update in packet.narrative_dimension_updates)
            for dimension in dimensions:
                field_path = self._field_path_for_dimension(dimension)
                if field_path is None:
                    continue
                source = sources_by_path.setdefault(
                    field_path,
                    ProfileDraftFieldSource(field_path=field_path),
                )
                if dimension not in source.dimensions:
                    source.dimensions.append(dimension)
                if interpretation.interpretation_id not in source.interpretation_ids:
                    source.interpretation_ids.append(interpretation.interpretation_id)
                for excerpt in evidence_by_dimension.get(dimension, generic_evidence):
                    if excerpt not in source.evidence_excerpts:
                        source.evidence_excerpts.append(excerpt)

        return list(sources_by_path.values())

    def _field_path_for_dimension(self, dimension: DiscoveryDimension) -> str | None:
        return {
            DiscoveryDimension.TARGET_ANNUAL_RETURN: "financial_objectives.target_annual_return_pct",
            DiscoveryDimension.INVESTMENT_HORIZON: "financial_objectives.investment_horizon_years",
            DiscoveryDimension.ANNUAL_LIQUIDITY_NEED: "financial_objectives.annual_liquidity_need",
            DiscoveryDimension.LIQUIDITY_FREQUENCY: "financial_objectives.liquidity_frequency",
            DiscoveryDimension.MAX_DRAWDOWN_LIMIT: "risk_boundaries.max_drawdown_limit_pct",
            DiscoveryDimension.MAX_ANNUAL_VOLATILITY: "risk_boundaries.max_annual_volatility_pct",
            DiscoveryDimension.MAX_LEVERAGE_RATIO: "risk_boundaries.max_leverage_ratio",
            DiscoveryDimension.SINGLE_ASSET_CAP: "risk_boundaries.single_asset_cap_pct",
            DiscoveryDimension.BLOCKED_SECTORS: "investment_constraints.blocked_sectors",
            DiscoveryDimension.BLOCKED_TICKERS: "investment_constraints.blocked_tickers",
            DiscoveryDimension.BASE_CURRENCY: "investment_constraints.base_currency",
            DiscoveryDimension.TAX_RESIDENCY: "investment_constraints.tax_residency",
            DiscoveryDimension.ACCOUNT_ENTITY_TYPE: "account_background.account_entity_type",
            DiscoveryDimension.AUM_ALLOCATED: "account_background.aum_allocated",
            DiscoveryDimension.EXECUTION_MODE: "account_background.execution_mode",
            DiscoveryDimension.FINANCIAL_LITERACY: "persona_traits.financial_literacy",
            DiscoveryDimension.WEALTH_ORIGIN_DNA: "persona_traits.wealth_origin_dna",
            DiscoveryDimension.BEHAVIORAL_RISK_PROFILE: "persona_traits.behavioral_risk_profile",
        }.get(dimension)

    def _derive_risk_budget(self, risk_boundaries: RiskBoundaries) -> RiskBudget:
        conservative_signals = 0
        aggressive_signals = 0
        if risk_boundaries.max_drawdown_limit_pct is not None:
            if risk_boundaries.max_drawdown_limit_pct <= Decimal("10"):
                conservative_signals += 1
            elif risk_boundaries.max_drawdown_limit_pct >= Decimal("20"):
                aggressive_signals += 1
        if risk_boundaries.max_annual_volatility_pct is not None:
            if risk_boundaries.max_annual_volatility_pct <= Decimal("12"):
                conservative_signals += 1
            elif risk_boundaries.max_annual_volatility_pct >= Decimal("25"):
                aggressive_signals += 1
        if risk_boundaries.max_leverage_ratio is not None:
            if risk_boundaries.max_leverage_ratio == Decimal("0"):
                conservative_signals += 1
            elif risk_boundaries.max_leverage_ratio > Decimal("1"):
                aggressive_signals += 1
        if aggressive_signals >= 2:
            return RiskBudget.HIGH
        if conservative_signals >= 2:
            return RiskBudget.LOW
        return RiskBudget.MEDIUM

    def _derive_persona_style(
        self,
        risk_budget: RiskBudget,
        financial_objectives: FinancialObjectives,
        account_background: AccountBackground,
    ) -> str:
        if financial_objectives.annual_liquidity_need and financial_objectives.annual_liquidity_need > 0:
            return "cash-flow aware"
        if account_background.execution_mode is ExecutionMode.DISCRETIONARY:
            return "delegated systematic"
        return {
            RiskBudget.LOW: "capital preservation",
            RiskBudget.MEDIUM: "balanced",
            RiskBudget.HIGH: "growth oriented",
        }[risk_budget]

    def _build_mandate_summary(
        self,
        financial_objectives: FinancialObjectives,
        risk_boundaries: RiskBoundaries,
        investment_constraints: InvestmentConstraints,
        account_background: AccountBackground,
        risk_budget: RiskBudget,
    ) -> str:
        target = self._stringify(financial_objectives.target_annual_return_pct) or "unspecified"
        horizon = self._stringify(financial_objectives.investment_horizon_years) or "unspecified"
        drawdown = self._stringify(risk_boundaries.max_drawdown_limit_pct) or "unspecified"
        currency = investment_constraints.base_currency or "portfolio base currency not set"
        execution_mode = account_background.execution_mode.value if account_background.execution_mode else "execution mode not set"
        return (
            f"Target {target}% annual return over {horizon} years with {risk_budget.value} risk budget, "
            f"max drawdown limit {drawdown}%, base currency {currency}, and execution mode {execution_mode}."
        )

    def _to_decimal(self, value: Any) -> Decimal | None:
        if value in (None, ""):
            return None
        try:
            return Decimal(str(value))
        except (InvalidOperation, ValueError):
            return None

    def _parse_decimal_strict(self, dimension: DiscoveryDimension, value: Any) -> Decimal | None:
        parsed = self._to_decimal(value)
        if parsed is None and value not in (None, ""):
            raise InvalidDiscoveryInterpretationError(
                f"{dimension.value} must use FinKernel's predefined decimal format."
            )
        return parsed

    def _to_int(self, value: Any) -> int | None:
        if value in (None, ""):
            return None
        try:
            return int(value)
        except (TypeError, ValueError):
            return None

    def _parse_int_strict(self, dimension: DiscoveryDimension, value: Any) -> int | None:
        parsed = self._to_int(value)
        if parsed is None and value not in (None, ""):
            raise InvalidDiscoveryInterpretationError(
                f"{dimension.value} must use FinKernel's predefined integer format."
            )
        return parsed

    def _parse_enum_strict(self, enum_type, dimension: DiscoveryDimension, value: Any):
        try:
            return enum_type(str(value))
        except ValueError as exc:
            raise InvalidDiscoveryInterpretationError(
                f"{dimension.value} must use one of FinKernel's predefined enum values."
            ) from exc

    def _coerce_text(self, value: Any, *, uppercase: bool = False) -> str | None:
        if value in (None, ""):
            return None
        text = str(value).strip()
        if not text:
            return None
        return text.upper() if uppercase else text

    def _stringify(self, value: Any) -> str:
        return "" if value in (None, "") else str(value)

    def _slugify_profile_id(self, preferred_name: str, owner_id: str) -> str:
        base = re.sub(r"[^a-z0-9]+", "-", preferred_name.lower()).strip("-") or "profile"
        owner = re.sub(r"[^a-z0-9]+", "-", owner_id.lower()).strip("-") or "owner"
        return f"{owner}-{base}"

    def _dimensions_for_update_choice(self, update_choice: PersonaUpdateChoice | None) -> list[DiscoveryDimension]:
        if update_choice is None:
            return []
        return list(UPDATE_CHOICE_DIMENSIONS.get(update_choice, []))

    def _normalize_dimensions(self, dimensions: list[DiscoveryDimension]) -> list[DiscoveryDimension]:
        return list(dict.fromkeys(dimensions))

    def _allowed_dimensions_for_section(
        self,
        session: DiscoverySession,
        section: DiscoveryPillar,
    ) -> list[DiscoveryDimension]:
        target_dimensions = set(session.target_dimensions or ALL_REQUIRED_DIMENSIONS)
        return [dimension for dimension in PILLAR_DIMENSIONS[section] if dimension in target_dimensions]

    def _validate_interpretation_packet(
        self,
        session: DiscoverySession,
        packet: DiscoveryInterpretationPacket,
    ) -> list[DiscoveryDimension]:
        allowed_dimensions = self._allowed_dimensions_for_section(session, packet.section)
        if not allowed_dimensions:
            raise InvalidDiscoveryInterpretationError(
                f"{packet.section.value} is not part of the current discovery pass."
            )

        invalid_covered = [dimension for dimension in packet.covered_dimensions if dimension not in allowed_dimensions]
        invalid_structured = [update.dimension for update in packet.structured_field_updates if update.dimension not in allowed_dimensions]
        invalid_narrative = [update.dimension for update in packet.narrative_dimension_updates if update.dimension not in allowed_dimensions]

        invalid_dimensions = list(dict.fromkeys(invalid_covered + invalid_structured + invalid_narrative))
        if invalid_dimensions:
            raise InvalidDiscoveryInterpretationError(
                "The interpretation packet updated dimensions outside the current section scope: "
                + ", ".join(dimension.value for dimension in invalid_dimensions)
            )

        duplicated_dimensions = self._find_duplicate_dimensions(packet.covered_dimensions)
        duplicated_dimensions.extend(
            dimension
            for dimension in self._find_duplicate_dimensions([update.dimension for update in packet.structured_field_updates])
            if dimension not in duplicated_dimensions
        )
        duplicated_dimensions.extend(
            dimension
            for dimension in self._find_duplicate_dimensions([update.dimension for update in packet.narrative_dimension_updates])
            if dimension not in duplicated_dimensions
        )
        if duplicated_dimensions:
            raise InvalidDiscoveryInterpretationError(
                "The interpretation packet repeated dimensions in the same turn: "
                + ", ".join(dimension.value for dimension in duplicated_dimensions)
            )

        invalid_gap_dimensions = [
            issue.dimension
            for issue in packet.dimension_remaining_gaps
            if issue.dimension is not None and issue.dimension not in allowed_dimensions
        ]
        invalid_conflict_dimensions = [
            issue.dimension
            for issue in packet.dimension_conflict_notes
            if issue.dimension is not None and issue.dimension not in allowed_dimensions
        ]
        invalid_issue_dimensions = list(dict.fromkeys(invalid_gap_dimensions + invalid_conflict_dimensions))
        if invalid_issue_dimensions:
            raise InvalidDiscoveryInterpretationError(
                "The interpretation packet attached gaps or conflicts to dimensions outside the current section scope: "
                + ", ".join(dimension.value for dimension in invalid_issue_dimensions)
            )

        if packet.section_complete and (
            packet.remaining_gaps
            or packet.dimension_remaining_gaps
            or packet.conflict_notes
            or packet.dimension_conflict_notes
        ):
            raise InvalidDiscoveryInterpretationError(
                "section_complete cannot be true while unresolved gaps or conflicts are still present."
            )

        return allowed_dimensions

    def _clean_issue_notes(self, notes: list[str]) -> list[str]:
        return list(dict.fromkeys(note.strip() for note in notes if note.strip()))

    def _dimension_issue_notes(self, issues: list[DimensionIssue]) -> dict[DiscoveryDimension, list[str]]:
        notes_by_dimension: dict[DiscoveryDimension, list[str]] = {}
        for issue in issues:
            if issue.dimension is None:
                continue
            note = issue.note.strip()
            if not note:
                continue
            existing = notes_by_dimension.setdefault(issue.dimension, [])
            if note not in existing:
                existing.append(note)
        return notes_by_dimension

    def _section_issue_notes(self, issues: list[DimensionIssue]) -> list[str]:
        return list(dict.fromkeys(issue.note.strip() for issue in issues if issue.dimension is None and issue.note.strip()))

    def _find_duplicate_dimensions(self, dimensions: list[DiscoveryDimension]) -> list[DiscoveryDimension]:
        seen: set[DiscoveryDimension] = set()
        duplicates: list[DiscoveryDimension] = []
        for dimension in dimensions:
            if dimension in seen and dimension not in duplicates:
                duplicates.append(dimension)
            seen.add(dimension)
        return duplicates

    def _dimension_requires_more_work(self, state: DimensionState) -> bool:
        return state.coverage_score < 2 or bool(state.pending_gaps) or state.conflict_flag

    def _mark_dimensions_for_refresh(self, session: DiscoverySession, dimensions: list[DiscoveryDimension]) -> None:
        for dimension in self._normalize_dimensions(dimensions):
            state = self._get_dimension_state(session, dimension)
            state.coverage_score = 0
            state.confidence_score = 0
            state.evidence_score = 0
            state.depth_score = 0
            state.conflict_flag = False
            state.last_updated_at = None
            state.extracted_facts = []
            state.pending_gaps = ["This dimension still needs fresh discovery in the current update pass."]
            state.normalized_value = None

    def _build_section_coverage_from_session(
        self,
        session: DiscoverySession,
    ) -> list[SectionCoverageSnapshot]:
        states = {state.dimension: state for state in session.dimension_states}
        target_dimensions = set(session.target_dimensions or ALL_REQUIRED_DIMENSIONS)
        snapshots: list[SectionCoverageSnapshot] = []
        for pillar, dimensions in PILLAR_DIMENSIONS.items():
            section_states = [states[dimension] for dimension in dimensions]
            section_target_dimensions = [dimension for dimension in dimensions if dimension in target_dimensions]
            covered_dimensions = [
                state.dimension
                for state in section_states
                if state.coverage_score >= 2 and not state.pending_gaps
            ]
            outstanding_dimensions = [
                dimension
                for dimension in section_target_dimensions
                if self._dimension_requires_more_work(states[dimension])
            ]
            touched_dimensions = [state.dimension for state in section_states if state.coverage_score > 0 or state.extracted_facts]
            progress_percent = int(round((len(covered_dimensions) / len(dimensions)) * 100)) if dimensions else 0
            if len(covered_dimensions) == len(dimensions):
                status = SectionCoverageStatus.COVERED
            elif touched_dimensions:
                status = SectionCoverageStatus.IN_PROGRESS
            else:
                status = SectionCoverageStatus.NOT_STARTED

            remaining_gaps = [
                gap
                for state in section_states
                for gap in state.pending_gaps
            ]
            conflict_notes = [
                f"{state.dimension.value} still contains unresolved conflicting signals."
                for state in section_states
                if state.conflict_flag
            ]
            confidence_label = self._confidence_label_from_scores(section_states)
            evidence_quality_label = self._evidence_quality_label_from_scores(section_states)
            blocked_by_conflicts = any(state.conflict_flag for state in section_states)
            last_updated_at = max(
                (state.last_updated_at for state in section_states if state.last_updated_at is not None),
                default=None,
            )

            snapshots.append(
                SectionCoverageSnapshot(
                    section=pillar,
                    status=status,
                    target_dimensions=section_target_dimensions,
                    outstanding_dimensions=outstanding_dimensions,
                    covered_dimensions=covered_dimensions,
                    covered_dimension_count=len(covered_dimensions),
                    total_dimension_count=len(dimensions),
                    progress_percent=progress_percent,
                    remaining_gaps=list(dict.fromkeys(remaining_gaps)),
                    conflict_notes=list(dict.fromkeys(conflict_notes)),
                    confidence_label=confidence_label,
                    evidence_quality_label=evidence_quality_label,
                    blocked_by_conflicts=blocked_by_conflicts,
                    last_updated_at=last_updated_at,
                )
            )
        return snapshots

    def _build_discovery_state(self, session: DiscoverySession) -> ProfileDiscoveryState:
        section_coverage = session.section_coverage or self._build_section_coverage_from_session(session)
        working_snapshot = session.working_profile_snapshot or WorkingProfileSnapshot()
        current_section = self._next_incomplete_section(section_coverage)
        readiness = self._build_readiness(session)
        return ProfileDiscoveryState(
            session_id=session.session_id,
            owner_id=session.owner_id,
            workflow_kind=session.workflow_kind,
            status=session.status,
            source_profile_id=session.source_profile_id,
            current_section=current_section,
            starter_question=self._build_starter_question(session, current_section, section_coverage),
            target_dimensions=session.target_dimensions,
            section_coverage=section_coverage,
            working_profile_snapshot=working_snapshot,
            recent_turns=session.conversation_turns[-5:],
            recent_interpretations=session.interpretation_history[-5:],
            notes=readiness.notes,
        )

    def _next_incomplete_section(self, section_coverage: list[SectionCoverageSnapshot]) -> DiscoveryPillar | None:
        for snapshot in section_coverage:
            if snapshot.status is not SectionCoverageStatus.COVERED:
                return snapshot.section
        return None

    def _build_starter_question(
        self,
        session: DiscoverySession,
        current_section: DiscoveryPillar | None,
        section_coverage: list[SectionCoverageSnapshot],
    ) -> DiscoveryQuestion | None:
        if current_section is None:
            return None
        snapshot = next((item for item in section_coverage if item.section is current_section), None)
        if snapshot is None or snapshot.status is not SectionCoverageStatus.NOT_STARTED:
            return None
        prompt_text, why_this_matters = SECTION_STARTER_QUESTIONS[current_section]
        return DiscoveryQuestion(
            question_id=f"starter-{session.session_id}-{current_section.value}",
            session_id=session.session_id,
            dimension=PILLAR_DIMENSIONS[current_section][0],
            pillar=current_section,
            question_type=DiscoveryQuestionType.STARTER,
            source_type=DiscoveryQuestionSource.STARTER_BANK,
            prompt_text=prompt_text,
            why_this_matters=why_this_matters,
            expected_answer_shape=ExpectedAnswerShape.OPEN_TEXT,
        )

    def _default_evidence_dimension(
        self,
        packet: DiscoveryInterpretationPacket,
        touched_dimensions: set[DiscoveryDimension],
    ) -> DiscoveryDimension | None:
        if packet.covered_dimensions:
            return packet.covered_dimensions[0]
        if packet.structured_field_updates:
            return packet.structured_field_updates[0].dimension
        if packet.narrative_dimension_updates:
            return packet.narrative_dimension_updates[0].dimension
        if touched_dimensions:
            return sorted(touched_dimensions, key=lambda dimension: dimension.value)[0]
        return None

    def _apply_structured_field_update(self, snapshot: WorkingProfileSnapshot, update: StructuredFieldUpdate) -> Any:
        value = self._validate_structured_field_value(update.dimension, update.value)
        if update.dimension is DiscoveryDimension.TARGET_ANNUAL_RETURN:
            snapshot.financial_objectives.target_annual_return_pct = value
        elif update.dimension is DiscoveryDimension.INVESTMENT_HORIZON:
            snapshot.financial_objectives.investment_horizon_years = value
        elif update.dimension is DiscoveryDimension.ANNUAL_LIQUIDITY_NEED:
            snapshot.financial_objectives.annual_liquidity_need = value
        elif update.dimension is DiscoveryDimension.LIQUIDITY_FREQUENCY:
            snapshot.financial_objectives.liquidity_frequency = value
        elif update.dimension is DiscoveryDimension.MAX_DRAWDOWN_LIMIT:
            snapshot.risk_boundaries.max_drawdown_limit_pct = value
        elif update.dimension is DiscoveryDimension.MAX_ANNUAL_VOLATILITY:
            snapshot.risk_boundaries.max_annual_volatility_pct = value
        elif update.dimension is DiscoveryDimension.MAX_LEVERAGE_RATIO:
            snapshot.risk_boundaries.max_leverage_ratio = value
        elif update.dimension is DiscoveryDimension.SINGLE_ASSET_CAP:
            snapshot.risk_boundaries.single_asset_cap_pct = value
        elif update.dimension is DiscoveryDimension.BLOCKED_SECTORS:
            snapshot.investment_constraints.blocked_sectors = value or []
        elif update.dimension is DiscoveryDimension.BLOCKED_TICKERS:
            snapshot.investment_constraints.blocked_tickers = value or []
        elif update.dimension is DiscoveryDimension.BASE_CURRENCY:
            snapshot.investment_constraints.base_currency = value
        elif update.dimension is DiscoveryDimension.TAX_RESIDENCY:
            snapshot.investment_constraints.tax_residency = value
        elif update.dimension is DiscoveryDimension.ACCOUNT_ENTITY_TYPE:
            snapshot.account_background.account_entity_type = value
        elif update.dimension is DiscoveryDimension.AUM_ALLOCATED:
            snapshot.account_background.aum_allocated = value
        elif update.dimension is DiscoveryDimension.EXECUTION_MODE:
            snapshot.account_background.execution_mode = value
        else:
            raise InvalidDiscoveryInterpretationError(f"{update.dimension.value} is not a structured field.")
        return value

    def _apply_narrative_dimension_update(self, snapshot: WorkingProfileSnapshot, update: NarrativeDimensionUpdate) -> None:
        if update.dimension is DiscoveryDimension.FINANCIAL_LITERACY:
            snapshot.persona_traits.financial_literacy = update.text.strip()
            return
        if update.dimension is DiscoveryDimension.WEALTH_ORIGIN_DNA:
            snapshot.persona_traits.wealth_origin_dna = update.text.strip()
            return
        if update.dimension is DiscoveryDimension.BEHAVIORAL_RISK_PROFILE:
            snapshot.persona_traits.behavioral_risk_profile = update.text.strip()
            return
        raise InvalidDiscoveryInterpretationError(f"{update.dimension.value} is not a narrative profile dimension.")

    def _append_evidence_snippet(self, snapshot: WorkingProfileSnapshot, snippet: EvidenceSnippet) -> None:
        candidate = {
            "dimension": snippet.dimension.value if snippet.dimension else None,
            "excerpt": snippet.excerpt.strip(),
            "rationale": snippet.rationale,
            "captured_at": datetime.now(UTC).isoformat(),
        }
        if candidate["excerpt"] and candidate not in snapshot.persona_evidence:
            snapshot.persona_evidence.append(candidate)

    def _append_long_term_memory(self, snapshot: WorkingProfileSnapshot, candidate: NarrativeMemoryCandidate) -> None:
        item = candidate.model_dump(mode="json")
        if item not in snapshot.long_term_memories:
            snapshot.long_term_memories.append(item)

    def _append_short_term_memory(self, snapshot: WorkingProfileSnapshot, candidate: ShortTermMemoryCandidate) -> None:
        item = {
            "theme": candidate.theme,
            "summary": candidate.summary,
            "source_dimension": candidate.source_dimension.value if candidate.source_dimension else None,
        }
        if item not in snapshot.short_term_memories:
            snapshot.short_term_memories.append(item)

    def _append_contextual_rule(self, snapshot: WorkingProfileSnapshot, candidate: ContextualRuleCandidate) -> None:
        item = candidate.model_dump(mode="json")
        if item not in snapshot.contextual_rules:
            snapshot.contextual_rules.append(item)

    def _validate_structured_field_value(self, dimension: DiscoveryDimension, value: Any) -> Any:
        if value is None:
            return None
        if dimension in {
            DiscoveryDimension.TARGET_ANNUAL_RETURN,
            DiscoveryDimension.ANNUAL_LIQUIDITY_NEED,
            DiscoveryDimension.MAX_DRAWDOWN_LIMIT,
            DiscoveryDimension.MAX_ANNUAL_VOLATILITY,
            DiscoveryDimension.MAX_LEVERAGE_RATIO,
            DiscoveryDimension.SINGLE_ASSET_CAP,
            DiscoveryDimension.AUM_ALLOCATED,
        }:
            return self._parse_decimal_strict(dimension, value)
        if dimension is DiscoveryDimension.INVESTMENT_HORIZON:
            return self._parse_int_strict(dimension, value)
        if dimension is DiscoveryDimension.LIQUIDITY_FREQUENCY:
            return self._parse_enum_strict(LiquidityFrequency, dimension, value)
        if dimension is DiscoveryDimension.ACCOUNT_ENTITY_TYPE:
            return self._parse_enum_strict(AccountEntityType, dimension, value)
        if dimension is DiscoveryDimension.EXECUTION_MODE:
            return self._parse_enum_strict(ExecutionMode, dimension, value)
        if dimension in {DiscoveryDimension.BLOCKED_SECTORS, DiscoveryDimension.BLOCKED_TICKERS}:
            if not isinstance(value, list):
                raise InvalidDiscoveryInterpretationError(f"{dimension.value} must be returned as a list.")
            cleaned = {str(item).strip() for item in value if str(item).strip()}
            return sorted(cleaned)
        if dimension is DiscoveryDimension.BASE_CURRENCY:
            text = self._coerce_text(value, uppercase=True)
            return text
        if dimension is DiscoveryDimension.TAX_RESIDENCY:
            return self._coerce_text(value)
        raise InvalidDiscoveryInterpretationError(f"{dimension.value} is not a supported structured field.")

    def _confidence_score_from_label(self, label: ConfidenceLabel) -> int:
        return {
            ConfidenceLabel.LOW: 1,
            ConfidenceLabel.MEDIUM: 2,
            ConfidenceLabel.HIGH: 3,
        }[label]

    def _confidence_label_from_scores(self, states: list[DimensionState]) -> ConfidenceLabel:
        scored = [state.confidence_score for state in states if state.coverage_score > 0]
        if not scored:
            return ConfidenceLabel.LOW
        minimum = min(scored)
        if minimum >= 3:
            return ConfidenceLabel.HIGH
        if minimum >= 2:
            return ConfidenceLabel.MEDIUM
        return ConfidenceLabel.LOW

    def _evidence_quality_label_from_scores(self, states: list[DimensionState]) -> EvidenceQualityLabel:
        scored = [state.evidence_score for state in states if state.coverage_score > 0]
        if not scored:
            return EvidenceQualityLabel.LOW
        minimum = min(scored)
        if minimum >= 3:
            return EvidenceQualityLabel.HIGH
        if minimum >= 2:
            return EvidenceQualityLabel.MEDIUM
        return EvidenceQualityLabel.LOW

    def _build_readiness(self, session: DiscoverySession) -> DraftReadinessAssessment:
        target_dimensions = self._normalize_dimensions(session.target_dimensions or list(ALL_REQUIRED_DIMENSIONS))
        unmet_dimensions: list[DiscoveryDimension] = []
        notes: list[str] = []
        for dimension in target_dimensions:
            state = self._get_dimension_state(session, dimension)
            if state.coverage_score < 2:
                unmet_dimensions.append(dimension)
                notes.append(f"{dimension.value} still needs confirmed coverage.")
                continue
            if state.pending_gaps:
                unmet_dimensions.append(dimension)
                notes.extend(f"{dimension.value}: {gap}" for gap in state.pending_gaps)
                continue
            if state.conflict_flag:
                unmet_dimensions.append(dimension)
                notes.append(f"{dimension.value} still contains unresolved conflicting signals.")
        return DraftReadinessAssessment(
            ready=not unmet_dimensions,
            unmet_dimensions=unmet_dimensions,
            notes=list(dict.fromkeys(notes)),
        )

    def _get_dimension_state(self, session: DiscoverySession, dimension: DiscoveryDimension) -> DimensionState:
        for state in session.dimension_states:
            if state.dimension is dimension:
                return state
        raise KeyError(f"Missing dimension state for {dimension.value}")

    def _session_payload(self, session: DiscoverySession) -> dict[str, Any]:
        return session.model_dump(
            mode="json",
            exclude={"conversation_turns", "interpretation_history"},
        )

    def _save_session(
        self,
        session: DiscoverySession,
        *,
        new_turn: DiscoveryConversationTurn | None = None,
        new_interpretation: AcceptedInterpretationPacket | None = None,
    ) -> None:
        record = self._session_payload(session)
        with self._session_scope() as db_session:
            self.session_repository.upsert(
                db_session,
                DiscoverySessionModel(
                    session_id=session.session_id,
                    owner_id=session.owner_id,
                    status=session.status.value,
                    payload=record,
                ),
            )
            if new_turn is not None:
                self.turn_repository.add(
                    db_session,
                    DiscoveryConversationTurnModel(
                        turn_id=new_turn.turn_id,
                        session_id=session.session_id,
                        owner_id=session.owner_id,
                        section=new_turn.section.value,
                        payload=new_turn.model_dump(mode="json"),
                        answered_at=new_turn.answered_at,
                    ),
                )
            if new_interpretation is not None:
                self.interpretation_repository.add(
                    db_session,
                    DiscoveryInterpretationModel(
                        interpretation_id=new_interpretation.interpretation_id,
                        session_id=session.session_id,
                        owner_id=session.owner_id,
                        section=new_interpretation.packet.section.value,
                        payload=new_interpretation.model_dump(mode="json"),
                        stored_at=new_interpretation.stored_at,
                    ),
                )

    def _save_draft(self, draft: ProfileDraft) -> None:
        with self._session_scope() as db_session:
            self.draft_repository.upsert(
                db_session,
                ProfileDraftModel(
                    draft_id=draft.draft_id,
                    session_id=draft.session_id,
                    owner_id=draft.owner_id,
                    payload=draft.model_dump(mode="json"),
                ),
            )

    def _mark_session_completed(self, session_id: str) -> None:
        session = self.get_session(session_id)
        session.status = DiscoverySessionStatus.COMPLETED
        self._save_session(session)

    @contextmanager
    def _session_scope(self) -> Iterator[Session]:
        session = self.session_factory()
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

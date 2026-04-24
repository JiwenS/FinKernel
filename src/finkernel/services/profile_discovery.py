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
    ConfirmProfileDraftRequest,
    ContextualRuleCandidate,
    DiscoveryAnswer,
    DiscoveryDimension,
    DiscoveryQuestion,
    DiscoveryQuestionSource,
    DiscoveryQuestionType,
    DiscoverySession,
    DiscoverySessionStatus,
    DiscoveryWorkflowKind,
    DimensionState,
    DraftReadinessAssessment,
    NarrativeMemoryCandidate,
    PersonaAssessmentReason,
    PersonaAssessmentState,
    PersonaAssessmentStatus,
    PersonaUpdateChoice,
    PersonaUpdateOption,
    ProfileDraft,
    ReviewProfileRequest,
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
    PersonaTraits,
    PersonaSourcePacket,
    ProfileLifecycleStatus,
    RiskBoundaries,
    RiskBudget,
    RiskProfileSummary,
)
from finkernel.services.persona_markdown import build_persona_evidence_from_answers
from finkernel.services.profiles import ProfileStore
from finkernel.services.question_planner import MANDATORY_DIMENSIONS, QuestionPlanner, build_empty_dimension_states
from finkernel.storage.models import DiscoverySessionModel, ProfileDraftModel
from finkernel.storage.repositories import DiscoverySessionRepository, ProfileDraftRepository

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
    PersonaUpdateChoice.FULL_REASSESSMENT: list(MANDATORY_DIMENSIONS),
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


class DiscoveryNotReadyError(ValueError):
    pass


class ProfileDiscoveryService:
    def __init__(
        self,
        *,
        settings: Settings,
        session_factory: sessionmaker[Session],
        profile_store: ProfileStore,
        planner: QuestionPlanner | None = None,
        session_repository: DiscoverySessionRepository | None = None,
        draft_repository: ProfileDraftRepository | None = None,
    ) -> None:
        self.settings = settings
        self.session_factory = session_factory
        self.profile_store = profile_store
        self.planner = planner or QuestionPlanner()
        self.session_repository = session_repository or DiscoverySessionRepository()
        self.draft_repository = draft_repository or ProfileDraftRepository()

    def start_discovery(self, *, owner_id: str, preferred_profile_name: str | None = None) -> DiscoverySession:
        session = DiscoverySession(
            session_id=str(uuid4()),
            owner_id=owner_id,
            preferred_profile_name=preferred_profile_name,
            workflow_kind=DiscoveryWorkflowKind.ADD,
            dimension_states=build_empty_dimension_states(),
        )
        next_question = self.planner.choose_next_question(session)
        if next_question is not None:
            session.current_question_id = next_question.question_id
            session.current_question = next_question
            session.asked_question_ids.append(next_question.question_id)
        self._save_session(session, next_question=next_question)
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
        session = DiscoverySession(
            session_id=session_id,
            owner_id=profile.owner_id,
            preferred_profile_name=profile.display_name,
            workflow_kind=DiscoveryWorkflowKind.UPDATE,
            source_profile_id=profile.profile_id,
            update_choice=update_choice,
            update_notes=update_notes,
            target_dimensions=selected_dimensions,
            dimension_states=build_empty_dimension_states(),
        )
        seeded_answers = self._seed_answers_from_profile(
            profile,
            session_id=session_id,
            payload=ReviewProfileRequest(
                trigger=self._build_update_trigger(update_choice, selected_dimensions),
                notes=update_notes,
            ),
        )
        for answer in seeded_answers:
            session.answers.append(answer)
            self.planner.update_dimension_state(session, answer)
        self._reset_target_dimensions(session, selected_dimensions)
        session.updated_at = datetime.now(UTC)
        readiness = self.planner.build_readiness(session)
        if readiness.ready:
            session.status = DiscoverySessionStatus.DRAFT_READY
            self._save_session(session, next_question=None)
            return session

        next_question = self.planner.choose_next_question(session)
        if next_question is not None:
            session.current_question_id = next_question.question_id
            session.current_question = next_question
            session.asked_question_ids.append(next_question.question_id)
        self._save_session(session, next_question=next_question)
        return session

    def get_session(self, session_id: str) -> DiscoverySession:
        with self._session_scope() as session:
            model = self.session_repository.get(session, session_id)
            if model is None:
                raise KeyError(f"Unknown discovery_session_id: {session_id}")
            return DiscoverySession.model_validate(model.payload)

    def get_next_question(self, session_id: str) -> DiscoveryQuestion | None:
        session, current_question = self._load_session_with_question(session_id)
        if session.status is DiscoverySessionStatus.DRAFT_READY:
            return None
        if current_question is not None and current_question.question_id == session.current_question_id:
            return current_question

        next_question = self.planner.choose_next_question(session)
        if next_question is None:
            session.status = DiscoverySessionStatus.DRAFT_READY
            session.current_question_id = None
            session.current_question = None
            self._save_session(session, next_question=None)
            return None
        session.current_question_id = next_question.question_id
        session.current_question = next_question
        session.asked_question_ids.append(next_question.question_id)
        self._save_session(session, next_question=next_question)
        return next_question

    def submit_answer(self, *, session_id: str, answer_text: str, question_id: str | None = None) -> DiscoverySession:
        session, current_question = self._load_session_with_question(session_id)
        question = current_question if question_id is None else self._find_question(session_id=session_id, question_id=question_id)
        if question is None:
            raise KeyError(f"No active question is available for discovery session {session_id}.")

        answer = DiscoveryAnswer(
            answer_id=str(uuid4()),
            session_id=session_id,
            question_id=question.question_id,
            dimension=question.dimension,
            answer_text=answer_text.strip(),
            question_type=question.question_type,
            source_type=question.source_type,
        )
        session.answers.append(answer)
        self.planner.update_dimension_state(session, answer)
        session.updated_at = datetime.now(UTC)
        readiness = self.planner.build_readiness(session)
        session.status = DiscoverySessionStatus.DRAFT_READY if readiness.ready else DiscoverySessionStatus.DISCOVERY_IN_PROGRESS
        session.current_question_id = None
        session.current_question = None
        self._save_session(session, next_question=None)
        return session

    def generate_draft(self, session_id: str) -> ProfileDraft:
        session = self.get_session(session_id)
        readiness = self.planner.build_readiness(session)
        if not readiness.ready:
            raise DiscoveryNotReadyError(f"Discovery session {session_id} is not ready for draft generation.")

        draft = self._build_draft(session, readiness)
        self._save_draft(draft)
        session.status = DiscoverySessionStatus.DRAFT_READY
        current_question = self._find_question(session_id=session_id, question_id=session.current_question_id) if session.current_question_id else None
        self._save_session(session, next_question=current_question)
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

    def start_review(self, *, profile_id: str, payload: ReviewProfileRequest) -> DiscoverySession:
        profile = self.profile_store.get(profile_id, require_active=False)
        session_id = str(uuid4())
        session = DiscoverySession(
            session_id=session_id,
            owner_id=profile.owner_id,
            preferred_profile_name=profile.display_name,
            workflow_kind=DiscoveryWorkflowKind.UPDATE,
            source_profile_id=profile.profile_id,
            update_choice=PersonaUpdateChoice.FULL_REASSESSMENT,
            update_notes=payload.notes,
            target_dimensions=list(MANDATORY_DIMENSIONS),
            status=DiscoverySessionStatus.DRAFT_READY,
            dimension_states=self._seed_dimension_states(),
            answers=self._seed_answers_from_profile(profile, session_id=session_id, payload=payload),
        )
        session.updated_at = datetime.now(UTC)
        self._save_session(session, next_question=None)
        return session

    def assess_profile_completeness(self, profile_id: str, *, version: int | None = None) -> DraftReadinessAssessment:
        profile = self.get_profile(profile_id, version=version)
        session = DiscoverySession(
            session_id=f"assessment-{profile.profile_id}-{profile.version}",
            owner_id=profile.owner_id,
            preferred_profile_name=profile.display_name,
            workflow_kind=DiscoveryWorkflowKind.UPDATE,
            source_profile_id=profile.profile_id,
            dimension_states=build_empty_dimension_states(),
        )
        seeded_answers = self._seed_answers_from_profile(
            profile,
            session_id=session.session_id,
            payload=ReviewProfileRequest(trigger="persona_completeness_check"),
        )
        for answer in seeded_answers:
            session.answers.append(answer)
            self.planner.update_dimension_state(session, answer)
        readiness = self.planner.build_readiness(session)
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
                "persona_markdown": payload.persona_markdown or suggested.persona_markdown,
            }
        )
        self.profile_store.append_profile(final_profile)
        self._mark_session_completed(draft.session_id)
        return final_profile

    def _seed_dimension_states(self) -> list[DimensionState]:
        states = build_empty_dimension_states()
        for state in states:
            state.coverage_score = 3
            state.confidence_score = 3
            state.depth_score = 2
        return states

    def _seed_answers_from_profile(self, profile: PersonaProfile, *, session_id: str, payload: ReviewProfileRequest) -> list[DiscoveryAnswer]:
        answers = self._seed_review_answers_from_evidence(profile)
        if not answers:
            answers = self._seed_review_answers_from_structured_profile(profile)
        if payload.notes:
            answers.append((DiscoveryDimension.BEHAVIORAL_RISK_PROFILE, f"Review note: {payload.notes}"))

        seeded_answers: list[DiscoveryAnswer] = []
        now = datetime.now(UTC)
        for index, (dimension, text) in enumerate(answers):
            if not text:
                continue
            seeded_answers.append(
                DiscoveryAnswer(
                    answer_id=str(uuid4()),
                    session_id=session_id,
                    question_id=f"seed-{index}-{dimension.value}",
                    dimension=dimension,
                    answer_text=text,
                    question_type=DiscoveryQuestionType.DEEPENING,
                    source_type=DiscoveryQuestionSource.RULE_TRIGGER,
                    answered_at=now,
                    extracted_signals=["review_seed"],
                )
            )
        return seeded_answers

    def _seed_review_answers_from_evidence(self, profile: PersonaProfile) -> list[tuple[DiscoveryDimension, str]]:
        answers: list[tuple[DiscoveryDimension, str]] = []
        seen_dimensions: set[DiscoveryDimension] = set()
        for item in profile.persona_evidence:
            raw_dimension = item.get("dimension")
            excerpt = str(item.get("excerpt") or "").strip()
            if not raw_dimension or not excerpt:
                continue
            try:
                dimension = DiscoveryDimension(str(raw_dimension))
            except ValueError:
                continue
            if dimension in seen_dimensions:
                continue
            answers.append((dimension, excerpt))
            seen_dimensions.add(dimension)
        return answers

    def _seed_review_answers_from_structured_profile(self, profile: PersonaProfile) -> list[tuple[DiscoveryDimension, str]]:
        financial = profile.financial_objectives
        risk = profile.risk_boundaries
        constraints = profile.investment_constraints
        background = profile.account_background
        traits = profile.persona_traits
        return [
            (DiscoveryDimension.TARGET_ANNUAL_RETURN, self._stringify(financial.target_annual_return_pct)),
            (DiscoveryDimension.INVESTMENT_HORIZON, self._stringify(financial.investment_horizon_years)),
            (DiscoveryDimension.ANNUAL_LIQUIDITY_NEED, self._stringify(financial.annual_liquidity_need)),
            (DiscoveryDimension.LIQUIDITY_FREQUENCY, financial.liquidity_frequency.value if financial.liquidity_frequency else ""),
            (DiscoveryDimension.MAX_DRAWDOWN_LIMIT, self._stringify(risk.max_drawdown_limit_pct)),
            (DiscoveryDimension.MAX_ANNUAL_VOLATILITY, self._stringify(risk.max_annual_volatility_pct)),
            (DiscoveryDimension.MAX_LEVERAGE_RATIO, self._stringify(risk.max_leverage_ratio)),
            (DiscoveryDimension.SINGLE_ASSET_CAP, self._stringify(risk.single_asset_cap_pct)),
            (DiscoveryDimension.BLOCKED_SECTORS, self._serialize_list(constraints.blocked_sectors) or "none"),
            (DiscoveryDimension.BLOCKED_TICKERS, self._serialize_list(constraints.blocked_tickers) or "none"),
            (DiscoveryDimension.BASE_CURRENCY, constraints.base_currency or ""),
            (DiscoveryDimension.TAX_RESIDENCY, constraints.tax_residency or ""),
            (DiscoveryDimension.ACCOUNT_ENTITY_TYPE, background.account_entity_type.value if background.account_entity_type else ""),
            (DiscoveryDimension.AUM_ALLOCATED, self._stringify(background.aum_allocated)),
            (DiscoveryDimension.EXECUTION_MODE, background.execution_mode.value if background.execution_mode else ""),
            (DiscoveryDimension.FINANCIAL_LITERACY, traits.financial_literacy or ""),
            (DiscoveryDimension.WEALTH_ORIGIN_DNA, traits.wealth_origin_dna or ""),
            (DiscoveryDimension.BEHAVIORAL_RISK_PROFILE, traits.behavioral_risk_profile or ""),
        ]

    def _serialize_list(self, items: list[str]) -> str:
        return ", ".join(items)

    def _stringify(self, value: Any) -> str:
        return "" if value in (None, "") else str(value)

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
                notes.insert(0, "All required persona sections are covered. Write persona markdown and confirm the draft.")
            else:
                notes.insert(0, "This update pass has enough evidence to write refreshed persona markdown and confirm a new version.")
            return PersonaAssessmentState(
                owner_id=session.owner_id,
                action=action,
                status=PersonaAssessmentStatus.DRAFT_READY,
                reason=PersonaAssessmentReason.PERSONA_READY_FOR_CONFIRMATION,
                recommended_next_action="write_or_refresh_persona_markdown_then_confirm_profile_draft",
                prompt_template_id=PROMPT_TEMPLATE_DRAFT_READY,
                active_profile_id=active_profile.profile_id if active_profile else draft.suggested_profile.profile_id,
                active_profile_version=active_profile.version if active_profile else None,
                persona_markdown_missing=not bool(active_profile.persona_markdown) if active_profile else True,
                discovery_session_id=session.session_id,
                profile_draft_id=draft.draft_id,
                selected_update_choice=session.update_choice,
                missing_dimensions=draft.readiness.unmet_dimensions,
                notes=notes,
            )

        question = session.current_question if session.current_question_id else None
        if question is None:
            question = self.get_next_question(session.session_id)
            session = self.get_session(session.session_id)
            if session.status is DiscoverySessionStatus.DRAFT_READY:
                return self._build_assessment_state_from_session(
                    session,
                    action=action,
                    reason=reason,
                    active_profile=active_profile,
                )

        readiness = self.planner.build_readiness(session)
        notes = list(readiness.notes)
        if active_profile is not None and not active_profile.persona_markdown:
            notes.append("Persona markdown is still missing.")
        if action is DiscoveryWorkflowKind.UPDATE and session.target_dimensions:
            notes.append(
                "Focused update sections: "
                + ", ".join(dimension.value for dimension in session.target_dimensions)
                + "."
            )
        return PersonaAssessmentState(
            owner_id=session.owner_id,
            action=action,
            status=PersonaAssessmentStatus.QUESTION_PENDING,
            reason=reason,
            recommended_next_action="ask_the_returned_question_then_submit_the_answer",
            prompt_template_id=PROMPT_TEMPLATE_ADD_QUESTION if action is DiscoveryWorkflowKind.ADD else PROMPT_TEMPLATE_UPDATE_QUESTION,
            active_profile_id=active_profile.profile_id if active_profile else None,
            active_profile_version=active_profile.version if active_profile else None,
            persona_markdown_missing=not bool(active_profile.persona_markdown) if active_profile else False,
            discovery_session_id=session.session_id,
            selected_update_choice=session.update_choice,
            missing_dimensions=readiness.unmet_dimensions,
            notes=notes,
            next_question=question,
        )

    def _build_draft(self, session: DiscoverySession, readiness: DraftReadinessAssessment) -> ProfileDraft:
        answer_map = {answer.dimension: answer.answer_text for answer in session.answers}
        normalized_map = {
            state.dimension: state.normalized_value
            for state in session.dimension_states
            if state.normalized_value is not None
        }
        preferred_name = session.preferred_profile_name or "Primary Risk Profile"
        profile_id = session.source_profile_id or self._slugify_profile_id(preferred_name, session.owner_id)
        financial_objectives = self._build_financial_objectives(normalized_map)
        risk_boundaries = self._build_risk_boundaries(normalized_map)
        investment_constraints = self._build_investment_constraints(normalized_map)
        account_background = self._build_account_background(normalized_map)
        persona_traits = self._build_persona_traits(normalized_map, answer_map)
        risk_budget = self._derive_risk_budget(risk_boundaries)
        mandate_summary = self._build_mandate_summary(
            financial_objectives,
            risk_boundaries,
            investment_constraints,
            account_background,
            risk_budget,
        )
        contextual_rules = self._build_contextual_rules(
            answer_map,
            financial_objectives,
            risk_boundaries,
            investment_constraints,
            account_background,
        )
        long_term_memories = self._build_long_term_memories(answer_map, persona_traits)
        short_term_memories = self._build_short_term_memories(answer_map, financial_objectives)
        persona_evidence = build_persona_evidence_from_answers([answer.model_dump(mode="json") for answer in session.answers])
        suggested_profile = PersonaProfile(
            profile_id=profile_id,
            owner_id=session.owner_id,
            version=1,
            status=ProfileLifecycleStatus.PENDING_USER_CONFIRMATION,
            display_name=preferred_name,
            mandate_summary=mandate_summary,
            persona_style=self._derive_persona_style(risk_budget, financial_objectives, account_background),
            created_from="guided_discovery" if session.workflow_kind is DiscoveryWorkflowKind.ADD else "persona_update",
            risk_budget=risk_budget,
            financial_objectives=financial_objectives,
            risk_boundaries=risk_boundaries,
            investment_constraints=investment_constraints,
            account_background=account_background,
            persona_traits=persona_traits,
            contextual_rules=[item.model_dump(mode="json") for item in contextual_rules],
            long_term_memories=[item.model_dump(mode="json") for item in long_term_memories],
            short_term_memories=short_term_memories,
            persona_evidence=persona_evidence,
        )
        return ProfileDraft(
            draft_id=str(uuid4()),
            session_id=session.session_id,
            owner_id=session.owner_id,
            readiness=readiness,
            suggested_profile=suggested_profile,
            contextual_rules=contextual_rules,
            narrative_memories=long_term_memories,
        )

    def _build_financial_objectives(self, normalized_map: dict[DiscoveryDimension, Any]) -> FinancialObjectives:
        frequency = normalized_map.get(DiscoveryDimension.LIQUIDITY_FREQUENCY)
        return FinancialObjectives(
            target_annual_return_pct=self._to_decimal(normalized_map.get(DiscoveryDimension.TARGET_ANNUAL_RETURN)),
            investment_horizon_years=self._to_int(normalized_map.get(DiscoveryDimension.INVESTMENT_HORIZON)),
            annual_liquidity_need=self._to_decimal(normalized_map.get(DiscoveryDimension.ANNUAL_LIQUIDITY_NEED)),
            liquidity_frequency=LiquidityFrequency(str(frequency)) if frequency else None,
        )

    def _build_risk_boundaries(self, normalized_map: dict[DiscoveryDimension, Any]) -> RiskBoundaries:
        return RiskBoundaries(
            max_drawdown_limit_pct=self._to_decimal(normalized_map.get(DiscoveryDimension.MAX_DRAWDOWN_LIMIT)),
            max_annual_volatility_pct=self._to_decimal(normalized_map.get(DiscoveryDimension.MAX_ANNUAL_VOLATILITY)),
            max_leverage_ratio=self._to_decimal(normalized_map.get(DiscoveryDimension.MAX_LEVERAGE_RATIO)),
            single_asset_cap_pct=self._to_decimal(normalized_map.get(DiscoveryDimension.SINGLE_ASSET_CAP)),
        )

    def _build_investment_constraints(self, normalized_map: dict[DiscoveryDimension, Any]) -> InvestmentConstraints:
        return InvestmentConstraints(
            blocked_sectors=list(normalized_map.get(DiscoveryDimension.BLOCKED_SECTORS) or []),
            blocked_tickers=list(normalized_map.get(DiscoveryDimension.BLOCKED_TICKERS) or []),
            base_currency=self._coerce_text(normalized_map.get(DiscoveryDimension.BASE_CURRENCY), uppercase=True),
            tax_residency=self._coerce_text(normalized_map.get(DiscoveryDimension.TAX_RESIDENCY)),
        )

    def _build_account_background(self, normalized_map: dict[DiscoveryDimension, Any]) -> AccountBackground:
        entity_type = normalized_map.get(DiscoveryDimension.ACCOUNT_ENTITY_TYPE)
        execution_mode = normalized_map.get(DiscoveryDimension.EXECUTION_MODE)
        return AccountBackground(
            account_entity_type=AccountEntityType(str(entity_type)) if entity_type else None,
            aum_allocated=self._to_decimal(normalized_map.get(DiscoveryDimension.AUM_ALLOCATED)),
            execution_mode=ExecutionMode(str(execution_mode)) if execution_mode else None,
        )

    def _build_persona_traits(
        self,
        normalized_map: dict[DiscoveryDimension, Any],
        answer_map: dict[DiscoveryDimension, str],
    ) -> PersonaTraits:
        return PersonaTraits(
            financial_literacy=self._coerce_text(
                normalized_map.get(DiscoveryDimension.FINANCIAL_LITERACY) or answer_map.get(DiscoveryDimension.FINANCIAL_LITERACY)
            ),
            wealth_origin_dna=self._coerce_text(
                normalized_map.get(DiscoveryDimension.WEALTH_ORIGIN_DNA) or answer_map.get(DiscoveryDimension.WEALTH_ORIGIN_DNA)
            ),
            behavioral_risk_profile=self._coerce_text(
                normalized_map.get(DiscoveryDimension.BEHAVIORAL_RISK_PROFILE) or answer_map.get(DiscoveryDimension.BEHAVIORAL_RISK_PROFILE)
            ),
        )

    def _build_contextual_rules(
        self,
        answer_map: dict[DiscoveryDimension, str],
        financial_objectives: FinancialObjectives,
        risk_boundaries: RiskBoundaries,
        investment_constraints: InvestmentConstraints,
        account_background: AccountBackground,
    ) -> list[ContextualRuleCandidate]:
        rules: list[ContextualRuleCandidate] = []
        liquidity = answer_map.get(DiscoveryDimension.ANNUAL_LIQUIDITY_NEED, "")
        if financial_objectives.annual_liquidity_need and financial_objectives.annual_liquidity_need > 0:
            rules.append(
                ContextualRuleCandidate(
                    rule_text="Preserve liquidity reserves before increasing portfolio risk when recurring cash withdrawals are expected.",
                    reason="Derived from annual liquidity requirements.",
                )
            )
        if risk_boundaries.max_leverage_ratio == Decimal("0"):
            rules.append(
                ContextualRuleCandidate(
                    rule_text="Do not use leverage in portfolio construction or execution for this mandate.",
                    reason="Derived from the leverage boundary.",
                )
            )
        if risk_boundaries.single_asset_cap_pct is not None:
            rules.append(
                ContextualRuleCandidate(
                    rule_text="Continuously monitor single-asset concentration against the approved cap.",
                    reason="Derived from the single-asset concentration boundary.",
                )
            )
        if investment_constraints.blocked_sectors or investment_constraints.blocked_tickers:
            rules.append(
                ContextualRuleCandidate(
                    rule_text="Treat blocked sectors and blocked tickers as non-overridable filter rules unless the profile itself is updated.",
                    reason="Derived from explicit investment constraints.",
                )
            )
        if account_background.execution_mode is ExecutionMode.ADVISORY:
            rules.append(
                ContextualRuleCandidate(
                    rule_text="Require human confirmation before sending any trade for execution.",
                    reason="Derived from advisory execution mode.",
                )
            )
        if liquidity and re.search(r"\b(next|soon|month|quarter|year)\b", liquidity, re.IGNORECASE):
            rules.append(
                ContextualRuleCandidate(
                    rule_text="Keep short-horizon liquidity events visible in portfolio planning until they pass.",
                    reason="Derived from time-sensitive liquidity wording.",
                )
            )
        return rules

    def _build_long_term_memories(
        self,
        answer_map: dict[DiscoveryDimension, str],
        persona_traits: PersonaTraits,
    ) -> list[NarrativeMemoryCandidate]:
        items: list[NarrativeMemoryCandidate] = []
        for dimension, theme in (
            (DiscoveryDimension.WEALTH_ORIGIN_DNA, "wealth_origin_dna"),
            (DiscoveryDimension.BEHAVIORAL_RISK_PROFILE, "behavioral_risk_profile"),
            (DiscoveryDimension.FINANCIAL_LITERACY, "financial_literacy"),
        ):
            text = answer_map.get(dimension)
            if text and len(text.split()) >= 8:
                items.append(NarrativeMemoryCandidate(summary=text, theme=theme, source_dimension=dimension))
        for item in profile_long_memory_candidates_from_traits(persona_traits):
            if all(existing.summary != item.summary for existing in items):
                items.append(item)
        return items

    def _build_short_term_memories(
        self,
        answer_map: dict[DiscoveryDimension, str],
        financial_objectives: FinancialObjectives,
    ) -> list[dict[str, str]]:
        items: list[dict[str, str]] = []
        liquidity = answer_map.get(DiscoveryDimension.ANNUAL_LIQUIDITY_NEED)
        if liquidity and re.search(r"\b(within|month|months|week|weeks|soon|upcoming|next)\b", liquidity, re.IGNORECASE):
            items.append(
                {
                    "theme": "near_term_liquidity",
                    "summary": liquidity,
                    "source_dimension": DiscoveryDimension.ANNUAL_LIQUIDITY_NEED.value,
                }
            )
        behavioral = answer_map.get(DiscoveryDimension.BEHAVIORAL_RISK_PROFILE)
        if behavioral and re.search(r"\b(recent|lately|right now|currently|last week|last month|two weeks)\b", behavioral, re.IGNORECASE):
            items.append(
                {
                    "theme": "recent_market_emotion",
                    "summary": behavioral,
                    "source_dimension": DiscoveryDimension.BEHAVIORAL_RISK_PROFILE.value,
                }
            )
        if financial_objectives.liquidity_frequency in {LiquidityFrequency.MONTHLY, LiquidityFrequency.QUARTERLY}:
            items.append(
                {
                    "theme": "recurring_cash_flow",
                    "summary": f"Recurring liquidity cadence is {financial_objectives.liquidity_frequency.value}.",
                    "source_dimension": DiscoveryDimension.LIQUIDITY_FREQUENCY.value,
                }
            )
        return items

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

    def _to_int(self, value: Any) -> int | None:
        if value in (None, ""):
            return None
        try:
            return int(value)
        except (TypeError, ValueError):
            return None

    def _coerce_text(self, value: Any, *, uppercase: bool = False) -> str | None:
        if value in (None, ""):
            return None
        text = str(value).strip()
        if not text:
            return None
        return text.upper() if uppercase else text

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

    def _reset_target_dimensions(self, session: DiscoverySession, dimensions: list[DiscoveryDimension]) -> None:
        for dimension in self._normalize_dimensions(dimensions):
            state = self._get_dimension_state(session, dimension)
            state.coverage_score = 0
            state.confidence_score = 0
            state.depth_score = 0
            state.conflict_flag = False
            state.last_question_id = None
            state.last_updated_at = None
            state.extracted_facts = []
            state.pending_gaps = []
            state.normalized_value = None

    def _build_update_trigger(self, update_choice: PersonaUpdateChoice | None, target_dimensions: list[DiscoveryDimension]) -> str:
        if update_choice is not None:
            return f"assess_persona:{update_choice.value}"
        if target_dimensions:
            joined = ",".join(dimension.value for dimension in target_dimensions)
            return f"assess_persona:resume_missing_sections:{joined}"
        return "assess_persona:update"

    def _get_dimension_state(self, session: DiscoverySession, dimension: DiscoveryDimension) -> DimensionState:
        for state in session.dimension_states:
            if state.dimension is dimension:
                return state
        raise KeyError(f"Missing dimension state for {dimension.value}")

    def _load_session_with_question(self, session_id: str) -> tuple[DiscoverySession, DiscoveryQuestion | None]:
        session = self.get_session(session_id)
        question = self._find_question(session_id=session_id, question_id=session.current_question_id)
        return session, question

    def _save_session(self, session: DiscoverySession, *, next_question: DiscoveryQuestion | None) -> None:
        record = session.model_dump(mode="json")
        record["current_question"] = next_question.model_dump(mode="json") if next_question is not None else None
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

    def _find_question(self, *, session_id: str, question_id: str | None) -> DiscoveryQuestion | None:
        if question_id is None:
            return None
        session = self.get_session(session_id)
        if session.current_question is not None and session.current_question.question_id == question_id:
            return session.current_question
        return None

    def _mark_session_completed(self, session_id: str) -> None:
        session = self.get_session(session_id)
        session.status = DiscoverySessionStatus.COMPLETED
        session.current_question_id = None
        session.current_question = None
        self._save_session(session, next_question=None)

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


def profile_long_memory_candidates_from_traits(persona_traits: PersonaTraits) -> list[NarrativeMemoryCandidate]:
    items: list[NarrativeMemoryCandidate] = []
    for dimension, theme, text in (
        (DiscoveryDimension.FINANCIAL_LITERACY, "financial_literacy", persona_traits.financial_literacy),
        (DiscoveryDimension.WEALTH_ORIGIN_DNA, "wealth_origin_dna", persona_traits.wealth_origin_dna),
        (DiscoveryDimension.BEHAVIORAL_RISK_PROFILE, "behavioral_risk_profile", persona_traits.behavioral_risk_profile),
    ):
        if text and len(text.split()) >= 10:
            items.append(NarrativeMemoryCandidate(summary=text, theme=theme, source_dimension=dimension))
    return items

from __future__ import annotations

from contextlib import contextmanager
from datetime import UTC, datetime
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
    DimensionState,
    DraftReadinessAssessment,
    NarrativeMemoryCandidate,
    ProfileDraft,
    ReviewProfileRequest,
)
from finkernel.schemas.profile import DistilledProfileMemoryResponse, MemoryKind, PersonaProfile, PersonaSourcePacket, ProfileLifecycleStatus, RiskBudget, RiskProfileSummary
from finkernel.services.persona_markdown import build_persona_evidence_from_answers
from finkernel.services.profiles import ProfileStore
from finkernel.services.question_planner import QuestionPlanner, build_empty_dimension_states
from finkernel.storage.models import DiscoverySessionModel, ProfileDraftModel
from finkernel.storage.repositories import DiscoverySessionRepository, ProfileDraftRepository


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
            dimension_states=build_empty_dimension_states(),
        )
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
        self._save_session(session, next_question=self._find_question(session_id=session_id, question_id=session.current_question_id) if session.current_question_id else None)
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
            persona_markdown=profile.persona_markdown,
            persona_evidence=profile.persona_evidence,
            long_term_memories=profile.long_term_memories,
            short_term_memories=profile.short_term_memories,
            contextual_rules=profile.contextual_rules,
        )

    def get_risk_profile_summary(self, profile_id: str, *, version: int | None = None) -> RiskProfileSummary:
        profile = self.get_profile(profile_id, version=version)
        financial = profile.hard_rules.get("financial_objectives", {})
        risk = profile.hard_rules.get("risk_guardrails", {})
        constraints = profile.hard_rules.get("investment_constraints", {})
        interaction = profile.hard_rules.get("interaction_model", {})
        hard_constraints = []
        if constraints.get("constraints"):
            hard_constraints.append(str(constraints["constraints"]))
        hard_constraints.extend(profile.forbidden_symbols)
        return RiskProfileSummary(
            profile_id=profile.profile_id,
            owner_id=profile.owner_id,
            version=profile.version,
            display_name=profile.display_name,
            mandate_summary=profile.mandate_summary,
            risk_budget=profile.risk_budget,
            objective=financial.get("objective"),
            time_horizon=financial.get("time_horizon"),
            liquidity_needs=financial.get("liquidity_needs"),
            stress_response=risk.get("stress_response"),
            loss_threshold=risk.get("max_drawdown_signal"),
            concentration_guidance=constraints.get("concentration"),
            interaction_style=interaction.get("interaction_style"),
            review_cadence=interaction.get("review_cadence"),
            hard_constraints=hard_constraints,
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
            status=DiscoverySessionStatus.DRAFT_READY,
            dimension_states=self._seed_dimension_states(),
            answers=self._seed_answers_from_profile(profile, session_id=session_id, payload=payload),
        )
        session.updated_at = datetime.now(UTC)
        self._save_session(session, next_question=None)
        return session

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
            if state.dimension is DiscoveryDimension.BACKGROUND:
                state.coverage_score = 1
                state.confidence_score = 1
                state.depth_score = 1
            else:
                state.coverage_score = 3
                state.confidence_score = 3
                state.depth_score = 2
        return states

    def _seed_answers_from_profile(self, profile: PersonaProfile, *, session_id: str, payload: ReviewProfileRequest) -> list[DiscoveryAnswer]:
        answers = self._seed_review_answers_from_evidence(profile)
        if not answers:
            answers = self._seed_review_answers_from_structured_profile(profile)
        background_seed = self._seed_background_summary(profile, payload=payload)
        if background_seed:
            answers.append((DiscoveryDimension.BACKGROUND, background_seed))

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
        hard_rules = profile.hard_rules or {}
        financial = hard_rules.get("financial_objectives", {})
        risk = hard_rules.get("risk_guardrails", {})
        constraints = hard_rules.get("investment_constraints", {})
        interaction = hard_rules.get("interaction_model", {})
        return [
            (DiscoveryDimension.OBJECTIVE, financial.get("objective") or profile.mandate_summary),
            (DiscoveryDimension.LIQUIDITY, financial.get("liquidity_needs") or "No new liquidity changes noted."),
            (DiscoveryDimension.HORIZON, financial.get("time_horizon") or "Existing horizon unchanged."),
            (DiscoveryDimension.RISK_RESPONSE, risk.get("stress_response") or f"Current risk budget is {profile.risk_budget.value}."),
            (DiscoveryDimension.LOSS_THRESHOLD, risk.get("max_drawdown_signal") or "Existing loss threshold unchanged."),
            (DiscoveryDimension.CONSTRAINTS, constraints.get("constraints") or self._serialize_list(profile.forbidden_symbols) or "Existing constraints unchanged."),
            (DiscoveryDimension.CONCENTRATION, constraints.get("concentration") or "Existing concentration guidance unchanged."),
            (DiscoveryDimension.INTERACTION_STYLE, interaction.get("interaction_style") or "Keep existing interaction style."),
            (DiscoveryDimension.REVIEW_CADENCE, interaction.get("review_cadence") or "Keep existing review cadence."),
        ]

    def _seed_background_summary(self, profile: PersonaProfile, *, payload: ReviewProfileRequest) -> str:
        memories = profile.long_term_memories or []
        memory_text = ""
        if memories:
            summaries = [item.get("summary") for item in memories if item.get("summary")]
            memory_text = " ".join(summaries[:2])
        pieces = [piece for piece in [memory_text, payload.notes, f"Review trigger: {payload.trigger}."] if piece]
        return " ".join(pieces)

    def _serialize_list(self, items: list[str]) -> str:
        return ", ".join(items)

    def _build_draft(self, session: DiscoverySession, readiness: DraftReadinessAssessment) -> ProfileDraft:
        answer_map = {answer.dimension: answer.answer_text for answer in session.answers}
        preferred_name = session.preferred_profile_name or "Primary Risk Profile"
        profile_id = self._slugify_profile_id(preferred_name, session.owner_id)
        risk_budget = self._derive_risk_budget(answer_map)
        mandate_summary = self._build_mandate_summary(answer_map, risk_budget)
        forbidden_symbols = self._extract_forbidden_symbols(answer_map)
        hard_rules = self._build_hard_rules(answer_map, risk_budget)
        contextual_rules = self._build_contextual_rules(answer_map)
        long_term_memories = self._build_long_term_memories(answer_map)
        short_term_memories = self._build_short_term_memories(answer_map)
        persona_evidence = build_persona_evidence_from_answers([answer.model_dump(mode="json") for answer in session.answers])
        suggested_profile = PersonaProfile(
            profile_id=profile_id,
            owner_id=session.owner_id,
            version=1,
            status=ProfileLifecycleStatus.PENDING_USER_CONFIRMATION,
            display_name=preferred_name,
            mandate_summary=mandate_summary,
            persona_style=self._derive_persona_style(risk_budget, answer_map),
            created_from="guided_discovery",
            risk_budget=risk_budget,
            forbidden_symbols=forbidden_symbols,
            hard_rules=hard_rules,
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
            hard_rules=hard_rules,
            contextual_rules=contextual_rules,
            narrative_memories=long_term_memories,
        )

    def _build_hard_rules(self, answer_map: dict[DiscoveryDimension, str], risk_budget: RiskBudget) -> dict[str, Any]:
        return {
            "financial_objectives": {
                "objective": answer_map.get(DiscoveryDimension.OBJECTIVE),
                "time_horizon": answer_map.get(DiscoveryDimension.HORIZON),
                "liquidity_needs": answer_map.get(DiscoveryDimension.LIQUIDITY),
            },
            "risk_guardrails": {
                "risk_budget": risk_budget.value,
                "max_drawdown_signal": answer_map.get(DiscoveryDimension.LOSS_THRESHOLD),
                "stress_response": answer_map.get(DiscoveryDimension.RISK_RESPONSE),
            },
            "investment_constraints": {
                "constraints": answer_map.get(DiscoveryDimension.CONSTRAINTS),
                "concentration": answer_map.get(DiscoveryDimension.CONCENTRATION),
            },
            "interaction_model": {
                "interaction_style": answer_map.get(DiscoveryDimension.INTERACTION_STYLE),
                "review_cadence": answer_map.get(DiscoveryDimension.REVIEW_CADENCE),
            },
        }

    def _build_contextual_rules(self, answer_map: dict[DiscoveryDimension, str]) -> list[ContextualRuleCandidate]:
        rules: list[ContextualRuleCandidate] = []
        liquidity = answer_map.get(DiscoveryDimension.LIQUIDITY, "")
        risk = answer_map.get(DiscoveryDimension.RISK_RESPONSE, "")
        concentration = answer_map.get(DiscoveryDimension.CONCENTRATION, "")
        if liquidity and re.search(r"\b(cash|need|expense|reserve|money)\b", liquidity, re.IGNORECASE):
            rules.append(
                ContextualRuleCandidate(
                    rule_text="Prefer preserving liquid reserve before adding new high-volatility exposure when near-term cash needs exist.",
                    reason="Derived from stated liquidity needs.",
                )
            )
        if risk and re.search(r"\b(add|hold|reduce|sell)\b", risk, re.IGNORECASE):
            rules.append(
                ContextualRuleCandidate(
                    rule_text="During drawdowns, interpret user stress response before recommending more risk.",
                    reason="Derived from stated stress behavior.",
                )
            )
        if concentration:
            rules.append(
                ContextualRuleCandidate(
                    rule_text="Keep concentration guidance visible when a single position or theme grows quickly.",
                    reason="Derived from concentration preferences.",
                )
            )
        return rules

    def _build_long_term_memories(self, answer_map: dict[DiscoveryDimension, str]) -> list[NarrativeMemoryCandidate]:
        items: list[NarrativeMemoryCandidate] = []
        for dimension, theme in (
            (DiscoveryDimension.BACKGROUND, "background_context"),
            (DiscoveryDimension.RISK_RESPONSE, "risk_behavior"),
            (DiscoveryDimension.INTERACTION_STYLE, "interaction_preference"),
        ):
            text = answer_map.get(dimension)
            if text and len(text.split()) >= 8:
                items.append(NarrativeMemoryCandidate(summary=text, theme=theme, source_dimension=dimension))
        return items

    def _build_short_term_memories(self, answer_map: dict[DiscoveryDimension, str]) -> list[dict[str, str]]:
        items: list[dict[str, str]] = []
        liquidity = answer_map.get(DiscoveryDimension.LIQUIDITY)
        if liquidity and re.search(r"\b(within|month|months|week|weeks|soon|upcoming|next)\b", liquidity, re.IGNORECASE):
            items.append({"theme": "near_term_liquidity", "summary": liquidity, "source_dimension": DiscoveryDimension.LIQUIDITY.value})
        background = answer_map.get(DiscoveryDimension.BACKGROUND)
        if background and re.search(r"\b(review trigger|this quarter|this month|recent|currently|right now)\b", background, re.IGNORECASE):
            items.append({"theme": "current_context", "summary": background, "source_dimension": DiscoveryDimension.BACKGROUND.value})
        return items

    def _derive_risk_budget(self, answer_map: dict[DiscoveryDimension, str]) -> RiskBudget:
        risk_response = (answer_map.get(DiscoveryDimension.RISK_RESPONSE) or "").lower()
        loss_threshold = (answer_map.get(DiscoveryDimension.LOSS_THRESHOLD) or "").lower()
        if re.search(r"\b(add|upside|aggressive|growth)\b", risk_response) and not re.search(r"\bscared|panic|sleep|uneasy\b", risk_response):
            return RiskBudget.HIGH
        if re.search(r"\b(5|6|7|8)\b", loss_threshold) or re.search(r"\b(conservative|reduce|sell|panic|sleep)\b", risk_response):
            return RiskBudget.LOW
        return RiskBudget.MEDIUM

    def _derive_persona_style(self, risk_budget: RiskBudget, answer_map: dict[DiscoveryDimension, str]) -> str:
        objective = (answer_map.get(DiscoveryDimension.OBJECTIVE) or "").lower()
        if "income" in objective:
            return "income oriented"
        return {
            RiskBudget.LOW: "capital preservation",
            RiskBudget.MEDIUM: "balanced",
            RiskBudget.HIGH: "growth oriented",
        }[risk_budget]

    def _build_mandate_summary(self, answer_map: dict[DiscoveryDimension, str], risk_budget: RiskBudget) -> str:
        objective = answer_map.get(DiscoveryDimension.OBJECTIVE) or "Manage the portfolio under a clear user-defined mandate."
        horizon = answer_map.get(DiscoveryDimension.HORIZON) or "unspecified horizon"
        liquidity = answer_map.get(DiscoveryDimension.LIQUIDITY) or "no explicit liquidity note"
        return f"{objective} Operate with {risk_budget.value} risk budget, horizon {horizon}, and liquidity context: {liquidity}."

    def _extract_forbidden_symbols(self, answer_map: dict[DiscoveryDimension, str]) -> list[str]:
        constraints = answer_map.get(DiscoveryDimension.CONSTRAINTS, "")
        if not constraints:
            return []
        if not re.search(r"\b(avoid|don't|do not|won't|hate)\b", constraints, re.IGNORECASE):
            return []
        return sorted({token.upper() for token in re.findall(r"\b[A-Z]{1,5}\b", constraints)})

    def _slugify_profile_id(self, preferred_name: str, owner_id: str) -> str:
        base = re.sub(r"[^a-z0-9]+", "-", preferred_name.lower()).strip("-") or "profile"
        owner = re.sub(r"[^a-z0-9]+", "-", owner_id.lower()).strip("-") or "owner"
        return f"{owner}-{base}"

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

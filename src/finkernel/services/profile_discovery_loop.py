from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol

from finkernel.schemas.discovery import (
    DiscoveryInterpretationPacket,
    DiscoveryPillar,
    DiscoverySessionStatus,
    ProfileDiscoveryState,
    ProfileDraft,
)
from finkernel.services.profile_discovery import ProfileDiscoveryService


class DiscoveryQuestionGenerator(Protocol):
    def generate_question(self, state: ProfileDiscoveryState) -> str:
        """Return one dynamic follow-up question for the current discovery state."""


class DiscoveryAnswerProvider(Protocol):
    def collect_answer(self, state: ProfileDiscoveryState, question_text: str) -> str:
        """Return the user's answer to the current question."""


class DiscoveryAnswerExtractor(Protocol):
    def extract_packet(
        self,
        state: ProfileDiscoveryState,
        question_text: str,
        answer_text: str,
    ) -> DiscoveryInterpretationPacket:
        """Convert one user answer into a strict interpretation packet."""


class ProfileDiscoveryLoopError(RuntimeError):
    pass


@dataclass(frozen=True)
class ProfileDiscoveryLoopTurn:
    section: DiscoveryPillar
    question_text: str
    answer_text: str
    used_starter_question: bool
    status_after_turn: DiscoverySessionStatus


@dataclass(frozen=True)
class ProfileDiscoveryLoopResult:
    final_state: ProfileDiscoveryState
    turns: list[ProfileDiscoveryLoopTurn] = field(default_factory=list)
    draft: ProfileDraft | None = None


class ReferenceProfileDiscoveryLoop:
    """Reference host-side orchestration for adaptive profile discovery.

    The loop intentionally delegates semantic work to injected collaborators.
    FinKernel remains responsible for deterministic validation, persistence,
    coverage updates, and draft readiness.
    """

    def __init__(
        self,
        *,
        discovery_service: ProfileDiscoveryService,
        question_generator: DiscoveryQuestionGenerator,
        answer_provider: DiscoveryAnswerProvider,
        answer_extractor: DiscoveryAnswerExtractor,
        max_turns: int = 32,
    ) -> None:
        self.discovery_service = discovery_service
        self.question_generator = question_generator
        self.answer_provider = answer_provider
        self.answer_extractor = answer_extractor
        self.max_turns = max_turns

    def run(self, *, discovery_session_id: str, generate_draft: bool = False) -> ProfileDiscoveryLoopResult:
        turns: list[ProfileDiscoveryLoopTurn] = []
        state = self.discovery_service.get_discovery_state(discovery_session_id)

        while state.status is DiscoverySessionStatus.DISCOVERY_IN_PROGRESS:
            if len(turns) >= self.max_turns:
                raise ProfileDiscoveryLoopError(
                    f"Discovery session {discovery_session_id} exceeded {self.max_turns} turns."
                )
            if state.current_section is None:
                raise ProfileDiscoveryLoopError(
                    f"Discovery session {discovery_session_id} is in progress without a current section."
                )

            used_starter_question = state.starter_question is not None
            question_text = (
                state.starter_question.prompt_text
                if state.starter_question is not None
                else self.question_generator.generate_question(state)
            )
            answer_text = self.answer_provider.collect_answer(state, question_text)
            packet = self.answer_extractor.extract_packet(state, question_text, answer_text)
            if packet.question_text is None:
                packet = packet.model_copy(update={"question_text": question_text})
            if packet.answer_text != answer_text:
                packet = packet.model_copy(update={"answer_text": answer_text})

            state = self.discovery_service.submit_interpretation(
                session_id=discovery_session_id,
                packet=packet,
            )
            turns.append(
                ProfileDiscoveryLoopTurn(
                    section=packet.section,
                    question_text=question_text,
                    answer_text=answer_text,
                    used_starter_question=used_starter_question,
                    status_after_turn=state.status,
                )
            )

        draft = None
        if generate_draft and state.status is DiscoverySessionStatus.DRAFT_READY:
            draft = self.discovery_service.generate_draft(discovery_session_id)

        return ProfileDiscoveryLoopResult(final_state=state, turns=turns, draft=draft)

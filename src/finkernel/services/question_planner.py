from __future__ import annotations

import re
from typing import Iterable
from uuid import uuid4

from finkernel.schemas.discovery import (
    DimensionState,
    DiscoveryAnswer,
    DiscoveryDimension,
    DiscoveryPillar,
    DiscoveryQuestion,
    DiscoveryQuestionSource,
    DiscoveryQuestionType,
    DiscoverySession,
    DraftReadinessAssessment,
    ExpectedAnswerShape,
)


DIMENSION_TO_PILLAR: dict[DiscoveryDimension, DiscoveryPillar] = {
    DiscoveryDimension.OBJECTIVE: DiscoveryPillar.FINANCIAL_OBJECTIVES,
    DiscoveryDimension.LIQUIDITY: DiscoveryPillar.FINANCIAL_OBJECTIVES,
    DiscoveryDimension.HORIZON: DiscoveryPillar.FINANCIAL_OBJECTIVES,
    DiscoveryDimension.RISK_RESPONSE: DiscoveryPillar.RISK,
    DiscoveryDimension.LOSS_THRESHOLD: DiscoveryPillar.RISK,
    DiscoveryDimension.CONSTRAINTS: DiscoveryPillar.CONSTRAINTS,
    DiscoveryDimension.CONCENTRATION: DiscoveryPillar.CONSTRAINTS,
    DiscoveryDimension.BACKGROUND: DiscoveryPillar.BACKGROUND,
    DiscoveryDimension.INTERACTION_STYLE: DiscoveryPillar.BACKGROUND,
    DiscoveryDimension.REVIEW_CADENCE: DiscoveryPillar.BACKGROUND,
}

MANDATORY_DIMENSIONS: list[DiscoveryDimension] = [
    DiscoveryDimension.OBJECTIVE,
    DiscoveryDimension.LIQUIDITY,
    DiscoveryDimension.HORIZON,
    DiscoveryDimension.RISK_RESPONSE,
    DiscoveryDimension.LOSS_THRESHOLD,
    DiscoveryDimension.CONSTRAINTS,
    DiscoveryDimension.CONCENTRATION,
    DiscoveryDimension.INTERACTION_STYLE,
    DiscoveryDimension.REVIEW_CADENCE,
]

HIGH_RISK_DIMENSIONS = {
    DiscoveryDimension.LIQUIDITY,
    DiscoveryDimension.RISK_RESPONSE,
    DiscoveryDimension.LOSS_THRESHOLD,
}

STARTER_BANK: dict[DiscoveryDimension, tuple[str, str, ExpectedAnswerShape]] = {
    DiscoveryDimension.OBJECTIVE: (
        "What is this portfolio mainly for over the next few years: growth, capital preservation, income, or a specific future use?",
        "I need the portfolio's core purpose before I can shape the mandate safely.",
        ExpectedAnswerShape.OPEN_TEXT,
    ),
    DiscoveryDimension.LIQUIDITY: (
        "Do you expect to need a meaningful amount of cash from this portfolio within the next 12 months?",
        "Near-term cash needs heavily affect how much risk or illiquidity is acceptable.",
        ExpectedAnswerShape.OPEN_TEXT,
    ),
    DiscoveryDimension.HORIZON: (
        "Roughly how long should this capital be managed with this mandate before major goals change?",
        "Time horizon changes how much short-term volatility and rebalancing pressure make sense.",
        ExpectedAnswerShape.OPEN_TEXT,
    ),
    DiscoveryDimension.RISK_RESPONSE: (
        "If this portfolio fell 15% in a short period, would you be more likely to add, hold, or reduce risk?",
        "Your reaction under stress says more than a generic risk label.",
        ExpectedAnswerShape.CHOICE,
    ),
    DiscoveryDimension.LOSS_THRESHOLD: (
        "What level of decline would start to feel unacceptable to you personally?",
        "I need a concrete loss threshold or drawdown line to turn preference into enforceable guardrails.",
        ExpectedAnswerShape.OPEN_TEXT,
    ),
    DiscoveryDimension.CONSTRAINTS: (
        "Are there any industries, companies, instruments, or markets you explicitly do not want exposure to?",
        "Hard restrictions and exclusions need to be captured explicitly so the system can enforce them.",
        ExpectedAnswerShape.OPEN_TEXT,
    ),
    DiscoveryDimension.CONCENTRATION: (
        "Would you want limits on how concentrated any single position or theme can become?",
        "Concentration limits are one of the most important portfolio guardrails.",
        ExpectedAnswerShape.OPEN_TEXT,
    ),
    DiscoveryDimension.BACKGROUND: (
        "Is there any background about how this capital was earned or what it is meant to support that should shape how cautiously it is managed?",
        "Context like job exposure, family obligations, or prior losses often changes the right risk framing.",
        ExpectedAnswerShape.OPEN_TEXT,
    ),
    DiscoveryDimension.INTERACTION_STYLE: (
        "How involved do you want the system to be: mostly factual and concise, or more proactive in surfacing trade-offs and reminders?",
        "The profile should capture how you prefer the system to communicate and intervene.",
        ExpectedAnswerShape.OPEN_TEXT,
    ),
    DiscoveryDimension.REVIEW_CADENCE: (
        "How often should we explicitly revisit your profile assumptions: only when you ask, on a schedule, or after major market moves?",
        "Review cadence is part of the mandate, not just a UI preference.",
        ExpectedAnswerShape.OPEN_TEXT,
    ),
}

AMBIGUITY_RE = re.compile(r"\b(maybe|depends|not sure|it varies|kind of|probably|possibly)\b", re.IGNORECASE)
NUMBER_RE = re.compile(r"(\d+(?:\.\d+)?)")
MONEY_RE = re.compile(r"(\$?\d+(?:\.\d+)?\s*[kKmM]?)")
RISK_AVERSION_RE = re.compile(r"\b(afraid|anxious|panic|scared|uneasy|volatile|burned|sleep)\b", re.IGNORECASE)
RISK_SEEKING_RE = re.compile(r"\b(aggressive|upside|volatility|swings|high growth|growth)\b", re.IGNORECASE)
LIQUIDITY_RE = re.compile(r"\b(cash|expense|buy a house|home|tuition|startup|reserve|emergency|need money)\b", re.IGNORECASE)
VALUES_RE = re.compile(r"\b(avoid|don't invest|do not invest|unethical|hate|won't invest|ceo)\b", re.IGNORECASE)
CONCENTRATION_RE = re.compile(r"\b(cap|limit|concentrat|too much|single position|theme)\b", re.IGNORECASE)
REVIEW_RE = re.compile(r"\b(monthly|quarterly|schedule|market moves|check in)\b", re.IGNORECASE)


def build_empty_dimension_states() -> list[DimensionState]:
    return [DimensionState(dimension=dimension) for dimension in DiscoveryDimension]


class QuestionPlanner:
    def build_readiness(self, session: DiscoverySession) -> DraftReadinessAssessment:
        states = {state.dimension: state for state in session.dimension_states}
        unmet: list[DiscoveryDimension] = []
        notes: list[str] = []
        for dimension in MANDATORY_DIMENSIONS:
            state = states[dimension]
            if state.coverage_score < 2:
                unmet.append(dimension)
            elif dimension in HIGH_RISK_DIMENSIONS and state.confidence_score < 2:
                unmet.append(dimension)
        if states[DiscoveryDimension.LOSS_THRESHOLD].depth_score < 1:
            unmet.append(DiscoveryDimension.LOSS_THRESHOLD)
            notes.append("A concrete or surrogate loss threshold is still missing.")
        if states[DiscoveryDimension.CONCENTRATION].coverage_score < 2:
            notes.append("Concentration stance is not yet explicit enough.")
        return DraftReadinessAssessment(ready=not unmet, unmet_dimensions=list(dict.fromkeys(unmet)), notes=notes)

    def choose_next_question(self, session: DiscoverySession) -> DiscoveryQuestion | None:
        states = {state.dimension: state for state in session.dimension_states}
        if readiness := self.build_readiness(session):
            if readiness.ready:
                return None

        for state in session.dimension_states:
            if state.conflict_flag:
                return self._make_question(
                    session,
                    dimension=state.dimension,
                    question_type=DiscoveryQuestionType.CONFLICT_RESOLUTION,
                    source_type=DiscoveryQuestionSource.RULE_TRIGGER,
                    prompt_text=f"I have two signals for {state.dimension.value} that don't fully fit together yet. Which one should take priority?",
                    why="I need to resolve this conflict before safely generating a draft mandate.",
                    answer_shape=ExpectedAnswerShape.OPEN_TEXT,
                    priority=100,
                )

        drift_candidate = self._find_coverage_gap_recovery_dimension(session)
        if drift_candidate is not None:
            return self._make_question(
                session,
                dimension=drift_candidate,
                question_type=DiscoveryQuestionType.COVERAGE_RECOVERY,
                source_type=DiscoveryQuestionSource.COVERAGE_GAP,
                prompt_text=STARTER_BANK[drift_candidate][0],
                why="I still need to cover this part of your profile before I can generate a usable draft.",
                answer_shape=STARTER_BANK[drift_candidate][2],
                priority=90,
            )

        for dimension in MANDATORY_DIMENSIONS:
            state = states[dimension]
            if state.coverage_score == 0:
                starter_prompt, starter_why, answer_shape = STARTER_BANK[dimension]
                return self._make_question(
                    session,
                    dimension=dimension,
                    question_type=DiscoveryQuestionType.STARTER,
                    source_type=DiscoveryQuestionSource.STARTER_BANK,
                    prompt_text=starter_prompt,
                    why=starter_why,
                    answer_shape=answer_shape,
                    priority=80,
                )
            if state.coverage_score < 2 or (dimension in HIGH_RISK_DIMENSIONS and state.confidence_score < 2):
                follow_up = self._build_follow_up(session, dimension)
                if follow_up is not None:
                    return follow_up

        for dimension in (DiscoveryDimension.BACKGROUND,):
            state = states[dimension]
            if state.coverage_score == 0:
                starter_prompt, starter_why, answer_shape = STARTER_BANK[dimension]
                return self._make_question(
                    session,
                    dimension=dimension,
                    question_type=DiscoveryQuestionType.STARTER,
                    source_type=DiscoveryQuestionSource.STARTER_BANK,
                    prompt_text=starter_prompt,
                    why=starter_why,
                    answer_shape=answer_shape,
                    priority=40,
                )
        return None

    def update_dimension_state(self, session: DiscoverySession, answer: DiscoveryAnswer) -> None:
        state = self._get_state(session, answer.dimension)
        text = answer.answer_text.strip()
        lowered = text.lower()
        state.last_question_id = answer.question_id
        state.last_updated_at = answer.answered_at
        state.extracted_facts.append(text)
        state.pending_gaps = []

        ambiguous = bool(AMBIGUITY_RE.search(text))
        has_number = bool(NUMBER_RE.search(text))
        has_money = bool(MONEY_RE.search(text))
        long_form = len(text.split()) >= 12
        risk_averse = bool(RISK_AVERSION_RE.search(text))
        risk_seeking = bool(RISK_SEEKING_RE.search(text))

        state.coverage_score = max(state.coverage_score, 1 if ambiguous and not has_number else 2)
        state.confidence_score = max(state.confidence_score, 1 if ambiguous else 2)
        state.depth_score = max(state.depth_score, 2 if has_number or has_money or long_form else 1)

        if answer.dimension in HIGH_RISK_DIMENSIONS and ambiguous:
            state.pending_gaps.append("Needs quantification.")
            state.confidence_score = min(state.confidence_score, 1)
        if answer.dimension is DiscoveryDimension.CONSTRAINTS and not text:
            state.pending_gaps.append("Need explicit hard/soft restriction stance.")
        if answer.dimension is DiscoveryDimension.RISK_RESPONSE and risk_averse and risk_seeking:
            state.conflict_flag = True
        elif answer.dimension is DiscoveryDimension.LOSS_THRESHOLD and risk_seeking and has_number:
            threshold_value = self._extract_float(lowered)
            state.conflict_flag = bool(threshold_value is not None and threshold_value <= 8)
        else:
            state.conflict_flag = False

        if answer.dimension is DiscoveryDimension.LIQUIDITY and LIQUIDITY_RE.search(text):
            state.depth_score = max(state.depth_score, 2)
            if not has_number:
                state.pending_gaps.append("Need amount or timing.")
        if answer.dimension is DiscoveryDimension.CONSTRAINTS and VALUES_RE.search(text):
            if "hard" not in lowered and "strict" not in lowered:
                state.pending_gaps.append("Need to classify whether this is hard prohibition or soft preference.")
        if answer.dimension is DiscoveryDimension.CONCENTRATION and CONCENTRATION_RE.search(text):
            state.depth_score = max(state.depth_score, 2)
        if answer.dimension is DiscoveryDimension.REVIEW_CADENCE and REVIEW_RE.search(text):
            state.depth_score = max(state.depth_score, 2)

        answer.extracted_signals.extend(signal for signal in self._derive_signals(text) if signal not in answer.extracted_signals)

    def _build_follow_up(self, session: DiscoverySession, dimension: DiscoveryDimension) -> DiscoveryQuestion | None:
        answers = self._answers_for_dimension(session.answers, dimension)
        latest = answers[-1] if answers else None
        if latest is None:
            return None
        text = latest.answer_text
        lowered = text.lower()

        if dimension is DiscoveryDimension.LIQUIDITY and (LIQUIDITY_RE.search(text) or AMBIGUITY_RE.search(text)):
            return self._make_question(
                session,
                dimension=dimension,
                question_type=DiscoveryQuestionType.DEEPENING,
                source_type=DiscoveryQuestionSource.RULE_TRIGGER,
                prompt_text="What amount and rough timing should I assume for that cash need, and would it be a problem if markets were down when you needed it?",
                why="I need both timing and loss sensitivity before I can set liquidity guardrails.",
                answer_shape=ExpectedAnswerShape.OPEN_TEXT,
                priority=70,
                generated_from_answer_id=latest.answer_id,
            )

        if dimension is DiscoveryDimension.HORIZON and ("long term" in lowered or AMBIGUITY_RE.search(text)):
            return self._make_question(
                session,
                dimension=dimension,
                question_type=DiscoveryQuestionType.CLARIFICATION,
                source_type=DiscoveryQuestionSource.RULE_TRIGGER,
                prompt_text="When you say long term, should I think in terms of 3 years, 5 years, or 10+ years?",
                why="Time horizon needs a usable range, not just a broad label.",
                answer_shape=ExpectedAnswerShape.CHOICE,
                priority=65,
                generated_from_answer_id=latest.answer_id,
            )

        if dimension is DiscoveryDimension.RISK_RESPONSE and (AMBIGUITY_RE.search(text) or "depends" in lowered):
            return self._make_question(
                session,
                dimension=dimension,
                question_type=DiscoveryQuestionType.DEEPENING,
                source_type=DiscoveryQuestionSource.RULE_TRIGGER,
                prompt_text="What makes the difference for you in a selloff: whether the thesis changed, whether the move feels emotional, or simply how deep the drawdown is?",
                why="I need to know how you separate temporary volatility from a real break in conviction.",
                answer_shape=ExpectedAnswerShape.OPEN_TEXT,
                priority=75,
                generated_from_answer_id=latest.answer_id,
            )

        if dimension is DiscoveryDimension.LOSS_THRESHOLD and (AMBIGUITY_RE.search(text) or not NUMBER_RE.search(text)):
            return self._make_question(
                session,
                dimension=dimension,
                question_type=DiscoveryQuestionType.CLARIFICATION,
                source_type=DiscoveryQuestionSource.RULE_TRIGGER,
                prompt_text="Even a rough range is useful here: is your unacceptable loss line closer to 5%, 10%, 15%, or something else?",
                why="A concrete or at least bounded loss threshold is needed for enforceable guardrails.",
                answer_shape=ExpectedAnswerShape.CHOICE,
                priority=75,
                generated_from_answer_id=latest.answer_id,
            )

        if dimension is DiscoveryDimension.CONSTRAINTS and VALUES_RE.search(text):
            return self._make_question(
                session,
                dimension=dimension,
                question_type=DiscoveryQuestionType.CLARIFICATION,
                source_type=DiscoveryQuestionSource.RULE_TRIGGER,
                prompt_text="Should I treat that as a strict prohibition, a capped exposure, or more of a preference that can be overridden if you explicitly approve it?",
                why="I need to know whether the restriction is enforceable or advisory.",
                answer_shape=ExpectedAnswerShape.CHOICE,
                priority=60,
                generated_from_answer_id=latest.answer_id,
            )

        if dimension is DiscoveryDimension.CONCENTRATION and not NUMBER_RE.search(text):
            return self._make_question(
                session,
                dimension=dimension,
                question_type=DiscoveryQuestionType.DEEPENING,
                source_type=DiscoveryQuestionSource.RULE_TRIGGER,
                prompt_text="Should any single name or theme have a rough cap, even if it's just a comfort-zone range like 10%, 15%, or 20%?",
                why="Concentration needs to become operational, not stay qualitative.",
                answer_shape=ExpectedAnswerShape.OPEN_TEXT,
                priority=55,
                generated_from_answer_id=latest.answer_id,
            )

        if dimension is DiscoveryDimension.BACKGROUND and (RISK_AVERSION_RE.search(text) or long_narrative(text)):
            return self._make_question(
                session,
                dimension=dimension,
                question_type=DiscoveryQuestionType.DEEPENING,
                source_type=DiscoveryQuestionSource.MODEL_GENERATED,
                prompt_text="What part of that experience would you most want the system to remember and actively protect against in the future?",
                why="That background can become valuable narrative memory and may imply future review triggers.",
                answer_shape=ExpectedAnswerShape.OPEN_TEXT,
                priority=45,
                generated_from_answer_id=latest.answer_id,
            )

        return self._make_question(
            session,
            dimension=dimension,
            question_type=DiscoveryQuestionType.CLARIFICATION,
            source_type=DiscoveryQuestionSource.RULE_TRIGGER,
            prompt_text=f"I have a first signal for {dimension.value}, but I need one more concrete detail to make it actionable. Can you be a bit more specific?",
            why="The current answer is still too vague to use safely.",
            answer_shape=ExpectedAnswerShape.OPEN_TEXT,
            priority=50,
            generated_from_answer_id=latest.answer_id,
        )

    def _find_coverage_gap_recovery_dimension(self, session: DiscoverySession) -> DiscoveryDimension | None:
        unanswered = [state.dimension for state in session.dimension_states if state.dimension in MANDATORY_DIMENSIONS and state.coverage_score == 0]
        if not unanswered or len(session.answers) < 2:
            return None
        recent_dimensions = [answer.dimension for answer in session.answers[-2:]]
        if len(set(recent_dimensions)) == 1 and recent_dimensions[0] not in unanswered:
            return unanswered[0]
        return None

    def _get_state(self, session: DiscoverySession, dimension: DiscoveryDimension) -> DimensionState:
        for state in session.dimension_states:
            if state.dimension is dimension:
                return state
        raise KeyError(f"Missing dimension state for {dimension.value}")

    def _answers_for_dimension(self, answers: Iterable[DiscoveryAnswer], dimension: DiscoveryDimension) -> list[DiscoveryAnswer]:
        return [answer for answer in answers if answer.dimension is dimension]

    def _make_question(
        self,
        session: DiscoverySession,
        *,
        dimension: DiscoveryDimension,
        question_type: DiscoveryQuestionType,
        source_type: DiscoveryQuestionSource,
        prompt_text: str,
        why: str,
        answer_shape: ExpectedAnswerShape,
        priority: int,
        generated_from_answer_id: str | None = None,
    ) -> DiscoveryQuestion:
        return DiscoveryQuestion(
            question_id=str(uuid4()),
            session_id=session.session_id,
            dimension=dimension,
            pillar=DIMENSION_TO_PILLAR[dimension],
            question_type=question_type,
            source_type=source_type,
            prompt_text=prompt_text,
            why_this_matters=why,
            expected_answer_shape=answer_shape,
            priority_score=priority,
            generated_from_answer_id=generated_from_answer_id,
            stop_condition_target=dimension.value,
        )

    def _derive_signals(self, text: str) -> list[str]:
        lowered = text.lower()
        signals: list[str] = []
        if AMBIGUITY_RE.search(text):
            signals.append("ambiguity")
        if LIQUIDITY_RE.search(text):
            signals.append("liquidity")
        if RISK_AVERSION_RE.search(text):
            signals.append("risk_aversion")
        if RISK_SEEKING_RE.search(text):
            signals.append("risk_seeking")
        if VALUES_RE.search(text):
            signals.append("values_or_exclusion")
        if CONCENTRATION_RE.search(text):
            signals.append("concentration")
        if REVIEW_RE.search(text):
            signals.append("review_preference")
        if "tech" in lowered:
            signals.append("tech_exposure")
        return signals

    def _extract_float(self, lowered: str) -> float | None:
        match = NUMBER_RE.search(lowered)
        if match is None:
            return None
        try:
            return float(match.group(1))
        except ValueError:
            return None


def long_narrative(text: str) -> bool:
    return len(text.split()) >= 14

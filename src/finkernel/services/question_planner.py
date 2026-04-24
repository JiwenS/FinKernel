from __future__ import annotations

import re
from typing import Any, Iterable
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
    DiscoveryDimension.TARGET_ANNUAL_RETURN: DiscoveryPillar.FINANCIAL_OBJECTIVES,
    DiscoveryDimension.INVESTMENT_HORIZON: DiscoveryPillar.FINANCIAL_OBJECTIVES,
    DiscoveryDimension.ANNUAL_LIQUIDITY_NEED: DiscoveryPillar.FINANCIAL_OBJECTIVES,
    DiscoveryDimension.LIQUIDITY_FREQUENCY: DiscoveryPillar.FINANCIAL_OBJECTIVES,
    DiscoveryDimension.MAX_DRAWDOWN_LIMIT: DiscoveryPillar.RISK,
    DiscoveryDimension.MAX_ANNUAL_VOLATILITY: DiscoveryPillar.RISK,
    DiscoveryDimension.MAX_LEVERAGE_RATIO: DiscoveryPillar.RISK,
    DiscoveryDimension.SINGLE_ASSET_CAP: DiscoveryPillar.RISK,
    DiscoveryDimension.BLOCKED_SECTORS: DiscoveryPillar.CONSTRAINTS,
    DiscoveryDimension.BLOCKED_TICKERS: DiscoveryPillar.CONSTRAINTS,
    DiscoveryDimension.BASE_CURRENCY: DiscoveryPillar.CONSTRAINTS,
    DiscoveryDimension.TAX_RESIDENCY: DiscoveryPillar.CONSTRAINTS,
    DiscoveryDimension.ACCOUNT_ENTITY_TYPE: DiscoveryPillar.BACKGROUND,
    DiscoveryDimension.AUM_ALLOCATED: DiscoveryPillar.BACKGROUND,
    DiscoveryDimension.EXECUTION_MODE: DiscoveryPillar.BACKGROUND,
    DiscoveryDimension.FINANCIAL_LITERACY: DiscoveryPillar.BACKGROUND,
    DiscoveryDimension.WEALTH_ORIGIN_DNA: DiscoveryPillar.BACKGROUND,
    DiscoveryDimension.BEHAVIORAL_RISK_PROFILE: DiscoveryPillar.BACKGROUND,
}

PILLAR_DIMENSIONS: dict[DiscoveryPillar, list[DiscoveryDimension]] = {
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

MANDATORY_DIMENSIONS: list[DiscoveryDimension] = [
    dimension for pillar in DiscoveryPillar for dimension in PILLAR_DIMENSIONS[pillar]
]

NUMERIC_DIMENSIONS = {
    DiscoveryDimension.TARGET_ANNUAL_RETURN,
    DiscoveryDimension.INVESTMENT_HORIZON,
    DiscoveryDimension.ANNUAL_LIQUIDITY_NEED,
    DiscoveryDimension.MAX_DRAWDOWN_LIMIT,
    DiscoveryDimension.MAX_ANNUAL_VOLATILITY,
    DiscoveryDimension.MAX_LEVERAGE_RATIO,
    DiscoveryDimension.SINGLE_ASSET_CAP,
    DiscoveryDimension.AUM_ALLOCATED,
}

ENUM_DIMENSIONS = {
    DiscoveryDimension.LIQUIDITY_FREQUENCY,
    DiscoveryDimension.ACCOUNT_ENTITY_TYPE,
    DiscoveryDimension.EXECUTION_MODE,
}

LIST_DIMENSIONS = {
    DiscoveryDimension.BLOCKED_SECTORS,
    DiscoveryDimension.BLOCKED_TICKERS,
}

TRAIT_DIMENSIONS = {
    DiscoveryDimension.FINANCIAL_LITERACY,
    DiscoveryDimension.WEALTH_ORIGIN_DNA,
    DiscoveryDimension.BEHAVIORAL_RISK_PROFILE,
}

STARTER_BANK: dict[DiscoveryDimension, tuple[str, str, ExpectedAnswerShape]] = {
    DiscoveryDimension.TARGET_ANNUAL_RETURN: (
        "What annual return target should the system optimize toward for this capital, in percentage terms?",
        "This sets the core objective function for the account instead of leaving return expectations implicit.",
        ExpectedAnswerShape.NUMBER,
    ),
    DiscoveryDimension.INVESTMENT_HORIZON: (
        "How many years should this capital stay under the current mandate before its core purpose changes?",
        "Investment horizon is a hard constraint for asset matching and portfolio time scale.",
        ExpectedAnswerShape.NUMBER,
    ),
    DiscoveryDimension.ANNUAL_LIQUIDITY_NEED: (
        "How much cash does this portfolio need to deliver over a typical year, in absolute money terms?",
        "The system needs an explicit liquidity number rather than a vague sense of flexibility.",
        ExpectedAnswerShape.MONEY_RANGE,
    ),
    DiscoveryDimension.LIQUIDITY_FREQUENCY: (
        "How often should that liquidity be provided: monthly, quarterly, annually, or not on a recurring schedule?",
        "Cash-flow cadence affects income targeting, reserve sizing, and rebalancing pressure.",
        ExpectedAnswerShape.CHOICE,
    ),
    DiscoveryDimension.MAX_DRAWDOWN_LIMIT: (
        "What maximum peak-to-trough drawdown percentage should be treated as the portfolio's hard risk limit?",
        "This becomes a hard risk boundary for future de-risking or trading controls.",
        ExpectedAnswerShape.NUMBER,
    ),
    DiscoveryDimension.MAX_ANNUAL_VOLATILITY: (
        "What annualized volatility ceiling should the system stay under, in percentage terms?",
        "Volatility is one of the cleanest mathematical risk constraints for portfolio construction.",
        ExpectedAnswerShape.NUMBER,
    ),
    DiscoveryDimension.MAX_LEVERAGE_RATIO: (
        "What is the maximum leverage ratio this account is ever allowed to use? Use 0 if leverage is forbidden.",
        "Leverage permission must be explicit because it materially changes the system's risk envelope.",
        ExpectedAnswerShape.NUMBER,
    ),
    DiscoveryDimension.SINGLE_ASSET_CAP: (
        "What is the maximum percentage that any single asset is allowed to represent in the portfolio?",
        "This defines the single-name concentration ceiling used by the risk engine.",
        ExpectedAnswerShape.NUMBER,
    ),
    DiscoveryDimension.BLOCKED_SECTORS: (
        "Which sectors are absolutely blocked for this account? If none, say none.",
        "Blocked sectors belong in a filterable rule set, not in narrative prose alone.",
        ExpectedAnswerShape.LIST,
    ),
    DiscoveryDimension.BLOCKED_TICKERS: (
        "Which specific tickers are absolutely blocked for this account? If none, say none.",
        "Ticker-level exclusions need to be explicit so the execution layer can enforce them.",
        ExpectedAnswerShape.LIST,
    ),
    DiscoveryDimension.BASE_CURRENCY: (
        "What is the account's base currency for valuation and settlement?",
        "Base currency affects valuation, reporting, and downstream optimization assumptions.",
        ExpectedAnswerShape.CHOICE,
    ),
    DiscoveryDimension.TAX_RESIDENCY: (
        "Which tax residency or tax jurisdiction should the system assume for this account?",
        "Tax jurisdiction changes what later tax-aware logic is even allowed to consider.",
        ExpectedAnswerShape.OPEN_TEXT,
    ),
    DiscoveryDimension.ACCOUNT_ENTITY_TYPE: (
        "Is this account owned by an individual, a trust, or a corporate entity?",
        "Entity type affects compliance checks and what the system should assume about account structure.",
        ExpectedAnswerShape.CHOICE,
    ),
    DiscoveryDimension.AUM_ALLOCATED: (
        "How much capital, in absolute terms, is allocated to this FinKernel-managed mandate?",
        "The system needs the actual capital base to size risk and future execution boundaries correctly.",
        ExpectedAnswerShape.MONEY_RANGE,
    ),
    DiscoveryDimension.EXECUTION_MODE: (
        "Should the agent operate in advisory mode with human confirmation, or discretionary mode with delegated execution authority?",
        "Execution mode is a hard permission boundary for future trading automation.",
        ExpectedAnswerShape.CHOICE,
    ),
    DiscoveryDimension.FINANCIAL_LITERACY: (
        "How would you describe the user's financial literacy and product understanding in practical terms?",
        "This determines how detailed or simplified the agent's communication and explanations should be.",
        ExpectedAnswerShape.OPEN_TEXT,
    ),
    DiscoveryDimension.WEALTH_ORIGIN_DNA: (
        "What about the user's wealth origin or capital story should shape how the system interprets risk and opportunity?",
        "Wealth origin often changes what kinds of assets feel trustworthy or unacceptable to the user.",
        ExpectedAnswerShape.OPEN_TEXT,
    ),
    DiscoveryDimension.BEHAVIORAL_RISK_PROFILE: (
        "What behavioral risk pattern should the system remember about how this user reacts under market stress?",
        "Behavioral risk is a durable boundary for future autonomous monitoring and intervention.",
        ExpectedAnswerShape.OPEN_TEXT,
    ),
}

AMBIGUITY_RE = re.compile(r"\b(maybe|depends|not sure|it varies|kind of|probably|possibly|around-ish)\b", re.IGNORECASE)
NONE_RE = re.compile(r"\b(none|no restrictions|no blocked|nothing blocked|n/a|not applicable)\b", re.IGNORECASE)
NUMBER_RE = re.compile(r"(-?\d+(?:\.\d+)?)")
MONEY_RE = re.compile(r"(\$?\d+(?:\.\d+)?\s*[kKmMbB]?)")
YEARS_RE = re.compile(r"(\d+)(?:\s*[\+\-]?\s*)?(?:year|yr)", re.IGNORECASE)
CURRENCY_RE = re.compile(r"\b([A-Z]{3})\b")
TICKER_RE = re.compile(r"\b[A-Z]{1,5}\b")

SECTOR_MAP = {
    "tobacco": "Tobacco",
    "crypto": "Crypto",
    "gambling": "Gambling",
    "defense": "Defense",
    "weapon": "Weapons",
    "weapons": "Weapons",
    "oil": "OilAndGas",
    "gas": "OilAndGas",
    "energy": "Energy",
    "real estate": "RealEstate",
    "bank": "Banking",
    "banks": "Banking",
}

CURRENCY_KEYWORDS = {
    "usd": "USD",
    "dollar": "USD",
    "dollars": "USD",
    "hkd": "HKD",
    "hkdollar": "HKD",
    "cny": "CNY",
    "rmb": "CNY",
    "cnh": "CNH",
    "eur": "EUR",
    "euro": "EUR",
    "gbp": "GBP",
    "pound": "GBP",
    "jpy": "JPY",
    "yen": "JPY",
}

ACCOUNT_ENTITY_KEYWORDS = {
    "individual": "individual",
    "personal": "individual",
    "trust": "trust",
    "corporate": "corporate",
    "company": "corporate",
    "llc": "corporate",
}

EXECUTION_MODE_KEYWORDS = {
    "discretionary": "discretionary",
    "automatic": "discretionary",
    "auto": "discretionary",
    "advisory": "advisory",
    "manual": "advisory",
    "confirm": "advisory",
}

LIQUIDITY_FREQUENCY_KEYWORDS = {
    "monthly": "monthly",
    "month": "monthly",
    "quarterly": "quarterly",
    "quarter": "quarterly",
    "annual": "annual",
    "annually": "annual",
    "yearly": "annual",
    "none": "none",
}


def build_empty_dimension_states() -> list[DimensionState]:
    return [DimensionState(dimension=dimension) for dimension in DiscoveryDimension]


class QuestionPlanner:
    def build_readiness(self, session: DiscoverySession) -> DraftReadinessAssessment:
        states = {state.dimension: state for state in session.dimension_states}
        unmet: list[DiscoveryDimension] = []
        notes: list[str] = []

        for dimension in MANDATORY_DIMENSIONS:
            state = states[dimension]
            if state.coverage_score < 2 or state.confidence_score < 2:
                unmet.append(dimension)
            elif state.pending_gaps:
                unmet.append(dimension)
                notes.extend(state.pending_gaps)

        for pillar, dimensions in PILLAR_DIMENSIONS.items():
            missing = [dimension.value for dimension in dimensions if dimension in unmet]
            if missing:
                notes.append(f"{pillar.value} is still missing: {', '.join(missing)}.")

        return DraftReadinessAssessment(
            ready=not unmet,
            unmet_dimensions=list(dict.fromkeys(unmet)),
            notes=list(dict.fromkeys(notes)),
        )

    def choose_next_question(self, session: DiscoverySession) -> DiscoveryQuestion | None:
        states = {state.dimension: state for state in session.dimension_states}
        readiness = self.build_readiness(session)
        if readiness.ready:
            return None

        for state in session.dimension_states:
            if state.conflict_flag:
                return self._make_question(
                    session,
                    dimension=state.dimension,
                    question_type=DiscoveryQuestionType.CONFLICT_RESOLUTION,
                    source_type=DiscoveryQuestionSource.RULE_TRIGGER,
                    prompt_text=f"I have two conflicting signals for {state.dimension.value}. Which boundary should the system actually enforce?",
                    why="I need one unambiguous answer before this profile can be treated as operationally safe.",
                    answer_shape=ExpectedAnswerShape.OPEN_TEXT,
                    priority=100,
                )

        drift_candidate = self._find_coverage_gap_recovery_dimension(session)
        if drift_candidate is not None:
            starter_prompt, starter_why, answer_shape = STARTER_BANK[drift_candidate]
            return self._make_question(
                session,
                dimension=drift_candidate,
                question_type=DiscoveryQuestionType.COVERAGE_RECOVERY,
                source_type=DiscoveryQuestionSource.COVERAGE_GAP,
                prompt_text=starter_prompt,
                why=starter_why,
                answer_shape=answer_shape,
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
            if state.coverage_score < 2 or state.confidence_score < 2 or state.pending_gaps:
                follow_up = self._build_follow_up(session, dimension)
                if follow_up is not None:
                    return follow_up

        return None

    def update_dimension_state(self, session: DiscoverySession, answer: DiscoveryAnswer) -> None:
        state = self._get_state(session, answer.dimension)
        text = answer.answer_text.strip()
        lowered = text.lower()
        normalized = self._normalize_answer(answer.dimension, text)

        state.last_question_id = answer.question_id
        state.last_updated_at = answer.answered_at
        state.extracted_facts.append(text)
        state.pending_gaps = []
        state.normalized_value = normalized

        if self._is_usable_value(answer.dimension, normalized, text):
            state.coverage_score = 2
            state.confidence_score = 2 if not AMBIGUITY_RE.search(text) else 1
        else:
            state.coverage_score = 1
            state.confidence_score = 1
            state.pending_gaps.append(self._gap_message(answer.dimension))

        if answer.dimension in NUMERIC_DIMENSIONS and normalized is not None:
            state.depth_score = 2
        elif answer.dimension in ENUM_DIMENSIONS and normalized is not None:
            state.depth_score = 2
        elif answer.dimension in LIST_DIMENSIONS and normalized is not None:
            state.depth_score = 2
        elif answer.dimension in TRAIT_DIMENSIONS and self._has_trait_depth(text):
            state.depth_score = 2
        elif len(text.split()) >= 6:
            state.depth_score = 1

        if answer.dimension in TRAIT_DIMENSIONS and not self._has_trait_depth(text):
            state.pending_gaps.append("Need a more concrete trait-level description, not just a short label.")

        if answer.dimension is DiscoveryDimension.BLOCKED_TICKERS and normalized is None and not NONE_RE.search(text):
            state.pending_gaps.append("Need explicit tickers or an explicit 'none'.")
        if answer.dimension is DiscoveryDimension.BLOCKED_SECTORS and normalized is None and not NONE_RE.search(text):
            state.pending_gaps.append("Need explicit sectors or an explicit 'none'.")
        if answer.dimension is DiscoveryDimension.BASE_CURRENCY and normalized is None:
            state.pending_gaps.append("Need a base currency such as USD, HKD, EUR, or CNY.")
        if answer.dimension is DiscoveryDimension.TAX_RESIDENCY and len(text.split()) < 1:
            state.pending_gaps.append("Need a tax jurisdiction.")

        if answer.dimension in NUMERIC_DIMENSIONS and normalized is not None and self._numeric_conflict(answer.dimension, normalized, lowered):
            state.conflict_flag = True
        else:
            state.conflict_flag = False

        answer.extracted_signals.extend(signal for signal in self._derive_signals(answer.dimension, text, normalized) if signal not in answer.extracted_signals)

    def _build_follow_up(self, session: DiscoverySession, dimension: DiscoveryDimension) -> DiscoveryQuestion | None:
        answers = self._answers_for_dimension(session.answers, dimension)
        latest = answers[-1] if answers else None
        if latest is None:
            return None

        prompt_text, why, answer_shape = self._follow_up_prompt(dimension, latest.answer_text)
        return self._make_question(
            session,
            dimension=dimension,
            question_type=DiscoveryQuestionType.DEEPENING if dimension in TRAIT_DIMENSIONS else DiscoveryQuestionType.CLARIFICATION,
            source_type=DiscoveryQuestionSource.RULE_TRIGGER,
            prompt_text=prompt_text,
            why=why,
            answer_shape=answer_shape,
            priority=70,
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

    def _normalize_answer(self, dimension: DiscoveryDimension, text: str) -> Any | None:
        lowered = text.lower()

        if dimension in {
            DiscoveryDimension.TARGET_ANNUAL_RETURN,
            DiscoveryDimension.MAX_DRAWDOWN_LIMIT,
            DiscoveryDimension.MAX_ANNUAL_VOLATILITY,
            DiscoveryDimension.MAX_LEVERAGE_RATIO,
            DiscoveryDimension.SINGLE_ASSET_CAP,
        }:
            return self._extract_number(lowered)

        if dimension is DiscoveryDimension.INVESTMENT_HORIZON:
            years = self._extract_years(lowered)
            return years if years is not None else self._extract_int(lowered)

        if dimension in {DiscoveryDimension.ANNUAL_LIQUIDITY_NEED, DiscoveryDimension.AUM_ALLOCATED}:
            return self._extract_money(lowered)

        if dimension is DiscoveryDimension.LIQUIDITY_FREQUENCY:
            return self._extract_keyword(lowered, LIQUIDITY_FREQUENCY_KEYWORDS)

        if dimension is DiscoveryDimension.ACCOUNT_ENTITY_TYPE:
            return self._extract_keyword(lowered, ACCOUNT_ENTITY_KEYWORDS)

        if dimension is DiscoveryDimension.EXECUTION_MODE:
            return self._extract_keyword(lowered, EXECUTION_MODE_KEYWORDS)

        if dimension is DiscoveryDimension.BASE_CURRENCY:
            return self._extract_currency(text)

        if dimension is DiscoveryDimension.TAX_RESIDENCY:
            return text.strip() if text.strip() else None

        if dimension is DiscoveryDimension.BLOCKED_SECTORS:
            if NONE_RE.search(text):
                return []
            sectors = self._extract_sectors(lowered)
            return sectors or None

        if dimension is DiscoveryDimension.BLOCKED_TICKERS:
            if NONE_RE.search(text):
                return []
            tickers = sorted({token.upper() for token in TICKER_RE.findall(text)})
            return tickers or None

        if dimension in TRAIT_DIMENSIONS:
            return text.strip() if self._has_trait_depth(text) else None

        return text.strip() or None

    def _is_usable_value(self, dimension: DiscoveryDimension, normalized: Any | None, text: str) -> bool:
        if dimension in LIST_DIMENSIONS:
            return normalized is not None
        if dimension in TRAIT_DIMENSIONS:
            return normalized is not None
        return normalized is not None and not AMBIGUITY_RE.search(text)

    def _gap_message(self, dimension: DiscoveryDimension) -> str:
        return f"{dimension.value} still needs a more concrete answer."

    def _follow_up_prompt(
        self,
        dimension: DiscoveryDimension,
        text: str,
    ) -> tuple[str, str, ExpectedAnswerShape]:
        if dimension is DiscoveryDimension.TARGET_ANNUAL_RETURN:
            return (
                "Please give one explicit annual return target percentage, such as 6, 8.5, or 10.",
                "The optimization target needs one concrete number.",
                ExpectedAnswerShape.NUMBER,
            )
        if dimension is DiscoveryDimension.INVESTMENT_HORIZON:
            return (
                "Please translate that horizon into a concrete number of years.",
                "The portfolio horizon has to be machine-usable, not just 'long term'.",
                ExpectedAnswerShape.NUMBER,
            )
        if dimension is DiscoveryDimension.ANNUAL_LIQUIDITY_NEED:
            return (
                "What annual cash amount should I reserve for this mandate, in dollars or the base currency amount?",
                "The system needs an absolute annual liquidity number.",
                ExpectedAnswerShape.MONEY_RANGE,
            )
        if dimension is DiscoveryDimension.LIQUIDITY_FREQUENCY:
            return (
                "Should that liquidity be treated as monthly, quarterly, annual, or none?",
                "Liquidity cadence affects the shape of future allocations.",
                ExpectedAnswerShape.CHOICE,
            )
        if dimension is DiscoveryDimension.MAX_DRAWDOWN_LIMIT:
            return (
                "What exact drawdown percentage should trigger a hard risk response?",
                "Drawdown limits need to be explicit to become enforceable.",
                ExpectedAnswerShape.NUMBER,
            )
        if dimension is DiscoveryDimension.MAX_ANNUAL_VOLATILITY:
            return (
                "What annualized volatility percentage should be treated as the ceiling here?",
                "Volatility needs a numeric cap rather than a qualitative label.",
                ExpectedAnswerShape.NUMBER,
            )
        if dimension is DiscoveryDimension.MAX_LEVERAGE_RATIO:
            return (
                "Please give one leverage ratio limit. Use 0 if leverage is completely forbidden.",
                "Leverage permission must be binary and numeric.",
                ExpectedAnswerShape.NUMBER,
            )
        if dimension is DiscoveryDimension.SINGLE_ASSET_CAP:
            return (
                "What exact single-asset cap percentage should the system enforce?",
                "Concentration control needs a concrete cap.",
                ExpectedAnswerShape.NUMBER,
            )
        if dimension is DiscoveryDimension.BLOCKED_SECTORS:
            return (
                "List the blocked sectors explicitly, or say none if there are no sector bans.",
                "Sector constraints must be filterable by name.",
                ExpectedAnswerShape.LIST,
            )
        if dimension is DiscoveryDimension.BLOCKED_TICKERS:
            return (
                "List the blocked tickers explicitly, or say none if there are no ticker bans.",
                "Ticker restrictions must be machine-readable.",
                ExpectedAnswerShape.LIST,
            )
        if dimension is DiscoveryDimension.BASE_CURRENCY:
            return (
                "Please give the base currency explicitly, such as USD, HKD, EUR, or CNY.",
                "Currency assumptions should never be guessed.",
                ExpectedAnswerShape.CHOICE,
            )
        if dimension is DiscoveryDimension.TAX_RESIDENCY:
            return (
                "Which tax jurisdiction should I treat as the governing one for this account?",
                "Tax-aware logic needs one explicit residency or jurisdiction.",
                ExpectedAnswerShape.OPEN_TEXT,
            )
        if dimension is DiscoveryDimension.ACCOUNT_ENTITY_TYPE:
            return (
                "Please choose one: individual, trust, or corporate.",
                "Entity type affects execution and compliance assumptions.",
                ExpectedAnswerShape.CHOICE,
            )
        if dimension is DiscoveryDimension.AUM_ALLOCATED:
            return (
                "What is the approximate total capital amount allocated to this mandate?",
                "The system needs the capital base to size risk correctly.",
                ExpectedAnswerShape.MONEY_RANGE,
            )
        if dimension is DiscoveryDimension.EXECUTION_MODE:
            return (
                "Should this be advisory with human confirmation, or discretionary with delegated execution authority?",
                "Execution mode defines the account's permission boundary.",
                ExpectedAnswerShape.CHOICE,
            )
        if dimension is DiscoveryDimension.FINANCIAL_LITERACY:
            return (
                "Please describe the user's financial literacy more concretely, including what products or concepts they truly understand.",
                "The agent needs a practical communication model, not a vague sophistication label.",
                ExpectedAnswerShape.OPEN_TEXT,
            )
        if dimension is DiscoveryDimension.WEALTH_ORIGIN_DNA:
            return (
                "Please explain the capital story in a way that reveals what kinds of assets or narratives the user naturally trusts or distrusts.",
                "Wealth origin should influence interpretation, not just be a biography note.",
                ExpectedAnswerShape.OPEN_TEXT,
            )
        return (
            "Please describe the user's stress behavior more concretely, including what actually happens when markets fall fast.",
            "Behavioral risk needs specific observed patterns, not just a label like conservative or aggressive.",
            ExpectedAnswerShape.OPEN_TEXT,
        )

    def _derive_signals(self, dimension: DiscoveryDimension, text: str, normalized: Any | None) -> list[str]:
        lowered = text.lower()
        signals: list[str] = []
        if normalized is not None:
            signals.append("normalized")
        if AMBIGUITY_RE.search(text):
            signals.append("ambiguity")
        if dimension in NUMERIC_DIMENSIONS and normalized is not None:
            signals.append("quantified")
        if dimension in LIST_DIMENSIONS:
            signals.append("filter_rule")
        if dimension in TRAIT_DIMENSIONS:
            signals.append("persona_trait")
        if "panic" in lowered or "anxious" in lowered:
            signals.append("stress_anxiety")
        if "founder" in lowered or "business" in lowered or "inherit" in lowered:
            signals.append("wealth_origin")
        return signals

    def _numeric_conflict(self, dimension: DiscoveryDimension, normalized: Any, lowered: str) -> bool:
        value = float(normalized)
        if dimension is DiscoveryDimension.MAX_DRAWDOWN_LIMIT:
            return value > 80
        if dimension is DiscoveryDimension.MAX_ANNUAL_VOLATILITY:
            return value > 100
        if dimension is DiscoveryDimension.MAX_LEVERAGE_RATIO:
            return value > 10
        if dimension is DiscoveryDimension.SINGLE_ASSET_CAP:
            return value > 100
        if dimension is DiscoveryDimension.TARGET_ANNUAL_RETURN:
            return value > 100
        if dimension is DiscoveryDimension.INVESTMENT_HORIZON:
            return value <= 0
        if dimension in {DiscoveryDimension.ANNUAL_LIQUIDITY_NEED, DiscoveryDimension.AUM_ALLOCATED}:
            return value < 0
        return False

    def _extract_number(self, lowered: str) -> float | None:
        match = NUMBER_RE.search(lowered)
        if match is None:
            return None
        try:
            return float(match.group(1))
        except ValueError:
            return None

    def _extract_int(self, lowered: str) -> int | None:
        match = NUMBER_RE.search(lowered)
        if match is None:
            return None
        try:
            return int(float(match.group(1)))
        except ValueError:
            return None

    def _extract_years(self, lowered: str) -> int | None:
        match = YEARS_RE.search(lowered)
        if match is None:
            return None
        try:
            return int(match.group(1))
        except ValueError:
            return None

    def _extract_money(self, lowered: str) -> float | None:
        match = MONEY_RE.search(lowered.replace(",", ""))
        if match is None:
            return None
        token = match.group(1).replace("$", "").strip()
        multiplier = 1.0
        if token.lower().endswith("k"):
            multiplier = 1_000.0
            token = token[:-1]
        elif token.lower().endswith("m"):
            multiplier = 1_000_000.0
            token = token[:-1]
        elif token.lower().endswith("b"):
            multiplier = 1_000_000_000.0
            token = token[:-1]
        try:
            return float(token) * multiplier
        except ValueError:
            return None

    def _extract_keyword(self, lowered: str, keyword_map: dict[str, str]) -> str | None:
        for keyword, value in keyword_map.items():
            if keyword in lowered:
                return value
        return None

    def _extract_currency(self, text: str) -> str | None:
        match = CURRENCY_RE.search(text.upper())
        if match is not None:
            return match.group(1)
        lowered = text.lower().replace(" ", "")
        for keyword, value in CURRENCY_KEYWORDS.items():
            if keyword in lowered:
                return value
        return None

    def _extract_sectors(self, lowered: str) -> list[str]:
        sectors = {value for keyword, value in SECTOR_MAP.items() if keyword in lowered}
        return sorted(sectors)

    def _has_trait_depth(self, text: str) -> bool:
        return len(text.split()) >= 10 and not NONE_RE.search(text)

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

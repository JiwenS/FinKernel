from __future__ import annotations

from contextlib import contextmanager
from decimal import Decimal
from typing import Iterator

from sqlalchemy.orm import Session, sessionmaker

from finkernel.schemas.profile import PersonaProfile, ProfileAction
from finkernel.schemas.simulation import (
    AlertFact,
    AlertFactList,
    CandidateTradeAction,
    ConstraintFinding,
    PortfolioSnapshot,
    PositionSnapshot,
    RiskSignal,
    RiskSummary,
    SimulatedTradeInput,
    TradeSimulationResult,
)
from finkernel.services.authorization import AuthorizationError, ProfileAuthorizer
from finkernel.services.interfaces import BrokerClient
from finkernel.storage.repositories import WorkflowRepository


class SimulationService:
    def __init__(
        self,
        *,
        session_factory: sessionmaker[Session],
        broker_client: BrokerClient,
        workflow_repository: WorkflowRepository | None = None,
        profile_authorizer: ProfileAuthorizer | None = None,
    ) -> None:
        self.session_factory = session_factory
        self.broker_client = broker_client
        self.workflow_repository = workflow_repository or WorkflowRepository()
        self.profile_authorizer = profile_authorizer or ProfileAuthorizer()

    @contextmanager
    def _session_scope(self) -> Iterator[Session]:
        session = self.session_factory()
        try:
            yield session
        finally:
            session.close()

    def get_portfolio_snapshot(self, *, profile: PersonaProfile) -> PortfolioSnapshot:
        self.profile_authorizer._ensure_action(profile, ProfileAction.OBSERVE)
        account = self.broker_client.get_account_summary()
        positions = self._scoped_positions(profile)
        open_requests, _ = self._list_profile_requests(profile)
        pending_notional = sum(
            Decimal(item.quantity) * Decimal(item.limit_price)
            for item in open_requests
            if item.state in {"REQUESTED", "POLICY_EVALUATED", "PENDING_CONFIRMATION", "SUBMITTING", "SUBMITTED", "ACKED"}
        )
        return PortfolioSnapshot(
            owner_id=profile.owner_id,
            profile_id=profile.profile_id,
            bucket_name=profile.bucket_name,
            account_ids=profile.allowed_accounts,
            buying_power=self._scaled_amount(account.get("buying_power", "0"), profile),
            cash=self._scaled_amount(account.get("cash", "0"), profile),
            equity=self._scaled_amount(account.get("equity", "0"), profile),
            positions=positions,
            open_request_count=len(open_requests),
            pending_notional=pending_notional,
        )

    def get_risk_summary(self, *, profile: PersonaProfile) -> RiskSummary:
        self.profile_authorizer._ensure_action(profile, ProfileAction.OBSERVE)
        snapshot = self.get_portfolio_snapshot(profile=profile)
        total_market_value = sum(position.market_value for position in snapshot.positions)
        largest_position = max((position.market_value for position in snapshot.positions), default=Decimal("0"))
        largest_position_pct = (largest_position / total_market_value * Decimal("100")) if total_market_value else Decimal("0")
        signals: list[RiskSignal] = []
        if profile.risk_budget.value == "low" and largest_position_pct > Decimal("35"):
            signals.append(RiskSignal(code="CONCENTRATION_HIGH", severity="warning", message="Largest position exceeds 35% for low-risk profile."))
        if snapshot.pending_notional > snapshot.buying_power:
            signals.append(RiskSignal(code="PENDING_NOTIONAL_EXCEEDS_BUYING_POWER", severity="warning", message="Pending notional exceeds current buying power."))
        if snapshot.cash < Decimal("100"):
            signals.append(RiskSignal(code="LOW_CASH_BUFFER", severity="info", message="Cash buffer is very low."))
        return RiskSummary(
            owner_id=profile.owner_id,
            profile_id=profile.profile_id,
            bucket_name=profile.bucket_name,
            risk_budget=profile.risk_budget.value,
            total_market_value=total_market_value,
            pending_notional=snapshot.pending_notional,
            cash=snapshot.cash,
            buying_power=snapshot.buying_power,
            largest_position_pct=largest_position_pct.quantize(Decimal("0.01")) if total_market_value else Decimal("0.00"),
            signals=signals,
        )

    def simulate_trade(self, *, profile: PersonaProfile, trade_input: SimulatedTradeInput) -> TradeSimulationResult:
        self.profile_authorizer._ensure_action(profile, ProfileAction.SIMULATE)
        self.profile_authorizer._ensure_account(profile, trade_input.account_id)
        self.profile_authorizer._ensure_market(profile, trade_input.market)
        self.profile_authorizer._ensure_symbol(profile, trade_input.symbol)
        snapshot = self.get_portfolio_snapshot(profile=profile)
        current_qty = self._position_qty(snapshot.positions, trade_input.symbol)
        notional = trade_input.quantity * trade_input.limit_price
        projected_qty = current_qty + trade_input.quantity if trade_input.side == "buy" else current_qty - trade_input.quantity
        projected_cash_after = snapshot.cash - notional if trade_input.side == "buy" else snapshot.cash + notional
        constraints = [
            ConstraintFinding(code="HITL_REQUIRED", status="info", message="If executed, this action would still require human approval."),
            ConstraintFinding(code="PROFILE_BOUND", status="ok", message=f"Simulation is constrained to profile {profile.profile_id}."),
        ]
        if trade_input.side == "sell" and projected_qty < 0:
            constraints.append(ConstraintFinding(code="SHORT_POSITION_WARNING", status="warning", message="Projected position would go below zero."))
        if trade_input.side == "buy" and notional > snapshot.buying_power:
            constraints.append(ConstraintFinding(code="BUYING_POWER_WARNING", status="warning", message="Trade notional exceeds current buying power."))
        return TradeSimulationResult(
            owner_id=profile.owner_id,
            profile_id=profile.profile_id,
            symbol=trade_input.symbol,
            side=trade_input.side,
            quantity=trade_input.quantity,
            limit_price=trade_input.limit_price,
            notional=notional,
            current_position_qty=current_qty,
            projected_position_qty=projected_qty,
            cash_before=snapshot.cash,
            projected_cash_after=projected_cash_after,
            assumptions=[
                "Uses current broker account and position snapshot.",
                "Does not execute any order.",
                "Does not model slippage or commissions.",
            ],
            constraints=constraints,
        )

    def build_candidate_trade_action(self, *, profile: PersonaProfile, trade_input: SimulatedTradeInput) -> CandidateTradeAction:
        simulation = self.simulate_trade(profile=profile, trade_input=trade_input)
        summary = f"{trade_input.side.upper()} {trade_input.quantity} {trade_input.symbol} @ {trade_input.limit_price} under profile {profile.profile_id}"
        return CandidateTradeAction(
            owner_id=profile.owner_id,
            profile_id=profile.profile_id,
            summary=summary,
            rationale_basis=[
                "Persona-scoped current portfolio snapshot",
                "Profile risk budget framing",
                "Projected cash and position changes",
            ],
            trade_template=trade_input,
            simulation=simulation,
        )

    def get_alerts(self, *, profile: PersonaProfile) -> AlertFactList:
        risk = self.get_risk_summary(profile=profile)
        alerts = [AlertFact(code=signal.code, severity=signal.severity, message=signal.message) for signal in risk.signals]
        if not alerts:
            alerts.append(AlertFact(code="NO_ACTIVE_ALERTS", severity="info", message="No active persona-scoped alerts."))
        return AlertFactList(owner_id=profile.owner_id, profile_id=profile.profile_id, alerts=alerts)

    def _scoped_positions(self, profile: PersonaProfile) -> list[PositionSnapshot]:
        return [position for position in self.broker_client.list_positions() if profile.allows_symbol(position.symbol)]

    def _position_qty(self, positions: list[PositionSnapshot], symbol: str) -> Decimal:
        for position in positions:
            if position.symbol == symbol.upper():
                return position.quantity
        return Decimal("0")

    def _list_profile_requests(self, profile: PersonaProfile):
        with self._session_scope() as session:
            return self.workflow_repository.list_requests(
                session,
                account_ids=profile.allowed_accounts,
                symbols=profile.allowed_symbols or None,
                limit=200,
            )

    def _scaled_amount(self, raw_value: str | Decimal, profile: PersonaProfile) -> Decimal:
        return Decimal(str(raw_value)) * profile.capital_allocation_pct

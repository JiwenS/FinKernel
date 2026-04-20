from __future__ import annotations

from contextlib import contextmanager
from datetime import UTC, datetime, timedelta
from decimal import Decimal
import re
from typing import Iterator

from sqlalchemy.orm import Session, sessionmaker

from finkernel.schemas.advisory import (
    AdvisorRunResponse,
    AdvisorRunResult,
    StrategyCreate,
    StrategyFromTextCreate,
    StrategyFromTextResponse,
    StrategyInterpretation,
    StrategyResponse,
    SuggestedTradeAction,
    SuggestionResponse,
    SuggestionStatus,
    SuggestionType,
)
from finkernel.schemas.identity import ActorContext
from finkernel.schemas.profile import PersonaProfile, ProfileAction
from finkernel.schemas.trade import OrderSide, TradeRequestCreate, TradeRequestResponse
from finkernel.services.authorization import AuthorizationError, ProfileAuthorizer
from finkernel.services.market_data import MarketDataService
from finkernel.services.profiles import ProfileStore
from finkernel.services.simulation import SimulationService
from finkernel.storage.models import StrategyModel, SuggestionModel
from finkernel.storage.repositories import StrategyRepository, SuggestionRepository, WorkflowRepository
from finkernel.workflow.service import TradeWorkflowService


class AdvisoryService:
    def __init__(
        self,
        *,
        session_factory: sessionmaker[Session],
        profile_store: ProfileStore,
        workflow_service: TradeWorkflowService,
        simulation_service: SimulationService,
        market_data_service: MarketDataService,
        strategy_repository: StrategyRepository | None = None,
        suggestion_repository: SuggestionRepository | None = None,
        workflow_repository: WorkflowRepository | None = None,
        profile_authorizer: ProfileAuthorizer | None = None,
    ) -> None:
        self.session_factory = session_factory
        self.profile_store = profile_store
        self.workflow_service = workflow_service
        self.simulation_service = simulation_service
        self.market_data_service = market_data_service
        self.strategy_repository = strategy_repository or StrategyRepository()
        self.suggestion_repository = suggestion_repository or SuggestionRepository()
        self.workflow_repository = workflow_repository or WorkflowRepository()
        self.profile_authorizer = profile_authorizer or ProfileAuthorizer()

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

    def create_strategy(self, *, profile: PersonaProfile, payload: StrategyCreate) -> StrategyResponse:
        self.profile_authorizer._ensure_action(profile, ProfileAction.OBSERVE)
        for symbol in payload.target_allocation:
            self.profile_authorizer._ensure_symbol(profile, symbol)
        with self._session_scope() as session:
            model = StrategyModel(
                owner_id=profile.owner_id,
                profile_id=profile.profile_id,
                profile_version=profile.version,
                name=payload.name,
                mandate_summary=payload.mandate_summary,
                budget=payload.budget,
                target_allocation={symbol: str(weight) for symbol, weight in payload.target_allocation.items()},
                rebalance_threshold_pct=payload.rebalance_threshold_pct,
                active=payload.active,
            )
            stored = self.strategy_repository.add(session, model)
            return self._to_strategy_response(stored)

    def create_strategy_from_text(self, *, profile: PersonaProfile, payload: StrategyFromTextCreate) -> StrategyFromTextResponse:
        interpretation = self._interpret_strategy_text(profile=profile, text=payload.text)
        strategy = self.create_strategy(
            profile=profile,
            payload=StrategyCreate(
                name=self._build_strategy_name(interpretation.detected_style, interpretation.selected_symbols),
                mandate_summary=payload.text,
                budget=interpretation.detected_budget,
                target_allocation=interpretation.target_allocation,
                rebalance_threshold_pct=interpretation.rebalance_threshold_pct,
                active=payload.auto_activate,
            ),
        )
        return StrategyFromTextResponse(strategy=strategy, interpretation=interpretation)

    def list_strategies(self, *, profile: PersonaProfile) -> list[StrategyResponse]:
        self.profile_authorizer._ensure_action(profile, ProfileAction.OBSERVE)
        with self._session_scope() as session:
            items = self.strategy_repository.list_for_profile(session, profile.profile_id)
            return [self._to_strategy_response(item) for item in items]

    def get_strategy(self, strategy_id: str, *, profile: PersonaProfile) -> StrategyResponse | None:
        self.profile_authorizer._ensure_action(profile, ProfileAction.OBSERVE)
        with self._session_scope() as session:
            model = self.strategy_repository.get(session, strategy_id)
            if model is None or model.profile_id != profile.profile_id:
                return None
            return self._to_strategy_response(model)

    def list_suggestions(self, *, profile: PersonaProfile, status: SuggestionStatus | None = None) -> list[SuggestionResponse]:
        self.profile_authorizer._ensure_action(profile, ProfileAction.OBSERVE)
        with self._session_scope() as session:
            items = self.suggestion_repository.list_for_profile(
                session,
                profile.profile_id,
                status=status.value if status else None,
            )
            return [self._to_suggestion_response(session, self._sync_suggestion_status(session, item)) for item in items]

    def get_suggestion(self, suggestion_id: str, *, profile: PersonaProfile) -> SuggestionResponse | None:
        self.profile_authorizer._ensure_action(profile, ProfileAction.OBSERVE)
        with self._session_scope() as session:
            model = self.suggestion_repository.get(session, suggestion_id)
            if model is None or model.profile_id != profile.profile_id:
                return None
            model = self._sync_suggestion_status(session, model)
            return self._to_suggestion_response(session, model)

    def approve_suggestion(self, suggestion_id: str, *, profile: PersonaProfile) -> SuggestionResponse:
        self.profile_authorizer._ensure_action(profile, ProfileAction.REQUEST_EXECUTION)
        with self._session_scope() as session:
            model = self.suggestion_repository.get(session, suggestion_id)
            if model is None or model.profile_id != profile.profile_id:
                raise ValueError(f"Suggestion {suggestion_id} was not found.")
            if not model.workflow_request_id:
                raise ValueError(f"Suggestion {suggestion_id} does not have a workflow request.")
        self.workflow_service.approve_trade_request(model.workflow_request_id, actor_id=profile.profile_id)
        return self.get_suggestion(suggestion_id, profile=profile)  # type: ignore[return-value]

    def reject_suggestion(self, suggestion_id: str, *, profile: PersonaProfile) -> SuggestionResponse:
        self.profile_authorizer._ensure_action(profile, ProfileAction.REQUEST_EXECUTION)
        with self._session_scope() as session:
            model = self.suggestion_repository.get(session, suggestion_id)
            if model is None or model.profile_id != profile.profile_id:
                raise ValueError(f"Suggestion {suggestion_id} was not found.")
            if not model.workflow_request_id:
                raise ValueError(f"Suggestion {suggestion_id} does not have a workflow request.")
        self.workflow_service.reject_trade_request(model.workflow_request_id, actor_id=profile.profile_id)
        return self.get_suggestion(suggestion_id, profile=profile)  # type: ignore[return-value]

    def run_once(self, *, profile_id: str | None = None) -> AdvisorRunResponse:
        with self._session_scope() as session:
            strategies = (
                self.strategy_repository.list_for_profile(session, profile_id, active_only=True)
                if profile_id
                else self.strategy_repository.list_active(session)
            )

        results: list[AdvisorRunResult] = []
        created = 0
        for strategy in strategies:
            profile = self.profile_store.get(strategy.profile_id, version=strategy.profile_version)
            result = self._run_strategy(profile=profile, strategy_id=strategy.strategy_id)
            if result.created_suggestion_id:
                created += 1
            results.append(result)
        return AdvisorRunResponse(results=results, total_strategies=len(strategies), created_suggestions=created)

    def _run_strategy(self, *, profile: PersonaProfile, strategy_id: str) -> AdvisorRunResult:
        if not profile.allows_action(ProfileAction.REQUEST_EXECUTION):
            return AdvisorRunResult(
                profile_id=profile.profile_id,
                strategy_id=strategy_id,
                skipped_reason="Profile does not permit request_execution for autonomous suggestions.",
            )
        with self._session_scope() as session:
            strategy = self.strategy_repository.get(session, strategy_id)
            if strategy is None or not strategy.active:
                return AdvisorRunResult(profile_id=profile.profile_id, strategy_id=strategy_id, skipped_reason="Strategy is missing or inactive.")
            if self.suggestion_repository.has_open_suggestion_for_strategy(session, strategy.strategy_id):
                return AdvisorRunResult(profile_id=profile.profile_id, strategy_id=strategy.strategy_id, skipped_reason="An open suggestion already exists.")

        snapshot = self.simulation_service.get_portfolio_snapshot(profile=profile)
        target_allocation = {symbol: Decimal(str(weight)) for symbol, weight in strategy.target_allocation.items()}
        prices = self.market_data_service.get_latest_prices(list(target_allocation))
        if not prices:
            return AdvisorRunResult(profile_id=profile.profile_id, strategy_id=strategy.strategy_id, skipped_reason="No market prices were available.")

        current_values = {position.symbol: position.market_value for position in snapshot.positions}
        current_quantities = {position.symbol: position.quantity for position in snapshot.positions}
        denominator = sum(target_allocation.values())
        portfolio_base = min(snapshot.equity, strategy.budget) if strategy.budget is not None else snapshot.equity
        if portfolio_base <= 0:
            return AdvisorRunResult(profile_id=profile.profile_id, strategy_id=strategy.strategy_id, skipped_reason="No portfolio base is available.")

        best_symbol: str | None = None
        best_gap = Decimal("0")
        best_side = OrderSide.BUY
        for symbol, raw_weight in target_allocation.items():
            if symbol not in prices:
                continue
            target_value = (portfolio_base * raw_weight) / denominator
            current_value = current_values.get(symbol, Decimal("0"))
            gap = target_value - current_value
            if abs(gap) > abs(best_gap):
                best_gap = gap
                best_symbol = symbol
                best_side = OrderSide.BUY if gap > 0 else OrderSide.SELL

        if best_symbol is None:
            return AdvisorRunResult(profile_id=profile.profile_id, strategy_id=strategy.strategy_id, skipped_reason="No priced symbol could be evaluated.")

        if abs(best_gap) / portfolio_base < Decimal(str(strategy.rebalance_threshold_pct)):
            return AdvisorRunResult(profile_id=profile.profile_id, strategy_id=strategy.strategy_id, skipped_reason="Portfolio drift is below threshold.")

        price = prices[best_symbol]
        if best_side is OrderSide.BUY:
            available_notional = min(best_gap, snapshot.buying_power)
            quantity = int(available_notional / price)
        else:
            available_quantity = int(current_quantities.get(best_symbol, Decimal("0")))
            quantity = min(available_quantity, int(abs(best_gap) / price))
        quantity = self._apply_execution_guards(quantity=quantity, price=price)
        if quantity < 1:
            return AdvisorRunResult(profile_id=profile.profile_id, strategy_id=strategy.strategy_id, skipped_reason="Calculated quantity was below 1 share.")

        current_weight_pct = ((current_values.get(best_symbol, Decimal("0")) / portfolio_base) * Decimal("100")).quantize(Decimal("0.01"))
        target_weight_pct = ((target_allocation[best_symbol] / denominator) * Decimal("100")).quantize(Decimal("0.01"))
        action = SuggestedTradeAction(
            symbol=best_symbol,
            side=best_side,
            quantity=quantity,
            limit_price=price.quantize(Decimal("0.01")),
            weight_delta_pct=(target_weight_pct - current_weight_pct).quantize(Decimal("0.01")),
        )
        summary = f"{best_side.value.upper()} {quantity} {best_symbol} @ {action.limit_price} to move toward target allocation."
        rationale = (
            f"Strategy {strategy.name} targets {target_weight_pct}% in {best_symbol} while the current profile-scoped weight is "
            f"{current_weight_pct}%. Latest price was {action.limit_price}; generated from the autonomous advisor loop."
        )
        request = self.workflow_service.submit_trade_request(
            TradeRequestCreate(
                actor=ActorContext(user_id=profile.owner_id, account_id=profile.allowed_accounts[0], session_id=f"advisor:{strategy.strategy_id}"),
                symbol=action.symbol,
                side=action.side,
                quantity=action.quantity,
                limit_price=action.limit_price,
                notes=f"{summary}\n\n{rationale}",
                idempotency_key=f"advisor-{strategy.strategy_id}-{best_symbol}-{best_side.value}-{datetime.now(UTC).strftime('%Y%m%dT%H%M%S')}",
            ),
            request_source="advisor-loop",
            profile=profile,
        )
        with self._session_scope() as session:
            stored = self.suggestion_repository.add(
                session,
                SuggestionModel(
                    strategy_id=strategy.strategy_id,
                    workflow_request_id=request.request_id,
                    owner_id=profile.owner_id,
                    profile_id=profile.profile_id,
                    profile_version=profile.version,
                    suggestion_type=SuggestionType.REBALANCE.value,
                    status=SuggestionStatus.PENDING.value,
                    summary=summary,
                    rationale=rationale,
                    actions=[action.model_dump(mode="json")],
                    context_payload={
                        "target_weight_pct": str(target_weight_pct),
                        "current_weight_pct": str(current_weight_pct),
                        "portfolio_base": str(portfolio_base),
                    },
                    expires_at=datetime.now(UTC) + timedelta(hours=8),
                ),
            )
            return AdvisorRunResult(profile_id=profile.profile_id, strategy_id=strategy.strategy_id, created_suggestion_id=stored.suggestion_id)

    def _apply_execution_guards(self, *, quantity: int, price: Decimal) -> int:
        max_qty = int(self.workflow_service.settings.max_limit_order_qty)
        max_notional_qty = int(Decimal(str(self.workflow_service.settings.max_limit_order_notional)) / price)
        safe_ceiling = min(quantity, max_qty, max_notional_qty)
        return max(safe_ceiling, 0)

    def _interpret_strategy_text(self, *, profile: PersonaProfile, text: str) -> StrategyInterpretation:
        normalized = text.strip()
        lowered = normalized.lower()
        parser_notes: list[str] = []

        selected_symbols = [symbol for symbol in profile.allowed_symbols if re.search(rf"\b{re.escape(symbol.lower())}\b", lowered)]
        if not selected_symbols:
            selected_symbols = list(profile.allowed_symbols[:3] or [])
            parser_notes.append("No explicit symbol was detected; defaulted to the first profile-allowed symbols.")
        else:
            parser_notes.append("Used symbols explicitly mentioned in the text.")

        detected_budget = self._extract_budget(normalized)
        if detected_budget is not None:
            parser_notes.append(f"Detected a budget of {detected_budget}.")

        detected_style = self._detect_style(lowered, profile)
        parser_notes.append(f"Detected style: {detected_style}.")

        target_allocation = self._build_target_allocation(detected_style=detected_style, symbols=selected_symbols)
        rebalance_threshold_pct = self._infer_rebalance_threshold(detected_style)
        return StrategyInterpretation(
            detected_style=detected_style,
            detected_budget=detected_budget,
            selected_symbols=selected_symbols,
            target_allocation=target_allocation,
            rebalance_threshold_pct=rebalance_threshold_pct,
            parser_notes=parser_notes,
        )

    def _detect_style(self, lowered_text: str, profile: PersonaProfile) -> str:
        aggressive_keywords = ["激进", "成长", "growth", "aggressive", "high conviction", "high-conviction"]
        conservative_keywords = ["稳健", "保守", "低风险", "conservative", "defensive", "low risk", "capital preservation"]
        balanced_keywords = ["平衡", "均衡", "balanced"]
        if any(keyword in lowered_text for keyword in aggressive_keywords):
            return "aggressive_growth"
        if any(keyword in lowered_text for keyword in conservative_keywords):
            return "conservative"
        if any(keyword in lowered_text for keyword in balanced_keywords):
            return "balanced"
        return {
            "high": "aggressive_growth",
            "medium": "balanced",
            "low": "conservative",
        }[profile.risk_budget.value]

    def _build_target_allocation(self, *, detected_style: str, symbols: list[str]) -> dict[str, Decimal]:
        if not symbols:
            return {}
        if len(symbols) == 1:
            return {symbols[0]: Decimal("1.00")}
        if detected_style == "aggressive_growth":
            base = [Decimal("0.60"), Decimal("0.25"), Decimal("0.15")]
        elif detected_style == "conservative":
            base = [Decimal("0.55"), Decimal("0.45"), Decimal("0.00")]
        else:
            base = [Decimal("0.40"), Decimal("0.35"), Decimal("0.25")]
        allocation: dict[str, Decimal] = {}
        sliced = base[: len(symbols)]
        total = sum(sliced)
        for symbol, weight in zip(symbols, sliced, strict=False):
            allocation[symbol] = (weight / total).quantize(Decimal("0.0001"))
        return allocation

    def _infer_rebalance_threshold(self, detected_style: str) -> Decimal:
        if detected_style == "aggressive_growth":
            return Decimal("0.08")
        if detected_style == "conservative":
            return Decimal("0.04")
        return Decimal("0.05")

    def _build_strategy_name(self, detected_style: str, symbols: list[str]) -> str:
        style_label = {
            "aggressive_growth": "Growth",
            "balanced": "Balanced",
            "conservative": "Conservative",
        }.get(detected_style, "Advisor")
        symbol_label = "/".join(symbols[:3]) if symbols else "Portfolio"
        return f"{style_label} {symbol_label} Strategy"

    def _extract_budget(self, text: str) -> Decimal | None:
        compact = text.replace(",", "")
        usd_match = re.search(r"(?i)(?:\$|usd\s*)?(\d+(?:\.\d+)?)\s*k", compact)
        if usd_match:
            value = Decimal(usd_match.group(1)) * Decimal("1000")
            return value.quantize(Decimal("0.01"))

        usd_match = re.search(r"(?i)(?:\$|usd\s*)(\d+(?:\.\d+)?)", compact)
        if usd_match:
            value = Decimal(usd_match.group(1))
            return value.quantize(Decimal("0.01"))

        cn_match = re.search(r"(\d+(?:\.\d+)?)\s*(万|w)\b", compact, flags=re.IGNORECASE)
        if cn_match:
            value = Decimal(cn_match.group(1)) * Decimal("10000")
            return value.quantize(Decimal("0.01"))

        plain_match = re.search(r"\b(\d{4,7}(?:\.\d+)?)\b", compact)
        if plain_match:
            return Decimal(plain_match.group(1)).quantize(Decimal("0.01"))
        return None

    def _sync_suggestion_status(self, session: Session, model: SuggestionModel) -> SuggestionModel:
        if not model.workflow_request_id:
            return model
        request = self.workflow_repository.get(session, model.workflow_request_id)
        if request is None:
            return model
        new_status = self._map_workflow_state_to_suggestion_status(request.state)
        if new_status != model.status:
            model.status = new_status
            session.flush()
        return model

    def _map_workflow_state_to_suggestion_status(self, workflow_state: str) -> str:
        if workflow_state in {"REQUESTED", "POLICY_EVALUATED", "PENDING_CONFIRMATION"}:
            return SuggestionStatus.PENDING.value
        if workflow_state in {"CONFIRMED", "SUBMITTING", "SUBMITTED", "ACKED", "PARTIALLY_FILLED", "CANCEL_REQUESTED", "CANCELING"}:
            return SuggestionStatus.APPROVED.value
        if workflow_state in {"FILLED", "CANCELED"}:
            return SuggestionStatus.EXECUTED.value
        if workflow_state == "EXPIRED":
            return SuggestionStatus.EXPIRED.value
        return SuggestionStatus.REJECTED.value

    def _to_strategy_response(self, model: StrategyModel) -> StrategyResponse:
        return StrategyResponse(
            strategy_id=model.strategy_id,
            owner_id=model.owner_id,
            profile_id=model.profile_id,
            profile_version=model.profile_version,
            name=model.name,
            mandate_summary=model.mandate_summary,
            budget=model.budget,
            target_allocation={symbol: Decimal(str(weight)) for symbol, weight in model.target_allocation.items()},
            rebalance_threshold_pct=model.rebalance_threshold_pct,
            active=model.active,
            created_at=model.created_at,
            updated_at=model.updated_at,
        )

    def _to_suggestion_response(self, session: Session, model: SuggestionModel) -> SuggestionResponse:
        workflow_request: TradeRequestResponse | None = None
        if model.workflow_request_id:
            request = self.workflow_repository.get(session, model.workflow_request_id)
            if request is not None:
                workflow_request = self.workflow_service._to_response(request)
        return SuggestionResponse(
            suggestion_id=model.suggestion_id,
            strategy_id=model.strategy_id,
            workflow_request_id=model.workflow_request_id,
            owner_id=model.owner_id,
            profile_id=model.profile_id,
            profile_version=model.profile_version,
            suggestion_type=model.suggestion_type,
            status=model.status,
            summary=model.summary,
            rationale=model.rationale,
            actions=[SuggestedTradeAction.model_validate(item) for item in model.actions],
            context_payload=model.context_payload,
            expires_at=model.expires_at,
            created_at=model.created_at,
            updated_at=model.updated_at,
            workflow_request=workflow_request,
        )

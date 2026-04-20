from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from mcp.server.fastmcp import FastMCP
from mcp.server.fastmcp.server import TransportSecuritySettings

from finkernel.schemas.advisory import StrategyCreate, StrategyFromTextCreate, SuggestionStatus
from finkernel.schemas.discovery import ConfirmProfileDraftRequest, ReviewProfileRequest
from finkernel.schemas.profile import MemoryKind
from finkernel.schemas.simulation import SimulatedTradeInput
from finkernel.services.advisory import AdvisoryService
from finkernel.services.control_plane import ControlPlaneService
from finkernel.services.profile_discovery import ProfileDiscoveryService
from finkernel.services.profiles import ProfileStore
from finkernel.services.simulation import SimulationService

LOCAL_MCP_ALLOWED_HOSTS = [
    "localhost",
    "localhost:8000",
    "127.0.0.1",
    "127.0.0.1:8000",
    "testserver",
]


def create_mcp_server(
    *,
    advisory_service: AdvisoryService,
    control_plane_service: ControlPlaneService,
    profile_discovery_service: ProfileDiscoveryService,
    simulation_service: SimulationService,
    profile_store: ProfileStore,
) -> FastMCP:
    mcp = FastMCP(
        name="FinKernel MCP",
        instructions=(
            "Use these tools to manage a paper-trading profile through FinKernel. "
            "When a user asks for investment advice, capital deployment, portfolio management, rebalancing, "
            "or risk review, first check profile onboarding status. If no active profile exists, start profile "
            "discovery before giving profile-scoped recommendations. If a profile exists, read the active profile, "
            "persona markdown, and risk summary before strategy or advisor actions. Preferred flow: onboarding "
            "status -> discovery if needed -> profile context -> strategy or simulation -> advisor suggestions -> "
            "approval or rejection -> linked workflow request tracking. Do not jump straight to generic web-style "
            "investment advice when FinKernel profile context is available."
        ),
        json_response=True,
        stateless_http=True,
        streamable_http_path="/",
        transport_security=TransportSecuritySettings(
            allowed_hosts=LOCAL_MCP_ALLOWED_HOSTS,
        ),
    )

    def profile(profile_id: str):
        return profile_store.get(profile_id)

    @mcp.tool(name="get_profile_onboarding_status")
    def get_profile_onboarding_status(owner_id: str | None = None) -> dict:
        return profile_store.get_onboarding_status(owner_id=owner_id).model_dump(mode="json")

    @mcp.tool(name="get_profile")
    def get_profile(profile_id: str, version: int | None = None) -> dict:
        return profile_discovery_service.get_profile(profile_id, version=version).model_dump(mode="json")

    @mcp.tool(name="get_profile_persona_markdown")
    def get_profile_persona_markdown(profile_id: str, version: int | None = None) -> dict:
        profile_record = profile_discovery_service.get_profile(profile_id, version=version)
        return {
            "profile_id": profile_record.profile_id,
            "version": profile_record.version,
            "persona_markdown": profile_record.persona_markdown,
        }

    @mcp.tool(name="get_profile_persona_sources")
    def get_profile_persona_sources(profile_id: str, version: int | None = None) -> dict:
        return profile_discovery_service.get_persona_source_packet(profile_id, version=version).model_dump(mode="json")

    @mcp.tool(name="save_profile_persona_markdown")
    def save_profile_persona_markdown(profile_id: str, persona_markdown: str, version: int | None = None) -> dict:
        profile_record = profile_discovery_service.save_persona_markdown(
            profile_id=profile_id,
            persona_markdown=persona_markdown,
            version=version,
        )
        return {"profile": profile_record.model_dump(mode="json")}

    @mcp.tool(name="list_profile_versions")
    def list_profile_versions(profile_id: str) -> dict:
        return {"items": [item.model_dump(mode="json") for item in profile_discovery_service.list_profile_versions(profile_id)]}

    @mcp.tool(name="start_profile_discovery")
    def start_profile_discovery(owner_id: str, preferred_profile_name: str | None = None) -> dict:
        return profile_discovery_service.start_discovery(owner_id=owner_id, preferred_profile_name=preferred_profile_name).model_dump(mode="json")

    @mcp.tool(name="get_next_profile_question")
    def get_next_profile_question(discovery_session_id: str) -> dict | None:
        question = profile_discovery_service.get_next_question(discovery_session_id)
        return question.model_dump(mode="json") if question is not None else None

    @mcp.tool(name="submit_profile_discovery_answer")
    def submit_profile_discovery_answer(discovery_session_id: str, answer: str, question_id: str | None = None) -> dict:
        return profile_discovery_service.submit_answer(
            session_id=discovery_session_id,
            answer_text=answer,
            question_id=question_id,
        ).model_dump(mode="json")

    @mcp.tool(name="generate_profile_draft")
    def generate_profile_draft(discovery_session_id: str) -> dict:
        return profile_discovery_service.generate_draft(discovery_session_id).model_dump(mode="json")

    @mcp.tool(name="confirm_profile_draft")
    def confirm_profile_draft(
        profile_draft_id: str,
        profile_id: str | None = None,
        allowed_accounts: list[str] | None = None,
        allowed_markets: list[str] | None = None,
        capital_allocation_pct: float | None = None,
        allowed_actions: list[str] | None = None,
        hitl_required_actions: list[str] | None = None,
        persona_markdown: str | None = None,
    ) -> dict:
        profile = profile_discovery_service.confirm_draft(
            draft_id=profile_draft_id,
            payload=ConfirmProfileDraftRequest(
                profile_id=profile_id,
                allowed_accounts=allowed_accounts,
                allowed_markets=allowed_markets,
                capital_allocation_pct=Decimal(str(capital_allocation_pct)) if capital_allocation_pct is not None else None,
                allowed_actions=allowed_actions,
                hitl_required_actions=hitl_required_actions,
                persona_markdown=persona_markdown,
            ),
        )
        return {"profile": profile.model_dump(mode="json")}

    @mcp.tool(name="review_profile")
    def review_profile(profile_id: str, trigger: str, notes: str | None = None) -> dict:
        return profile_discovery_service.start_review(
            profile_id=profile_id,
            payload=ReviewProfileRequest(trigger=trigger, notes=notes),
        ).model_dump(mode="json")

    @mcp.tool(name="append_profile_memory")
    def append_profile_memory(
        profile_id: str,
        memory_kind: str,
        theme: str,
        content_text: str,
        source_dimension: str | None = None,
        expires_at: str | None = None,
    ) -> dict:
        profile = profile_discovery_service.append_memory(
            profile_id=profile_id,
            memory_kind=MemoryKind(memory_kind),
            theme=theme,
            content_text=content_text,
            source_dimension=source_dimension,
            expires_at=datetime.fromisoformat(expires_at) if expires_at else None,
        )
        return {"profile": profile.model_dump(mode="json")}

    @mcp.tool(name="search_profile_memory")
    def search_profile_memory(
        profile_id: str,
        query: str,
        memory_kind: str | None = None,
        include_expired: bool = False,
    ) -> dict:
        return {
            "items": profile_discovery_service.search_memory(
                profile_id=profile_id,
                query=query,
                memory_kind=MemoryKind(memory_kind) if memory_kind else None,
                include_expired=include_expired,
            )
        }

    @mcp.tool(name="distill_profile_memory")
    def distill_profile_memory(profile_id: str) -> dict:
        return profile_discovery_service.distill_memory(profile_id=profile_id).model_dump(mode="json")

    @mcp.tool(name="list_profiles")
    def list_profiles() -> dict:
        profiles = profile_store.load_all()
        return {
            "profiles": [
                {
                    "profile_id": item.profile_id,
                    "owner_id": item.owner_id,
                    "version": item.version,
                    "status": item.status.value,
                    "display_name": item.display_name,
                    "mandate_summary": item.mandate_summary,
                    "risk_budget": item.risk_budget.value,
                    "allowed_symbols": item.allowed_symbols,
                    "allowed_actions": [action.value for action in item.allowed_actions],
                    "created_from": item.created_from,
                }
                for item in profiles.values()
            ]
        }

    @mcp.tool(name="create_strategy")
    def create_strategy(
        profile_id: str,
        name: str,
        mandate_summary: str,
        target_allocation: dict[str, float],
        rebalance_threshold_pct: float = 0.05,
        budget: float | None = None,
        active: bool = True,
    ) -> dict:
        result = advisory_service.create_strategy(
            profile=profile(profile_id),
            payload=StrategyCreate(
                name=name,
                mandate_summary=mandate_summary,
                budget=budget,
                target_allocation={symbol: Decimal(str(weight)) for symbol, weight in target_allocation.items()},
                rebalance_threshold_pct=Decimal(str(rebalance_threshold_pct)),
                active=active,
            ),
        )
        return result.model_dump(mode="json")

    @mcp.tool(name="create_strategy_from_text")
    def create_strategy_from_text(profile_id: str, text: str, auto_activate: bool = True) -> dict:
        result = advisory_service.create_strategy_from_text(
            profile=profile(profile_id),
            payload=StrategyFromTextCreate(text=text, auto_activate=auto_activate),
        )
        return result.model_dump(mode="json")

    @mcp.tool(name="list_strategies")
    def list_strategies(profile_id: str) -> dict:
        result = advisory_service.list_strategies(profile=profile(profile_id))
        return {"items": [item.model_dump(mode="json") for item in result]}

    @mcp.tool(name="run_advisor_once")
    def run_advisor_once(profile_id: str | None = None) -> dict:
        if profile_id is None:
            profile_store.ensure_active_profiles_exist()
        result = advisory_service.run_once(profile_id=profile_id)
        return result.model_dump(mode="json")

    @mcp.tool(name="list_suggestions")
    def list_suggestions(profile_id: str, status: str | None = None) -> dict:
        parsed_status = SuggestionStatus(status) if status else None
        result = advisory_service.list_suggestions(profile=profile(profile_id), status=parsed_status)
        return {"items": [item.model_dump(mode="json") for item in result]}

    @mcp.tool(name="get_suggestion")
    def get_suggestion(profile_id: str, suggestion_id: str) -> dict:
        result = advisory_service.get_suggestion(suggestion_id, profile=profile(profile_id))
        if result is None:
            raise ValueError(f"Suggestion {suggestion_id} was not found.")
        return result.model_dump(mode="json")

    @mcp.tool(name="approve_suggestion")
    def approve_suggestion(profile_id: str, suggestion_id: str) -> dict:
        result = advisory_service.approve_suggestion(suggestion_id, profile=profile(profile_id))
        return result.model_dump(mode="json")

    @mcp.tool(name="reject_suggestion")
    def reject_suggestion(profile_id: str, suggestion_id: str) -> dict:
        result = advisory_service.reject_suggestion(suggestion_id, profile=profile(profile_id))
        return result.model_dump(mode="json")

    @mcp.tool(name="get_portfolio_snapshot")
    def get_portfolio_snapshot(profile_id: str) -> dict:
        result = simulation_service.get_portfolio_snapshot(profile=profile(profile_id))
        return result.model_dump(mode="json")

    @mcp.tool(name="get_risk_summary")
    def get_risk_summary(profile_id: str) -> dict:
        result = simulation_service.get_risk_summary(profile=profile(profile_id))
        return result.model_dump(mode="json")

    @mcp.tool(name="simulate_trade")
    def simulate_trade(
        profile_id: str,
        account_id: str,
        symbol: str,
        side: str,
        quantity: float,
        limit_price: float,
        market: str = "us_equities",
    ) -> dict:
        result = simulation_service.simulate_trade(
            profile=profile(profile_id),
            trade_input=SimulatedTradeInput(
                account_id=account_id,
                symbol=symbol,
                side=side,
                quantity=Decimal(str(quantity)),
                limit_price=Decimal(str(limit_price)),
                market=market,
            ),
        )
        return result.model_dump(mode="json")

    @mcp.tool(name="list_requests")
    def list_requests(
        profile_id: str,
        state: str | None = None,
        symbol: str | None = None,
        account_id: str | None = None,
        created_from: str | None = None,
        created_to: str | None = None,
        limit: int = 50,
    ) -> dict:
        result = control_plane_service.list_requests(
            profile=profile(profile_id),
            state=state,
            symbol=symbol,
            account_id=account_id,
            created_from=datetime.fromisoformat(created_from) if created_from else None,
            created_to=datetime.fromisoformat(created_to) if created_to else None,
            limit=limit,
        )
        return result.model_dump(mode="json")

    @mcp.tool(name="get_request")
    def get_request(profile_id: str, request_id: str) -> dict:
        result = control_plane_service.get_request(request_id, profile=profile(profile_id))
        if result is None:
            raise ValueError(f"Workflow request {request_id} was not found.")
        return result.model_dump(mode="json")

    @mcp.tool(name="refresh_request")
    def refresh_request(profile_id: str, request_id: str) -> dict:
        result = control_plane_service.refresh_request(request_id, profile=profile(profile_id))
        return result.model_dump(mode="json")

    @mcp.tool(name="reconcile_request")
    def reconcile_request(profile_id: str, request_id: str) -> dict:
        result = control_plane_service.reconcile_request(request_id, profile=profile(profile_id))
        return result.model_dump(mode="json")

    @mcp.tool(name="cancel_request")
    def cancel_request(profile_id: str, request_id: str) -> dict:
        result = control_plane_service.cancel_request(request_id, profile=profile(profile_id))
        return result.model_dump(mode="json")

    return mcp

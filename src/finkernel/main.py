from __future__ import annotations

from contextlib import asynccontextmanager
import asyncio
import logging

from fastapi import FastAPI

from finkernel.audit.service import AuditService
from finkernel.config import Settings, get_settings
from finkernel.connectors.brokers.alpaca import AlpacaBrokerClient
from finkernel.connectors.brokers.registry import BrokerRegistry
from finkernel.connectors.channels.discord import DiscordHITLClient
from finkernel.policy.engine import PolicyEngine
from finkernel.services.advisory import AdvisoryService
from finkernel.services.authorization import ProfileAuthorizer
from finkernel.services.control_plane import ControlPlaneService
from finkernel.services.interfaces import BrokerClient, ConfirmationChannel
from finkernel.services.market_data import MarketDataService
from finkernel.services.observability import ObservabilityService
from finkernel.services.profile_discovery import ProfileDiscoveryService
from finkernel.services.profiles import ProfileStore
from finkernel.services.simulation import SimulationService
from finkernel.storage.database import build_session_factory, check_database, init_database
from finkernel.transport.http.routes import advisory_router, control_plane_router, health_router, profiles_router, simulation_router, trade_requests_router
from finkernel.transport.mcp.server import create_mcp_server
from finkernel.workflow.service import TradeWorkflowService

logger = logging.getLogger(__name__)


class NullConfirmationChannel:
    def send_confirmation(self, workflow_request) -> None:
        raise RuntimeError("Discord is not configured. Provide DISCORD_BOT_TOKEN and DISCORD_CHANNEL_ID.")

    def send_status_update(self, workflow_request, message: str) -> None:
        return None


def configure_logging() -> None:
    root_logger = logging.getLogger()
    if root_logger.handlers:
        root_logger.setLevel(logging.INFO)
        return
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )


def build_runtime(
    settings: Settings,
    *,
    broker_client: BrokerClient | None = None,
    confirmation_channel: ConfirmationChannel | None = None,
) -> dict:
    session_factory = build_session_factory(settings)
    policy_engine = PolicyEngine(settings)
    audit_service = AuditService()
    observability_service = ObservabilityService()
    profile_store = ProfileStore(settings, session_factory=session_factory)
    profile_authorizer = ProfileAuthorizer(audit_service)
    profile_discovery_service = ProfileDiscoveryService(
        settings=settings,
        session_factory=session_factory,
        profile_store=profile_store,
    )

    workflow_service_holder: dict[str, TradeWorkflowService] = {}

    def action_handler(actor_id: str, action: str, request_id: str, token: str) -> str:
        return workflow_service_holder["service"].handle_confirmation_action(actor_id, action, request_id, token)

    discord_client = None
    if confirmation_channel is None and settings.discord_bot_token and settings.discord_channel_id:
        discord_client = DiscordHITLClient(settings, action_handler=action_handler)
        confirmation_channel = discord_client
    confirmation_channel = confirmation_channel or NullConfirmationChannel()
    broker_client = broker_client or AlpacaBrokerClient(settings)
    broker_registry = BrokerRegistry()
    broker_registry.register(broker_client, default=True)
    market_data_service = MarketDataService(broker_client)

    workflow_service = TradeWorkflowService(
        settings=settings,
        session_factory=session_factory,
        policy_engine=policy_engine,
        broker_client=broker_client,
        confirmation_channel=confirmation_channel,
        observability_service=observability_service,
        audit_service=audit_service,
        profile_authorizer=profile_authorizer,
    )
    workflow_service_holder["service"] = workflow_service
    control_plane_service = ControlPlaneService(
        session_factory=session_factory,
        broker_client=broker_client,
        audit_service=audit_service,
        observability_service=observability_service,
        profile_authorizer=profile_authorizer,
    )
    simulation_service = SimulationService(
        session_factory=session_factory,
        broker_client=broker_client,
        profile_authorizer=profile_authorizer,
    )
    advisory_service = AdvisoryService(
        session_factory=session_factory,
        profile_store=profile_store,
        workflow_service=workflow_service,
        simulation_service=simulation_service,
        market_data_service=market_data_service,
        profile_authorizer=profile_authorizer,
    )
    mcp_server = create_mcp_server(
        advisory_service=advisory_service,
        control_plane_service=control_plane_service,
        profile_discovery_service=profile_discovery_service,
        simulation_service=simulation_service,
        profile_store=profile_store,
    )
    return {
        "settings": settings,
        "session_factory": session_factory,
        "audit_service": audit_service,
        "observability_service": observability_service,
        "profile_store": profile_store,
        "profile_discovery_service": profile_discovery_service,
        "workflow_service": workflow_service,
        "control_plane_service": control_plane_service,
        "simulation_service": simulation_service,
        "advisory_service": advisory_service,
        "mcp_server": mcp_server,
        "discord_client": discord_client,
        "broker_registry": broker_registry,
    }


def create_app(
    settings: Settings | None = None,
    *,
    broker_client: BrokerClient | None = None,
    confirmation_channel: ConfirmationChannel | None = None,
) -> FastAPI:
    configure_logging()
    settings = settings or get_settings()
    runtime = build_runtime(settings, broker_client=broker_client, confirmation_channel=confirmation_channel)
    session_factory = runtime["session_factory"]
    profile_store = runtime["profile_store"]
    control_plane_service = runtime["control_plane_service"]
    advisory_service = runtime["advisory_service"]
    mcp_server = runtime["mcp_server"]
    discord_client = runtime["discord_client"]

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        stop_event = asyncio.Event()

        async def periodic_reconciliation_loop() -> None:
            while not stop_event.is_set():
                await asyncio.sleep(settings.reconciliation_interval_seconds)
                try:
                    results = await asyncio.to_thread(control_plane_service.refresh_active_requests)
                    if results:
                        logger.info("active_refresh periodic_count=%s", len(results))
                except Exception:
                    logger.exception("active_refresh periodic_failed")

        async def periodic_advisor_loop() -> None:
            while not stop_event.is_set():
                await asyncio.sleep(settings.advisor_loop_interval_seconds)
                try:
                    result = await asyncio.to_thread(advisory_service.run_once)
                    if result.created_suggestions:
                        logger.info(
                            "advisor_loop created_suggestions=%s total_strategies=%s",
                            result.created_suggestions,
                            result.total_strategies,
                        )
                except Exception:
                    logger.exception("advisor_loop periodic_failed")

        async with mcp_server.session_manager.run():
            if discord_client is not None and discord_client.enabled:
                discord_client.start_background()
            await asyncio.to_thread(init_database, session_factory, settings)
            await asyncio.to_thread(profile_store.bootstrap_from_seed)
            app.state.services["database_ok"] = await asyncio.to_thread(check_database, session_factory)
            startup_results = await asyncio.to_thread(control_plane_service.reconcile_inflight_requests)
            if startup_results:
                logger.info("startup_reconciliation startup_count=%s", len(startup_results))
            reconciliation_task = asyncio.create_task(periodic_reconciliation_loop())
            advisor_task = asyncio.create_task(periodic_advisor_loop())
            yield
            stop_event.set()
            reconciliation_task.cancel()
            advisor_task.cancel()
            try:
                await reconciliation_task
            except BaseException:
                pass
            try:
                await advisor_task
            except BaseException:
                pass
            if discord_client is not None and discord_client.enabled:
                discord_client.stop_background()

    app = FastAPI(title=settings.app_name, lifespan=lifespan)
    app.state.workflow_service = runtime["workflow_service"]
    app.state.control_plane_service = runtime["control_plane_service"]
    app.state.simulation_service = runtime["simulation_service"]
    app.state.advisory_service = runtime["advisory_service"]
    app.state.profile_store = runtime["profile_store"]
    app.state.profile_discovery_service = runtime["profile_discovery_service"]
    app.state.broker_registry = runtime["broker_registry"]
    app.state.mcp_server = mcp_server
    app.state.services = {
        "settings": settings,
        "database_ok": False,
        "discord_enabled": bool(settings.discord_bot_token and settings.discord_channel_id),
        "alpaca_configured": bool(settings.alpaca_api_key and settings.alpaca_secret_key),
        "discord_client": discord_client,
        "observability": runtime["observability_service"],
        "broker_registry": runtime["broker_registry"].list_slugs(),
        "mcp_enabled": True,
        "mcp_endpoint": f"{settings.api_prefix.rstrip('/')}/mcp",
    }
    app.include_router(health_router, prefix=settings.api_prefix)
    app.include_router(profiles_router, prefix=settings.api_prefix)
    app.include_router(trade_requests_router, prefix=settings.api_prefix)
    app.include_router(control_plane_router, prefix=settings.api_prefix)
    app.include_router(simulation_router, prefix=settings.api_prefix)
    app.include_router(advisory_router, prefix=settings.api_prefix)
    app.mount(f"{settings.api_prefix.rstrip('/')}/mcp", mcp_server.streamable_http_app())
    return app


app = create_app()

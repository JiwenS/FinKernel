from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
import logging

from fastapi import FastAPI

from finkernel.config import Settings, get_settings
from finkernel.services.file_profiles import FileProfileStore
from finkernel.services.profile_discovery import ProfileDiscoveryService
from finkernel.services.profiles import ProfileStore
from finkernel.storage.database import build_session_factory, check_database, init_database
from finkernel.transport.http.routes import health_router, profiles_router
from finkernel.transport.mcp.server import create_mcp_server

logger = logging.getLogger(__name__)


def configure_logging() -> None:
    root_logger = logging.getLogger()
    if root_logger.handlers:
        root_logger.setLevel(logging.INFO)
        return
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")


def build_runtime(settings: Settings) -> dict:
    session_factory = None
    if settings.storage_backend == "database":
        session_factory = build_session_factory(settings)
        profile_store = ProfileStore(settings, session_factory=session_factory)
    else:
        profile_store = FileProfileStore(settings)
    profile_discovery_service = ProfileDiscoveryService(
        settings=settings,
        session_factory=session_factory,
        profile_store=profile_store,
    )
    mcp_server = create_mcp_server(
        profile_discovery_service=profile_discovery_service,
        profile_store=profile_store,
    )
    return {
        "settings": settings,
        "session_factory": session_factory,
        "profile_store": profile_store,
        "profile_discovery_service": profile_discovery_service,
        "mcp_server": mcp_server,
    }


def create_app(settings: Settings | None = None) -> FastAPI:
    configure_logging()
    settings = settings or get_settings()
    runtime = build_runtime(settings)
    session_factory = runtime["session_factory"]
    profile_store = runtime["profile_store"]
    mcp_server = runtime["mcp_server"]

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        async with mcp_server.session_manager.run():
            if settings.storage_backend == "database":
                await asyncio.to_thread(init_database, session_factory, settings)
            await asyncio.to_thread(profile_store.bootstrap_from_seed)
            app.state.services["storage_ok"] = await asyncio.to_thread(
                check_database,
                session_factory,
            ) if settings.storage_backend == "database" else await asyncio.to_thread(profile_store.check)
            app.state.services["database_ok"] = app.state.services["storage_ok"] if settings.storage_backend == "database" else None
            yield

    app = FastAPI(title=settings.app_name, lifespan=lifespan)
    app.state.profile_store = runtime["profile_store"]
    app.state.profile_discovery_service = runtime["profile_discovery_service"]
    app.state.mcp_server = mcp_server
    app.state.services = {
        "settings": settings,
        "storage_backend": settings.storage_backend,
        "storage_ok": False,
        "database_ok": False,
        "mcp_enabled": True,
        "mcp_endpoint": f"{settings.api_prefix.rstrip('/')}/mcp",
    }
    app.include_router(health_router, prefix=settings.api_prefix)
    app.include_router(profiles_router, prefix=settings.api_prefix)
    app.mount(f"{settings.api_prefix.rstrip('/')}/mcp", mcp_server.streamable_http_app())
    return app


app = create_app()

from __future__ import annotations

import argparse
import logging

from finkernel.config import get_settings
from finkernel.services.file_profiles import FileProfileStore
from finkernel.services.profile_discovery import ProfileDiscoveryService
from finkernel.services.profiles import ProfileStore
from finkernel.storage.database import build_session_factory, init_database
from finkernel.transport.mcp.server import create_mcp_server


def configure_logging() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")


def bootstrap_runtime() -> dict:
    settings = get_settings()
    session_factory = None
    if settings.storage_backend == "database":
        session_factory = build_session_factory(settings)
        profile_store = ProfileStore(settings, session_factory=session_factory)
        init_database(session_factory, settings)
    else:
        profile_store = FileProfileStore(settings)
    profile_discovery_service = ProfileDiscoveryService(
        settings=settings,
        session_factory=session_factory,
        profile_store=profile_store,
    )
    profile_store.bootstrap_from_seed()
    return {
        "settings": settings,
        "profile_store": profile_store,
        "mcp_server": create_mcp_server(
            profile_discovery_service=profile_discovery_service,
            profile_store=profile_store,
        ),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Run FinKernel MCP over stdio.")
    parser.add_argument("--check", action="store_true", help="Initialize storage and exit without starting stdio.")
    args = parser.parse_args()

    configure_logging()
    runtime = bootstrap_runtime()
    if args.check:
        runtime["profile_store"].check() if runtime["settings"].storage_backend == "file" else None
        print(f"FinKernel MCP stdio runtime ready with {runtime['settings'].storage_backend} storage.")
        return
    runtime["mcp_server"].run("stdio")


if __name__ == "__main__":
    main()

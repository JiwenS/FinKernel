from __future__ import annotations

from finkernel.config import get_settings
from finkernel.main import build_runtime, configure_logging
from finkernel.storage.database import init_database


def main() -> None:
    configure_logging()
    settings = get_settings()
    runtime = build_runtime(settings)
    session_factory = runtime["session_factory"]
    profile_store = runtime["profile_store"]
    discord_client = runtime["discord_client"]
    mcp_server = runtime["mcp_server"]

    init_database(session_factory, settings)
    profile_store.bootstrap_from_seed()

    try:
        if discord_client is not None and discord_client.enabled:
            discord_client.start_background()
        mcp_server.run(transport="stdio")
    finally:
        if discord_client is not None and discord_client.enabled:
            discord_client.stop_background()


if __name__ == "__main__":
    main()

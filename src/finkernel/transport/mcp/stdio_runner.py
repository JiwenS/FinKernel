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
    mcp_server = runtime["mcp_server"]

    init_database(session_factory, settings)
    profile_store.bootstrap_from_seed()
    mcp_server.run(transport="stdio")


if __name__ == "__main__":
    main()

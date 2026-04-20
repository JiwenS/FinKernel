from __future__ import annotations

from fastapi import APIRouter, Request

router = APIRouter(tags=["health"])


@router.get("/health")
def health(request: Request) -> dict:
    services = request.app.state.services
    return {
        "status": "ok",
        "database": services["database_ok"],
        "redis_configured": bool(services["settings"].redis_url),
        "discord_enabled": services["discord_enabled"],
        "alpaca_configured": services["alpaca_configured"],
        "mcp_enabled": services["mcp_enabled"],
        "mcp_endpoint": services["mcp_endpoint"],
    }

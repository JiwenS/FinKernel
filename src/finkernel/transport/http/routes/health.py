from __future__ import annotations

from fastapi import APIRouter, Request

router = APIRouter(tags=["health"])


@router.get("/health")
def health(request: Request) -> dict:
    services = request.app.state.services
    return {
        "status": "ok",
        "storage_backend": services["storage_backend"],
        "storage": services["storage_ok"],
        "database": services["database_ok"],
        "mcp_enabled": services["mcp_enabled"],
        "mcp_endpoint": services["mcp_endpoint"],
        "profile_store_path": services["settings"].profile_store_path,
        "profile_data_dir": services["settings"].profile_data_dir,
    }

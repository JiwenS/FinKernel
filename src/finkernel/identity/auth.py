from __future__ import annotations

from fastapi import Header, HTTPException, status


def require_request_source(x_request_source: str | None = Header(default=None)) -> str:
    if not x_request_source:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="x-request-source header is required to preserve audit context.",
        )
    return x_request_source


def require_profile_id(x_profile_id: str | None = Header(default=None)) -> str:
    if not x_profile_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="x-profile-id header is required to bind a request to a declarative persona profile.",
        )
    return x_profile_id

from __future__ import annotations

from fastapi import HTTPException, Request, status

from finkernel.services.profile_discovery import (
    DiscoveryNotReadyError,
    DraftConfirmationRequiredError,
    InvalidDiscoveryInterpretationError,
    ProfileDiscoveryService,
)
from finkernel.services.profiles import InactiveProfileError, ProfileOnboardingRequiredError, ProfileStore


def get_profile_store(request: Request) -> ProfileStore:
    return request.app.state.profile_store


def get_profile_discovery_service(request: Request) -> ProfileDiscoveryService:
    return request.app.state.profile_discovery_service


def raise_for_profile_error(exc: Exception) -> None:
    if isinstance(exc, ProfileOnboardingRequiredError | InactiveProfileError):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=exc.to_detail()) from exc
    if isinstance(exc, DiscoveryNotReadyError):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail={"reason_code": "DISCOVERY_NOT_READY", "message": str(exc)}) from exc
    if isinstance(exc, DraftConfirmationRequiredError):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail={"reason_code": "DRAFT_CONFIRMATION_REQUIRED", "message": str(exc)}) from exc
    if isinstance(exc, InvalidDiscoveryInterpretationError):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail={"reason_code": "INVALID_DISCOVERY_INTERPRETATION", "message": str(exc)},
        ) from exc
    if isinstance(exc, KeyError):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    raise exc

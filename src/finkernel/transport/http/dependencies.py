from __future__ import annotations

from fastapi import HTTPException, Request, status

from finkernel.schemas.profile import PersonaProfile
from finkernel.services.advisory import AdvisoryService
from finkernel.services.control_plane import ControlPlaneService
from finkernel.services.profile_discovery import DiscoveryNotReadyError, ProfileDiscoveryService
from finkernel.services.profiles import InactiveProfileError, ProfileOnboardingRequiredError, ProfileStore
from finkernel.services.simulation import SimulationService
from finkernel.workflow.service import TradeWorkflowService


def get_workflow_service(request: Request) -> TradeWorkflowService:
    return request.app.state.workflow_service


def get_control_plane_service(request: Request) -> ControlPlaneService:
    return request.app.state.control_plane_service


def get_simulation_service(request: Request) -> SimulationService:
    return request.app.state.simulation_service


def get_advisory_service(request: Request) -> AdvisoryService:
    return request.app.state.advisory_service


def get_profile_store(request: Request) -> ProfileStore:
    return request.app.state.profile_store


def get_profile_discovery_service(request: Request) -> ProfileDiscoveryService:
    return request.app.state.profile_discovery_service


def resolve_profile(request: Request, profile_id: str) -> PersonaProfile:
    store = get_profile_store(request)
    return store.get(profile_id)


def ensure_active_profiles_exist(request: Request, owner_id: str | None = None) -> None:
    store = get_profile_store(request)
    store.ensure_active_profiles_exist(owner_id=owner_id)


def raise_for_profile_error(exc: Exception) -> None:
    if isinstance(exc, ProfileOnboardingRequiredError | InactiveProfileError):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=exc.to_detail()) from exc
    if isinstance(exc, DiscoveryNotReadyError):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail={"reason_code": "DISCOVERY_NOT_READY", "message": str(exc)}) from exc
    if isinstance(exc, KeyError):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    raise exc

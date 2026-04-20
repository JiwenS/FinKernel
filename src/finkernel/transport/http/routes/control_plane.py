from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, Request

from finkernel.identity.auth import require_profile_id
from finkernel.schemas.control_plane import AuditEventListResponse, ReconciliationResult, WorkflowRequestListResponse, WorkflowRequestSummary
from finkernel.services.authorization import AuthorizationError
from finkernel.transport.http.dependencies import get_control_plane_service, raise_for_profile_error, resolve_profile
from finkernel.services.control_plane import ControlPlaneService

router = APIRouter(tags=["control-plane"])


@router.get("/requests", response_model=WorkflowRequestListResponse)
def list_requests(
    request: Request,
    state: str | None = Query(default=None),
    symbol: str | None = Query(default=None),
    account_id: str | None = Query(default=None),
    created_from: datetime | None = Query(default=None),
    created_to: datetime | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    profile_id: str = Depends(require_profile_id),
    control_plane: ControlPlaneService = Depends(get_control_plane_service),
) -> WorkflowRequestListResponse:
    try:
        profile = resolve_profile(request, profile_id)
        return control_plane.list_requests(
            profile=profile,
            state=state,
            symbol=symbol,
            account_id=account_id,
            created_from=created_from,
            created_to=created_to,
            limit=limit,
        )
    except (KeyError, LookupError) as exc:
        raise_for_profile_error(exc)
    except AuthorizationError as exc:
        raise HTTPException(status_code=403, detail={"reason_code": exc.reason_code, "message": str(exc)}) from exc


@router.get("/requests/{request_id}", response_model=WorkflowRequestSummary)
def get_request(
    request: Request,
    request_id: str,
    profile_id: str = Depends(require_profile_id),
    control_plane: ControlPlaneService = Depends(get_control_plane_service),
) -> WorkflowRequestSummary:
    try:
        profile = resolve_profile(request, profile_id)
        item = control_plane.get_request(request_id, profile=profile)
        if item is None:
            raise HTTPException(status_code=404, detail="Workflow request not found.")
        return item
    except (KeyError, LookupError) as exc:
        raise_for_profile_error(exc)
    except AuthorizationError as exc:
        raise HTTPException(status_code=403, detail={"reason_code": exc.reason_code, "message": str(exc)}) from exc


@router.get("/requests/{request_id}/audit", response_model=AuditEventListResponse)
def get_request_audit(
    request: Request,
    request_id: str,
    limit: int = Query(default=100, ge=1, le=500),
    profile_id: str = Depends(require_profile_id),
    control_plane: ControlPlaneService = Depends(get_control_plane_service),
) -> AuditEventListResponse:
    try:
        profile = resolve_profile(request, profile_id)
        return control_plane.list_audit_events(profile=profile, workflow_request_id=request_id, limit=limit)
    except (KeyError, LookupError) as exc:
        raise_for_profile_error(exc)
    except AuthorizationError as exc:
        raise HTTPException(status_code=403, detail={"reason_code": exc.reason_code, "message": str(exc)}) from exc


@router.post("/requests/{request_id}/reconcile", response_model=ReconciliationResult)
def reconcile_request(
    request: Request,
    request_id: str,
    profile_id: str = Depends(require_profile_id),
    control_plane: ControlPlaneService = Depends(get_control_plane_service),
) -> ReconciliationResult:
    try:
        profile = resolve_profile(request, profile_id)
        return control_plane.reconcile_request(request_id, profile=profile)
    except (KeyError, LookupError) as exc:
        raise_for_profile_error(exc)
    except AuthorizationError as exc:
        raise HTTPException(status_code=403, detail={"reason_code": exc.reason_code, "message": str(exc)}) from exc
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/requests/{request_id}/refresh", response_model=ReconciliationResult)
def refresh_request(
    request: Request,
    request_id: str,
    profile_id: str = Depends(require_profile_id),
    control_plane: ControlPlaneService = Depends(get_control_plane_service),
) -> ReconciliationResult:
    try:
        profile = resolve_profile(request, profile_id)
        return control_plane.refresh_request(request_id, profile=profile)
    except (KeyError, LookupError) as exc:
        raise_for_profile_error(exc)
    except AuthorizationError as exc:
        raise HTTPException(status_code=403, detail={"reason_code": exc.reason_code, "message": str(exc)}) from exc
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/requests/{request_id}/cancel", response_model=ReconciliationResult)
def cancel_request(
    request: Request,
    request_id: str,
    profile_id: str = Depends(require_profile_id),
    control_plane: ControlPlaneService = Depends(get_control_plane_service),
) -> ReconciliationResult:
    try:
        profile = resolve_profile(request, profile_id)
        return control_plane.cancel_request(request_id, profile=profile)
    except (KeyError, LookupError) as exc:
        raise_for_profile_error(exc)
    except AuthorizationError as exc:
        raise HTTPException(status_code=403, detail={"reason_code": exc.reason_code, "message": str(exc)}) from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/audit-events", response_model=AuditEventListResponse)
def list_audit_events(
    request: Request,
    workflow_request_id: str | None = Query(default=None),
    event_type: str | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=500),
    profile_id: str = Depends(require_profile_id),
    control_plane: ControlPlaneService = Depends(get_control_plane_service),
) -> AuditEventListResponse:
    try:
        profile = resolve_profile(request, profile_id)
        return control_plane.list_audit_events(profile=profile, workflow_request_id=workflow_request_id, event_type=event_type, limit=limit)
    except (KeyError, LookupError) as exc:
        raise_for_profile_error(exc)
    except AuthorizationError as exc:
        raise HTTPException(status_code=403, detail={"reason_code": exc.reason_code, "message": str(exc)}) from exc

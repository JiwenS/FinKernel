from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Response, status

from fastapi import Request

from finkernel.identity.auth import require_profile_id, require_request_source
from finkernel.services.authorization import AuthorizationError
from finkernel.transport.http.dependencies import get_control_plane_service, get_workflow_service, raise_for_profile_error, resolve_profile
from finkernel.schemas.trade import TradeRequestCreate, TradeRequestResponse
from finkernel.services.control_plane import ControlPlaneService
from finkernel.workflow.service import TradeWorkflowService

router = APIRouter(prefix="/trade-requests", tags=["trade-requests"])


@router.post("", response_model=TradeRequestResponse, status_code=status.HTTP_202_ACCEPTED)
def create_trade_request(
    request: Request,
    payload: TradeRequestCreate,
    response: Response,
    request_source: str = Depends(require_request_source),
    profile_id: str = Depends(require_profile_id),
    workflow_service: TradeWorkflowService = Depends(get_workflow_service),
) -> TradeRequestResponse:
    response.headers["x-request-source"] = request_source
    try:
        profile = resolve_profile(request, profile_id)
        return workflow_service.submit_trade_request(payload, request_source=request_source, profile=profile)
    except (KeyError, LookupError) as exc:
        raise_for_profile_error(exc)
    except AuthorizationError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail={"reason_code": exc.reason_code, "message": str(exc)}) from exc


@router.get("/{request_id}", response_model=TradeRequestResponse)
def get_trade_request(
    request: Request,
    request_id: str,
    profile_id: str = Depends(require_profile_id),
    control_plane: ControlPlaneService = Depends(get_control_plane_service),
) -> TradeRequestResponse:
    try:
        profile = resolve_profile(request, profile_id)
        record = control_plane.get_request(request_id, profile=profile)
        if record is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Trade request not found.")
        return record
    except (KeyError, LookupError) as exc:
        raise_for_profile_error(exc)
    except AuthorizationError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail={"reason_code": exc.reason_code, "message": str(exc)}) from exc

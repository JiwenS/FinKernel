from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status

from finkernel.identity.auth import require_profile_id
from finkernel.schemas.advisory import (
    AdvisorRunResponse,
    StrategyCreate,
    StrategyFromTextCreate,
    StrategyFromTextResponse,
    StrategyResponse,
    SuggestionResponse,
    SuggestionStatus,
)
from finkernel.services.advisory import AdvisoryService
from finkernel.services.authorization import AuthorizationError
from finkernel.transport.http.dependencies import ensure_active_profiles_exist, get_advisory_service, raise_for_profile_error, resolve_profile

router = APIRouter(tags=["advisory"])


@router.get("/strategies", response_model=list[StrategyResponse])
def list_strategies(
    request: Request,
    profile_id: str = Depends(require_profile_id),
    advisory_service: AdvisoryService = Depends(get_advisory_service),
) -> list[StrategyResponse]:
    try:
        profile = resolve_profile(request, profile_id)
        return advisory_service.list_strategies(profile=profile)
    except (KeyError, LookupError) as exc:
        raise_for_profile_error(exc)
    except AuthorizationError as exc:
        raise HTTPException(status_code=403, detail={"reason_code": exc.reason_code, "message": str(exc)}) from exc


@router.post("/strategies", response_model=StrategyResponse, status_code=status.HTTP_201_CREATED)
def create_strategy(
    request: Request,
    payload: StrategyCreate,
    profile_id: str = Depends(require_profile_id),
    advisory_service: AdvisoryService = Depends(get_advisory_service),
) -> StrategyResponse:
    try:
        profile = resolve_profile(request, profile_id)
        return advisory_service.create_strategy(profile=profile, payload=payload)
    except (KeyError, LookupError) as exc:
        raise_for_profile_error(exc)
    except AuthorizationError as exc:
        raise HTTPException(status_code=403, detail={"reason_code": exc.reason_code, "message": str(exc)}) from exc


@router.post("/strategies/from-text", response_model=StrategyFromTextResponse, status_code=status.HTTP_201_CREATED)
def create_strategy_from_text(
    request: Request,
    payload: StrategyFromTextCreate,
    profile_id: str = Depends(require_profile_id),
    advisory_service: AdvisoryService = Depends(get_advisory_service),
) -> StrategyFromTextResponse:
    try:
        profile = resolve_profile(request, profile_id)
        return advisory_service.create_strategy_from_text(profile=profile, payload=payload)
    except (KeyError, LookupError) as exc:
        raise_for_profile_error(exc)
    except AuthorizationError as exc:
        raise HTTPException(status_code=403, detail={"reason_code": exc.reason_code, "message": str(exc)}) from exc


@router.get("/strategies/{strategy_id}", response_model=StrategyResponse)
def get_strategy(
    request: Request,
    strategy_id: str,
    profile_id: str = Depends(require_profile_id),
    advisory_service: AdvisoryService = Depends(get_advisory_service),
) -> StrategyResponse:
    try:
        profile = resolve_profile(request, profile_id)
        item = advisory_service.get_strategy(strategy_id, profile=profile)
        if item is None:
            raise HTTPException(status_code=404, detail="Strategy not found.")
        return item
    except (KeyError, LookupError) as exc:
        raise_for_profile_error(exc)
    except AuthorizationError as exc:
        raise HTTPException(status_code=403, detail={"reason_code": exc.reason_code, "message": str(exc)}) from exc


@router.get("/suggestions", response_model=list[SuggestionResponse])
def list_suggestions(
    request: Request,
    status_filter: SuggestionStatus | None = Query(default=None, alias="status"),
    profile_id: str = Depends(require_profile_id),
    advisory_service: AdvisoryService = Depends(get_advisory_service),
) -> list[SuggestionResponse]:
    try:
        profile = resolve_profile(request, profile_id)
        return advisory_service.list_suggestions(profile=profile, status=status_filter)
    except (KeyError, LookupError) as exc:
        raise_for_profile_error(exc)
    except AuthorizationError as exc:
        raise HTTPException(status_code=403, detail={"reason_code": exc.reason_code, "message": str(exc)}) from exc


@router.get("/suggestions/{suggestion_id}", response_model=SuggestionResponse)
def get_suggestion(
    request: Request,
    suggestion_id: str,
    profile_id: str = Depends(require_profile_id),
    advisory_service: AdvisoryService = Depends(get_advisory_service),
) -> SuggestionResponse:
    try:
        profile = resolve_profile(request, profile_id)
        item = advisory_service.get_suggestion(suggestion_id, profile=profile)
        if item is None:
            raise HTTPException(status_code=404, detail="Suggestion not found.")
        return item
    except (KeyError, LookupError) as exc:
        raise_for_profile_error(exc)
    except AuthorizationError as exc:
        raise HTTPException(status_code=403, detail={"reason_code": exc.reason_code, "message": str(exc)}) from exc


@router.post("/suggestions/{suggestion_id}/approve", response_model=SuggestionResponse)
def approve_suggestion(
    request: Request,
    suggestion_id: str,
    profile_id: str = Depends(require_profile_id),
    advisory_service: AdvisoryService = Depends(get_advisory_service),
) -> SuggestionResponse:
    try:
        profile = resolve_profile(request, profile_id)
        return advisory_service.approve_suggestion(suggestion_id, profile=profile)
    except (KeyError, LookupError) as exc:
        raise_for_profile_error(exc)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except AuthorizationError as exc:
        raise HTTPException(status_code=403, detail={"reason_code": exc.reason_code, "message": str(exc)}) from exc


@router.post("/suggestions/{suggestion_id}/reject", response_model=SuggestionResponse)
def reject_suggestion(
    request: Request,
    suggestion_id: str,
    profile_id: str = Depends(require_profile_id),
    advisory_service: AdvisoryService = Depends(get_advisory_service),
) -> SuggestionResponse:
    try:
        profile = resolve_profile(request, profile_id)
        return advisory_service.reject_suggestion(suggestion_id, profile=profile)
    except (KeyError, LookupError) as exc:
        raise_for_profile_error(exc)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except AuthorizationError as exc:
        raise HTTPException(status_code=403, detail={"reason_code": exc.reason_code, "message": str(exc)}) from exc


@router.post("/advisor/run-once", response_model=AdvisorRunResponse)
def run_advisor_once(
    request: Request,
    profile_id: str | None = Query(default=None),
    advisory_service: AdvisoryService = Depends(get_advisory_service),
) -> AdvisorRunResponse:
    try:
        if profile_id:
            resolve_profile(request, profile_id)
        else:
            ensure_active_profiles_exist(request)
        return advisory_service.run_once(profile_id=profile_id)
    except (KeyError, LookupError) as exc:
        raise_for_profile_error(exc)

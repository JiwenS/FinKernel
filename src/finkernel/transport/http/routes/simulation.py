from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request

from finkernel.identity.auth import require_profile_id
from finkernel.schemas.simulation import AlertFactList, CandidateTradeAction, PortfolioSnapshot, RiskSummary, SimulatedTradeInput, TradeSimulationResult
from finkernel.services.authorization import AuthorizationError
from finkernel.services.simulation import SimulationService
from finkernel.transport.http.dependencies import get_simulation_service, raise_for_profile_error, resolve_profile

router = APIRouter(tags=["simulation"])


@router.get("/portfolio/snapshot", response_model=PortfolioSnapshot)
def get_portfolio_snapshot(
    request: Request,
    profile_id: str = Depends(require_profile_id),
    simulation_service: SimulationService = Depends(get_simulation_service),
) -> PortfolioSnapshot:
    try:
        profile = resolve_profile(request, profile_id)
        return simulation_service.get_portfolio_snapshot(profile=profile)
    except (KeyError, LookupError) as exc:
        raise_for_profile_error(exc)
    except AuthorizationError as exc:
        raise HTTPException(status_code=403, detail={"reason_code": exc.reason_code, "message": str(exc)}) from exc


@router.get("/portfolio/risk-summary", response_model=RiskSummary)
def get_risk_summary(
    request: Request,
    profile_id: str = Depends(require_profile_id),
    simulation_service: SimulationService = Depends(get_simulation_service),
) -> RiskSummary:
    try:
        profile = resolve_profile(request, profile_id)
        return simulation_service.get_risk_summary(profile=profile)
    except (KeyError, LookupError) as exc:
        raise_for_profile_error(exc)
    except AuthorizationError as exc:
        raise HTTPException(status_code=403, detail={"reason_code": exc.reason_code, "message": str(exc)}) from exc


@router.post("/simulations/trade", response_model=TradeSimulationResult)
def simulate_trade(
    request: Request,
    payload: SimulatedTradeInput,
    profile_id: str = Depends(require_profile_id),
    simulation_service: SimulationService = Depends(get_simulation_service),
) -> TradeSimulationResult:
    try:
        profile = resolve_profile(request, profile_id)
        return simulation_service.simulate_trade(profile=profile, trade_input=payload)
    except (KeyError, LookupError) as exc:
        raise_for_profile_error(exc)
    except AuthorizationError as exc:
        raise HTTPException(status_code=403, detail={"reason_code": exc.reason_code, "message": str(exc)}) from exc


@router.post("/candidate-actions/trade", response_model=CandidateTradeAction)
def build_candidate_trade_action(
    request: Request,
    payload: SimulatedTradeInput,
    profile_id: str = Depends(require_profile_id),
    simulation_service: SimulationService = Depends(get_simulation_service),
) -> CandidateTradeAction:
    try:
        profile = resolve_profile(request, profile_id)
        return simulation_service.build_candidate_trade_action(profile=profile, trade_input=payload)
    except (KeyError, LookupError) as exc:
        raise_for_profile_error(exc)
    except AuthorizationError as exc:
        raise HTTPException(status_code=403, detail={"reason_code": exc.reason_code, "message": str(exc)}) from exc


@router.get("/alerts", response_model=AlertFactList)
def get_alerts(
    request: Request,
    profile_id: str = Depends(require_profile_id),
    simulation_service: SimulationService = Depends(get_simulation_service),
) -> AlertFactList:
    try:
        profile = resolve_profile(request, profile_id)
        return simulation_service.get_alerts(profile=profile)
    except (KeyError, LookupError) as exc:
        raise_for_profile_error(exc)
    except AuthorizationError as exc:
        raise HTTPException(status_code=403, detail={"reason_code": exc.reason_code, "message": str(exc)}) from exc

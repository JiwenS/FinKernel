from __future__ import annotations

from fastapi import APIRouter, Depends, Response

from finkernel.schemas.discovery import (
    AssessPersonaRequest,
    ConfirmProfileDraftRequest,
    DiscoveryQuestion,
    DiscoverySession,
    PersonaAssessmentState,
    ProfileDraft,
    ReviewProfileRequest,
    StartDiscoveryRequest,
    SubmitDiscoveryAnswerRequest,
)
from finkernel.schemas.profile import (
    AppendProfileMemoryRequest,
    DistilledProfileMemoryResponse,
    MemoryKind,
    PersonaProfile,
    PersonaSourcePacket,
    ProfileMemorySearchResponse,
    ProfileOnboardingStatus,
    RiskProfileSummary,
    SavePersonaMarkdownRequest,
)
from finkernel.services.profile_discovery import ProfileDiscoveryService
from finkernel.services.profiles import ProfileStore
from finkernel.transport.http.dependencies import get_profile_discovery_service, get_profile_store, raise_for_profile_error

router = APIRouter(tags=["profiles"])


@router.get("/profiles/onboarding-status", response_model=ProfileOnboardingStatus)
def get_profile_onboarding_status(owner_id: str | None = None, profile_store: ProfileStore = Depends(get_profile_store)) -> ProfileOnboardingStatus:
    return profile_store.get_onboarding_status(owner_id=owner_id)


@router.post("/profiles/assess-persona", response_model=PersonaAssessmentState)
def assess_persona(payload: AssessPersonaRequest, discovery_service: ProfileDiscoveryService = Depends(get_profile_discovery_service)) -> PersonaAssessmentState:
    try:
        return discovery_service.assess_persona(
            owner_id=payload.owner_id,
            profile_id=payload.profile_id,
            preferred_profile_name=payload.preferred_profile_name,
            update_choice=payload.update_choice,
            update_notes=payload.update_notes,
        )
    except Exception as exc:
        raise_for_profile_error(exc)
        raise


@router.get("/profiles/{profile_id}", response_model=PersonaProfile)
def get_profile(profile_id: str, version: int | None = None, discovery_service: ProfileDiscoveryService = Depends(get_profile_discovery_service)) -> PersonaProfile:
    try:
        return discovery_service.get_profile(profile_id, version=version)
    except Exception as exc:
        raise_for_profile_error(exc)
        raise


@router.get("/profiles/{profile_id}/risk-summary", response_model=RiskProfileSummary)
def get_risk_profile_summary(profile_id: str, version: int | None = None, discovery_service: ProfileDiscoveryService = Depends(get_profile_discovery_service)) -> RiskProfileSummary:
    try:
        return discovery_service.get_risk_profile_summary(profile_id, version=version)
    except Exception as exc:
        raise_for_profile_error(exc)
        raise


@router.get("/profiles/{profile_id}/persona.md", response_class=Response)
def get_profile_persona_markdown(profile_id: str, version: int | None = None, discovery_service: ProfileDiscoveryService = Depends(get_profile_discovery_service)) -> Response:
    try:
        profile = discovery_service.get_profile(profile_id, version=version)
        return Response(content=profile.persona_markdown or "", media_type="text/markdown")
    except Exception as exc:
        raise_for_profile_error(exc)
        raise


@router.get("/profiles/{profile_id}/persona-sources", response_model=PersonaSourcePacket)
def get_profile_persona_sources(profile_id: str, version: int | None = None, discovery_service: ProfileDiscoveryService = Depends(get_profile_discovery_service)) -> PersonaSourcePacket:
    try:
        return discovery_service.get_persona_source_packet(profile_id, version=version)
    except Exception as exc:
        raise_for_profile_error(exc)
        raise


@router.put("/profiles/{profile_id}/persona", response_model=PersonaProfile)
def save_profile_persona_markdown(profile_id: str, payload: SavePersonaMarkdownRequest, discovery_service: ProfileDiscoveryService = Depends(get_profile_discovery_service)) -> PersonaProfile:
    try:
        return discovery_service.save_persona_markdown(profile_id=profile_id, persona_markdown=payload.persona_markdown, version=payload.version)
    except Exception as exc:
        raise_for_profile_error(exc)
        raise


@router.get("/profiles/{profile_id}/versions", response_model=list[PersonaProfile])
def list_profile_versions(profile_id: str, discovery_service: ProfileDiscoveryService = Depends(get_profile_discovery_service)) -> list[PersonaProfile]:
    try:
        return discovery_service.list_profile_versions(profile_id)
    except Exception as exc:
        raise_for_profile_error(exc)
        raise


@router.post("/profiles/discovery/sessions", response_model=DiscoverySession)
def start_profile_discovery(payload: StartDiscoveryRequest, discovery_service: ProfileDiscoveryService = Depends(get_profile_discovery_service)) -> DiscoverySession:
    return discovery_service.start_discovery(owner_id=payload.owner_id, preferred_profile_name=payload.preferred_profile_name)


@router.get("/profiles/discovery/sessions/{session_id}/next-question", response_model=DiscoveryQuestion | None)
def get_next_profile_question(session_id: str, discovery_service: ProfileDiscoveryService = Depends(get_profile_discovery_service)) -> DiscoveryQuestion | None:
    try:
        return discovery_service.get_next_question(session_id)
    except Exception as exc:
        raise_for_profile_error(exc)
        raise


@router.post("/profiles/discovery/sessions/{session_id}/answers", response_model=DiscoverySession)
def submit_profile_discovery_answer(session_id: str, payload: SubmitDiscoveryAnswerRequest, discovery_service: ProfileDiscoveryService = Depends(get_profile_discovery_service)) -> DiscoverySession:
    try:
        return discovery_service.submit_answer(session_id=session_id, answer_text=payload.answer, question_id=payload.question_id)
    except Exception as exc:
        raise_for_profile_error(exc)
        raise


@router.post("/profiles/discovery/sessions/{session_id}/draft", response_model=ProfileDraft)
def generate_profile_draft(session_id: str, discovery_service: ProfileDiscoveryService = Depends(get_profile_discovery_service)) -> ProfileDraft:
    try:
        return discovery_service.generate_draft(session_id)
    except Exception as exc:
        raise_for_profile_error(exc)
        raise


@router.post("/profiles/discovery/drafts/{draft_id}/confirm", response_model=dict)
def confirm_profile_draft(draft_id: str, payload: ConfirmProfileDraftRequest, discovery_service: ProfileDiscoveryService = Depends(get_profile_discovery_service)) -> dict:
    try:
        profile = discovery_service.confirm_draft(draft_id=draft_id, payload=payload)
        return {"profile": profile.model_dump(mode="json")}
    except Exception as exc:
        raise_for_profile_error(exc)
        raise


@router.post("/profiles/{profile_id}/review", response_model=DiscoverySession)
def review_profile(profile_id: str, payload: ReviewProfileRequest, discovery_service: ProfileDiscoveryService = Depends(get_profile_discovery_service)) -> DiscoverySession:
    try:
        return discovery_service.start_review(profile_id=profile_id, payload=payload)
    except Exception as exc:
        raise_for_profile_error(exc)
        raise


@router.post("/profiles/{profile_id}/memories", response_model=PersonaProfile)
def append_profile_memory(profile_id: str, payload: AppendProfileMemoryRequest, discovery_service: ProfileDiscoveryService = Depends(get_profile_discovery_service)) -> PersonaProfile:
    try:
        return discovery_service.append_memory(
            profile_id=profile_id,
            memory_kind=payload.memory_kind,
            theme=payload.theme,
            content_text=payload.content_text,
            source_dimension=payload.source_dimension,
            expires_at=payload.expires_at,
        )
    except Exception as exc:
        raise_for_profile_error(exc)
        raise


@router.get("/profiles/{profile_id}/memories/search", response_model=ProfileMemorySearchResponse)
def search_profile_memories(profile_id: str, query: str, memory_kind: str | None = None, include_expired: bool = False, discovery_service: ProfileDiscoveryService = Depends(get_profile_discovery_service)) -> ProfileMemorySearchResponse:
    try:
        return ProfileMemorySearchResponse(
            items=discovery_service.search_memory(
                profile_id=profile_id,
                query=query,
                memory_kind=MemoryKind(memory_kind) if memory_kind else None,
                include_expired=include_expired,
            )
        )
    except Exception as exc:
        raise_for_profile_error(exc)
        raise


@router.post("/profiles/{profile_id}/memories/distill", response_model=DistilledProfileMemoryResponse)
def distill_profile_memories(profile_id: str, discovery_service: ProfileDiscoveryService = Depends(get_profile_discovery_service)) -> DistilledProfileMemoryResponse:
    try:
        return discovery_service.distill_memory(profile_id=profile_id)
    except Exception as exc:
        raise_for_profile_error(exc)
        raise

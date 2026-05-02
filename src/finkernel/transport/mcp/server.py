from __future__ import annotations

from datetime import datetime

from mcp.server.fastmcp import FastMCP
from mcp.server.fastmcp.server import TransportSecuritySettings

from finkernel.schemas.discovery import ConfirmProfileDraftRequest, DiscoveryInterpretationPacket, PersonaUpdateChoice, ReviewProfileRequest
from finkernel.schemas.profile import MemoryKind
from finkernel.services.profile_discovery import ProfileDiscoveryService
from finkernel.services.profiles import ProfileStore

LOCAL_MCP_ALLOWED_HOSTS = [
    "localhost",
    "localhost:8000",
    "127.0.0.1",
    "127.0.0.1:8000",
    "testserver",
]


def create_mcp_server(*, profile_discovery_service: ProfileDiscoveryService, profile_store: ProfileStore) -> FastMCP:
    mcp = FastMCP(
        name="FinKernel MCP",
        instructions=(
            "Use these tools to build, assess, and maintain a personal risk profile through FinKernel. "
            "For dedicated profile-building flows, prefer assess_profile or the legacy assess_persona alias as the single orchestration entrypoint "
            "so the agent can tell whether it should add a profile from scratch, continue an update in progress, "
            "ask the user to choose an update section, or refresh profile markdown from a ready draft. "
            "For adaptive discovery workflows, hosts should inspect discovery state, use the returned section starter question when present, "
            "generate dynamic follow-up questions in the agent layer, and submit interpretation packets incrementally. "
            "When a user asks for portfolio guidance, risk review, or mandate clarification, first check profile "
            "onboarding status. If no active profile exists, start profile discovery before giving profile-scoped "
            "guidance. If a profile exists, read the active profile, persona markdown, persona sources, and risk "
            "profile summary before answering. Preferred flow: onboarding status -> assess_profile when building "
            "or updating the profile -> profile context -> risk profile summary -> review or memory updates. "
            "Do not jump straight to generic investment advice when FinKernel profile context is available."
        ),
        json_response=True,
        stateless_http=True,
        streamable_http_path="/",
        transport_security=TransportSecuritySettings(allowed_hosts=LOCAL_MCP_ALLOWED_HOSTS),
    )

    @mcp.tool(name="get_profile_onboarding_status")
    def get_profile_onboarding_status(owner_id: str | None = None) -> dict:
        return profile_store.get_onboarding_status(owner_id=owner_id).model_dump(mode="json")

    @mcp.tool(name="assess_persona")
    def assess_persona(
        owner_id: str,
        profile_id: str | None = None,
        preferred_profile_name: str | None = None,
        update_choice: str | None = None,
        update_notes: str | None = None,
    ) -> dict:
        return profile_discovery_service.assess_persona(
            owner_id=owner_id,
            profile_id=profile_id,
            preferred_profile_name=preferred_profile_name,
            update_choice=PersonaUpdateChoice(update_choice) if update_choice else None,
            update_notes=update_notes,
        ).model_dump(mode="json")

    @mcp.tool(name="assess_profile")
    def assess_profile(
        owner_id: str,
        profile_id: str | None = None,
        preferred_profile_name: str | None = None,
        update_choice: str | None = None,
        update_notes: str | None = None,
    ) -> dict:
        return assess_persona(
            owner_id=owner_id,
            profile_id=profile_id,
            preferred_profile_name=preferred_profile_name,
            update_choice=update_choice,
            update_notes=update_notes,
        )

    @mcp.tool(name="list_profiles")
    def list_profiles() -> dict:
        profiles = profile_store.load_all()
        return {
            "profiles": [
                {
                    "profile_id": item.profile_id,
                    "owner_id": item.owner_id,
                    "version": item.version,
                    "status": item.status.value,
                    "display_name": item.display_name,
                    "mandate_summary": item.mandate_summary,
                    "risk_budget": item.risk_budget.value,
                    "blocked_sectors": item.investment_constraints.blocked_sectors,
                    "blocked_tickers": item.investment_constraints.blocked_tickers,
                    "base_currency": item.investment_constraints.base_currency,
                    "created_from": item.created_from,
                }
                for item in profiles.values()
            ]
        }

    @mcp.tool(name="get_profile")
    def get_profile(profile_id: str, version: int | None = None) -> dict:
        return profile_discovery_service.get_profile(profile_id, version=version).model_dump(mode="json")

    @mcp.tool(name="get_profile_persona_markdown")
    def get_profile_persona_markdown(profile_id: str, version: int | None = None) -> dict:
        profile_record = profile_discovery_service.get_profile(profile_id, version=version)
        return {"profile_id": profile_record.profile_id, "version": profile_record.version, "persona_markdown": profile_record.persona_markdown}

    @mcp.tool(name="get_profile_markdown")
    def get_profile_markdown(profile_id: str, version: int | None = None) -> dict:
        profile_record = profile_discovery_service.get_profile(profile_id, version=version)
        return {
            "profile_id": profile_record.profile_id,
            "version": profile_record.version,
            "profile_markdown": profile_record.persona_markdown,
        }

    @mcp.tool(name="get_profile_persona_sources")
    def get_profile_persona_sources(profile_id: str, version: int | None = None) -> dict:
        return profile_discovery_service.get_persona_source_packet(profile_id, version=version).model_dump(mode="json")

    @mcp.tool(name="get_profile_sources")
    def get_profile_sources(profile_id: str, version: int | None = None) -> dict:
        return get_profile_persona_sources(profile_id=profile_id, version=version)

    @mcp.tool(name="get_risk_profile_summary")
    def get_risk_profile_summary(profile_id: str, version: int | None = None) -> dict:
        return profile_discovery_service.get_risk_profile_summary(profile_id, version=version).model_dump(mode="json")

    @mcp.tool(name="save_profile_persona_markdown")
    def save_profile_persona_markdown(profile_id: str, persona_markdown: str, version: int | None = None) -> dict:
        profile_record = profile_discovery_service.save_persona_markdown(profile_id=profile_id, persona_markdown=persona_markdown, version=version)
        return {"profile": profile_record.model_dump(mode="json")}

    @mcp.tool(name="save_profile_markdown")
    def save_profile_markdown(profile_id: str, profile_markdown: str, version: int | None = None) -> dict:
        profile_record = profile_discovery_service.save_profile_markdown(profile_id=profile_id, profile_markdown=profile_markdown, version=version)
        return {"profile": profile_record.model_dump(mode="json")}

    @mcp.tool(name="list_profile_versions")
    def list_profile_versions(profile_id: str) -> dict:
        return {"items": [item.model_dump(mode="json") for item in profile_discovery_service.list_profile_versions(profile_id)]}

    @mcp.tool(name="start_profile_discovery")
    def start_profile_discovery(owner_id: str, preferred_profile_name: str | None = None) -> dict:
        return profile_discovery_service.start_discovery(owner_id=owner_id, preferred_profile_name=preferred_profile_name).model_dump(mode="json")

    @mcp.tool(name="get_profile_discovery_state")
    def get_profile_discovery_state(discovery_session_id: str) -> dict:
        return profile_discovery_service.get_discovery_state(discovery_session_id).model_dump(mode="json")

    @mcp.tool(name="submit_profile_discovery_interpretation")
    def submit_profile_discovery_interpretation(discovery_session_id: str, packet: dict) -> dict:
        interpretation = DiscoveryInterpretationPacket.model_validate(packet)
        return profile_discovery_service.submit_interpretation(session_id=discovery_session_id, packet=interpretation).model_dump(mode="json")

    @mcp.tool(name="generate_profile_draft")
    def generate_profile_draft(discovery_session_id: str) -> dict:
        return profile_discovery_service.generate_draft(discovery_session_id).model_dump(mode="json")

    @mcp.tool(name="confirm_profile_draft")
    def confirm_profile_draft(
        profile_draft_id: str,
        persona_markdown: str | None = None,
        profile_markdown: str | None = None,
        profile_id: str | None = None,
        display_name: str | None = None,
    ) -> dict:
        profile = profile_discovery_service.confirm_draft(
            draft_id=profile_draft_id,
            payload=ConfirmProfileDraftRequest(
                profile_id=profile_id,
                display_name=display_name,
                persona_markdown=persona_markdown,
                profile_markdown=profile_markdown,
            ),
        )
        return {"profile": profile.model_dump(mode="json")}

    @mcp.tool(name="review_profile")
    def review_profile(profile_id: str, trigger: str, notes: str | None = None) -> dict:
        return profile_discovery_service.start_review(profile_id=profile_id, payload=ReviewProfileRequest(trigger=trigger, notes=notes)).model_dump(mode="json")

    @mcp.tool(name="append_profile_memory")
    def append_profile_memory(profile_id: str, memory_kind: str, theme: str, content_text: str, source_dimension: str | None = None, expires_at: str | None = None) -> dict:
        profile = profile_discovery_service.append_memory(
            profile_id=profile_id,
            memory_kind=MemoryKind(memory_kind),
            theme=theme,
            content_text=content_text,
            source_dimension=source_dimension,
            expires_at=datetime.fromisoformat(expires_at) if expires_at else None,
        )
        return {"profile": profile.model_dump(mode="json")}

    @mcp.tool(name="search_profile_memory")
    def search_profile_memory(profile_id: str, query: str, memory_kind: str | None = None, include_expired: bool = False) -> dict:
        return {
            "items": profile_discovery_service.search_memory(
                profile_id=profile_id,
                query=query,
                memory_kind=MemoryKind(memory_kind) if memory_kind else None,
                include_expired=include_expired,
            )
        }

    @mcp.tool(name="distill_profile_memory")
    def distill_profile_memory(profile_id: str) -> dict:
        return profile_discovery_service.distill_memory(profile_id=profile_id).model_dump(mode="json")

    return mcp

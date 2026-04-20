from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy.orm import Session

from finkernel.audit.service import AuditService
from finkernel.schemas.profile import PersonaProfile, ProfileAction
from finkernel.storage.models import WorkflowRequestModel


@dataclass
class AuthorizationError(Exception):
    reason_code: str
    message: str

    def __str__(self) -> str:
        return self.message


class ProfileAuthorizer:
    def __init__(self, audit_service: AuditService | None = None) -> None:
        self.audit_service = audit_service or AuditService()

    def ensure_trade_request_allowed(
        self,
        *,
        session: Session,
        profile: PersonaProfile,
        account_id: str,
        market: str,
        symbol: str,
    ) -> None:
        self._ensure_action(profile, ProfileAction.REQUEST_EXECUTION)
        self._ensure_account(profile, account_id)
        self._ensure_market(profile, market)
        self._ensure_symbol(profile, symbol)

    def ensure_request_visible(
        self,
        *,
        session: Session,
        profile: PersonaProfile,
        request: WorkflowRequestModel,
    ) -> None:
        self._ensure_action(profile, ProfileAction.OBSERVE)
        self._ensure_account(profile, request.account_id)
        self._ensure_symbol(profile, request.symbol)

    def ensure_action_allowed_for_request(
        self,
        *,
        session: Session,
        profile: PersonaProfile,
        request: WorkflowRequestModel,
        action: ProfileAction,
    ) -> None:
        self._ensure_action(profile, action)
        self._ensure_account(profile, request.account_id)
        self._ensure_symbol(profile, request.symbol)

    def record_denial(
        self,
        *,
        session: Session,
        workflow_request_id: str | None,
        profile: PersonaProfile,
        action: str,
        reason_code: str,
        message: str,
    ) -> None:
        self.audit_service.record(
            session,
            workflow_request_id=workflow_request_id,
            profile_id=profile.profile_id,
            profile_version=profile.version,
            event_type="AUTHORIZATION_DENIED",
            actor_type="profile",
            actor_id=profile.profile_id,
            state=None,
            decision="BLOCK",
            reason_code=reason_code,
            message=message,
            payload={"owner_id": profile.owner_id, "action": action},
        )

    def _ensure_action(self, profile: PersonaProfile, action: ProfileAction) -> None:
        if not profile.allows_action(action):
            raise AuthorizationError("ACTION_NOT_ALLOWED", f"Profile {profile.profile_id} cannot perform {action.value}.")

    def _ensure_account(self, profile: PersonaProfile, account_id: str) -> None:
        if not profile.allows_account(account_id):
            raise AuthorizationError("ACCOUNT_SCOPE_DENIED", f"Profile {profile.profile_id} cannot access account {account_id}.")

    def _ensure_market(self, profile: PersonaProfile, market: str) -> None:
        if not profile.allows_market(market):
            raise AuthorizationError("MARKET_SCOPE_DENIED", f"Profile {profile.profile_id} cannot access market {market}.")

    def _ensure_symbol(self, profile: PersonaProfile, symbol: str) -> None:
        if not profile.allows_symbol(symbol):
            raise AuthorizationError("SYMBOL_SCOPE_DENIED", f"Profile {profile.profile_id} cannot access symbol {symbol}.")

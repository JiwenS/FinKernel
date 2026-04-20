from __future__ import annotations

import logging
import secrets
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Iterator

from sqlalchemy.orm import Session, sessionmaker

from finkernel.audit.service import AuditService
from finkernel.config import Settings
from finkernel.connectors.errors import BrokerConnectorError
from finkernel.policy.engine import PolicyEngine
from finkernel.schemas.policy import PolicyDecisionType
from finkernel.schemas.profile import PersonaProfile
from finkernel.schemas.trade import TradeRequestCreate, TradeRequestResponse
from finkernel.schemas.workflow import WorkflowState
from finkernel.services.authorization import AuthorizationError, ProfileAuthorizer
from finkernel.services.interfaces import BrokerClient, ConfirmationChannel
from finkernel.services.observability import ObservabilityService
from finkernel.storage.models import WorkflowRequestModel
from finkernel.storage.repositories import WorkflowRepository

logger = logging.getLogger(__name__)


class TradeWorkflowService:
    def __init__(
        self,
        settings: Settings,
        session_factory: sessionmaker[Session],
        policy_engine: PolicyEngine,
        broker_client: BrokerClient,
        confirmation_channel: ConfirmationChannel,
        observability_service: ObservabilityService | None = None,
        audit_service: AuditService | None = None,
        workflow_repository: WorkflowRepository | None = None,
        profile_authorizer: ProfileAuthorizer | None = None,
    ) -> None:
        self.settings = settings
        self.session_factory = session_factory
        self.policy_engine = policy_engine
        self.broker_client = broker_client
        self.confirmation_channel = confirmation_channel
        self.observability_service = observability_service or ObservabilityService()
        self.audit_service = audit_service or AuditService()
        self.workflow_repository = workflow_repository or WorkflowRepository()
        self.profile_authorizer = profile_authorizer or ProfileAuthorizer(self.audit_service)

    @contextmanager
    def _session_scope(self) -> Iterator[Session]:
        session = self.session_factory()
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    def submit_trade_request(self, trade_request: TradeRequestCreate, request_source: str, profile: PersonaProfile) -> TradeRequestResponse:
        with self._session_scope() as session:
            try:
                self.profile_authorizer.ensure_trade_request_allowed(
                    session=session,
                    profile=profile,
                    account_id=trade_request.actor.account_id,
                    market=trade_request.market.value,
                    symbol=trade_request.symbol,
                )
            except AuthorizationError as exc:
                self._persist_profile_denial(
                    workflow_request_id=None,
                    profile=profile,
                    action="request_execution",
                    reason_code=exc.reason_code,
                    message=str(exc),
                )
                raise
            if trade_request.idempotency_key:
                existing = self.workflow_repository.get_by_idempotency_key(session, trade_request.idempotency_key)
                if existing is not None:
                    return self._to_response(existing)

            model = WorkflowRequestModel(
                user_id=trade_request.actor.user_id,
                account_id=trade_request.actor.account_id,
                owner_id=profile.owner_id,
                profile_id=profile.profile_id,
                profile_version=profile.version,
                session_id=trade_request.actor.session_id,
                symbol=trade_request.symbol,
                side=trade_request.side.value,
                quantity=trade_request.quantity,
                limit_price=trade_request.limit_price,
                order_type=trade_request.order_type.value,
                market=trade_request.market.value,
                broker=trade_request.broker.value,
                state=WorkflowState.REQUESTED.value,
                request_source=request_source,
                idempotency_key=trade_request.idempotency_key,
                notes=trade_request.notes,
            )
            self.workflow_repository.add(session, model)
            self.audit_service.record(
                session,
                workflow_request_id=model.request_id,
                profile_id=profile.profile_id,
                profile_version=profile.version,
                event_type="REQUEST_RECEIVED",
                actor_type="user",
                actor_id=model.user_id,
                state=model.state,
                message="Trade request accepted into the workflow.",
                payload={
                    "symbol": model.symbol,
                    "quantity": model.quantity,
                    "limit_price": str(model.limit_price),
                    "request_source": request_source,
                    "profile_id": profile.profile_id,
                    "profile_version": profile.version,
                    "owner_id": profile.owner_id,
                },
            )

            decision = self.policy_engine.evaluate_trade_request(trade_request)
            self._transition_state(model, WorkflowState.POLICY_EVALUATED.value)
            model.policy_decision = decision.decision.value
            model.policy_reason_code = decision.reason_code.value
            model.policy_explanation = decision.explanation
            self.audit_service.record(
                session,
                workflow_request_id=model.request_id,
                event_type="POLICY_EVALUATED",
                actor_type="system",
                actor_id=None,
                state=model.state,
                decision=decision.decision.value,
                reason_code=decision.reason_code.value,
                message=decision.explanation,
                payload=decision.filtered_scope,
                profile_id=profile.profile_id,
                profile_version=profile.version,
            )

            if decision.decision is PolicyDecisionType.BLOCK:
                self._transition_state(model, WorkflowState.REJECTED.value)
                model.last_error = decision.explanation
                self.audit_service.record(
                    session,
                    workflow_request_id=model.request_id,
                    profile_id=profile.profile_id,
                    profile_version=profile.version,
                    event_type="WORKFLOW_TERMINATED",
                    actor_type="system",
                    actor_id=None,
                    state=model.state,
                    decision=decision.decision.value,
                    reason_code=decision.reason_code.value,
                    message="Trade request blocked by policy.",
                )
                session.flush()
                return self._to_response(model)

            self._transition_state(model, WorkflowState.PENDING_CONFIRMATION.value)
            model.confirmation_token = secrets.token_urlsafe(16)
            self.audit_service.record(
                session,
                workflow_request_id=model.request_id,
                event_type="AWAITING_CONFIRMATION",
                actor_type="system",
                actor_id=None,
                state=model.state,
                decision=decision.decision.value,
                reason_code=decision.reason_code.value,
                message="Human confirmation is required before broker submission.",
                profile_id=profile.profile_id,
                profile_version=profile.version,
            )
            session.flush()
            response = self._to_response(model)
            request_id = model.request_id

        current = self.get_model(request_id)
        if current is None:
            raise RuntimeError(f"Workflow request {request_id} disappeared before confirmation dispatch.")
        self.confirmation_channel.send_confirmation(current)
        return response

    def get_trade_request(self, request_id: str) -> TradeRequestResponse | None:
        with self._session_scope() as session:
            model = self.workflow_repository.get(session, request_id)
            return self._to_response(model) if model else None

    def get_model(self, request_id: str) -> WorkflowRequestModel | None:
        with self._session_scope() as session:
            model = self.workflow_repository.get(session, request_id)
            if model is None:
                return None
            session.expunge(model)
            return model

    def handle_confirmation_command(self, actor_id: str, content: str) -> str:
        parts = content.strip().split()
        if len(parts) != 3:
            return "Usage: !approve <request_id> <token> or !reject <request_id> <token>"
        command = parts[0].lstrip(self.settings.discord_command_prefix).lower()
        request_id = parts[1]
        token = parts[2]
        if command == "approve":
            return self._approve_request(request_id, actor_id, token)
        if command == "reject":
            return self._reject_request(request_id, actor_id, token)
        return "Unknown command. Use !approve <request_id> <token> or !reject <request_id> <token>."

    def handle_confirmation_action(self, actor_id: str, action: str, request_id: str, token: str) -> str:
        if action == "approve":
            return self._approve_request(request_id, actor_id, token)
        if action == "reject":
            return self._reject_request(request_id, actor_id, token)
        return f"Unknown action: {action}"

    def approve_trade_request(self, request_id: str, *, actor_id: str, actor_type: str = "profile") -> str:
        return self._approve_request(
            request_id,
            actor_id,
            token=None,
            validate_confirmation=False,
            actor_type=actor_type,
            approval_message="Trade request approved from advisory control plane.",
        )

    def reject_trade_request(self, request_id: str, *, actor_id: str, actor_type: str = "profile") -> str:
        return self._reject_request(
            request_id,
            actor_id,
            token=None,
            validate_confirmation=False,
            actor_type=actor_type,
            rejection_message="Trade request rejected from advisory control plane.",
        )

    def _approve_request(
        self,
        request_id: str,
        actor_id: str,
        token: str | None,
        *,
        validate_confirmation: bool = True,
        actor_type: str = "discord_user",
        approval_message: str = "Trade request confirmed from Discord.",
    ) -> str:
        with self._session_scope() as session:
            model = self.workflow_repository.get(session, request_id)
            if validate_confirmation:
                validation_error = self._validate_confirmation_attempt(
                    session=session,
                    model=model,
                    actor_id=actor_id,
                    token=token,
                    action="approve",
                )
                if validation_error is not None:
                    return validation_error
            elif model is None:
                return "Request was not found."
            elif model.state != WorkflowState.PENDING_CONFIRMATION.value:
                return f"Request {model.request_id} is in state {model.state} and cannot be approved."
            self._transition_state(model, WorkflowState.CONFIRMED.value)
            self.audit_service.record(
                session,
                workflow_request_id=model.request_id,
                profile_id=model.profile_id,
                profile_version=model.profile_version,
                event_type="CONFIRMED",
                actor_type=actor_type,
                actor_id=actor_id,
                state=model.state,
                message=approval_message,
            )
            session.flush()

        with self._session_scope() as session:
            model = self.workflow_repository.get(session, request_id)
            if model is None:
                return f"Request {request_id} disappeared before broker submission."
            self._transition_state(model, WorkflowState.SUBMITTING.value)
            self.audit_service.record(
                session,
                workflow_request_id=model.request_id,
                profile_id=model.profile_id,
                profile_version=model.profile_version,
                event_type="BROKER_DISPATCHING",
                actor_type="system",
                actor_id=None,
                state=model.state,
                message="Trade request is being dispatched to the broker.",
            )
            session.flush()

        detached_model = self.get_model(request_id)
        if detached_model is None:
            return f"Request {request_id} disappeared before broker submission."

        try:
            result = self.broker_client.submit_order(detached_model)
        except Exception as exc:
            error_payload = self._normalize_connector_error(exc)
            with self._session_scope() as session:
                current = self.workflow_repository.get(session, request_id)
                if current is None:
                    return f"Request {request_id} disappeared before failure handling."
                self._transition_state(current, WorkflowState.FAILED.value)
                current.last_error_code = error_payload["code"]
                current.last_error = error_payload["message"]
                self.audit_service.record(
                    session,
                    workflow_request_id=current.request_id,
                    profile_id=current.profile_id,
                    profile_version=current.profile_version,
                    event_type="BROKER_FAILED",
                    actor_type="system",
                    actor_id=None,
                    state=current.state,
                    message="Broker submission failed.",
                    payload=error_payload,
                )
                self.observability_service.record_broker_outcome(outcome=error_payload["code"])
                logger.warning(
                    "broker_outcome request_id=%s outcome=%s request_source=%s",
                    current.request_id,
                    error_payload["code"],
                    current.request_source,
                )
            self._safe_status_update(detached_model, f"Request {request_id} failed: {error_payload['message']}")
            return f"Request {request_id} failed during broker submission: {error_payload['message']}"

        with self._session_scope() as session:
            current = self.workflow_repository.get(session, request_id)
            if current is None:
                return f"Request {request_id} disappeared after broker submission."
            self._transition_state(current, WorkflowState.SUBMITTED.value)
            self.audit_service.record(
                session,
                workflow_request_id=current.request_id,
                profile_id=current.profile_id,
                profile_version=current.profile_version,
                event_type="BROKER_SUBMITTED",
                actor_type="system",
                actor_id=None,
                state=current.state,
                message="Broker submission completed and returned a response.",
                payload={"connector_trace_id": result.connector_trace_id},
            )
            self._transition_state(current, WorkflowState.ACKED.value)
            current.broker_order_id = result.broker_order_id
            current.broker_status = result.status
            current.connector_trace_id = result.connector_trace_id
            self.audit_service.record(
                session,
                workflow_request_id=current.request_id,
                profile_id=current.profile_id,
                profile_version=current.profile_version,
                event_type="BROKER_ACKED",
                actor_type="system",
                actor_id=None,
                state=current.state,
                message="Broker accepted the limit order.",
                payload=result.raw_response,
            )
            self.observability_service.record_broker_outcome(outcome=result.status)
            logger.info(
                "broker_outcome request_id=%s outcome=%s broker_order_id=%s connector_trace_id=%s request_source=%s",
                current.request_id,
                result.status,
                result.broker_order_id,
                result.connector_trace_id,
                current.request_source,
            )
        self._safe_status_update(detached_model, f"Request {request_id} acknowledged by Alpaca with status {result.status}.")
        return f"Request {request_id} approved and submitted successfully."

    def _reject_request(
        self,
        request_id: str,
        actor_id: str,
        token: str | None,
        *,
        validate_confirmation: bool = True,
        actor_type: str = "discord_user",
        rejection_message: str = "Trade request rejected from Discord.",
    ) -> str:
        with self._session_scope() as session:
            model = self.workflow_repository.get(session, request_id)
            if validate_confirmation:
                validation_error = self._validate_confirmation_attempt(
                    session=session,
                    model=model,
                    actor_id=actor_id,
                    token=token,
                    action="reject",
                )
                if validation_error is not None:
                    return validation_error
            elif model is None:
                return "Request was not found."
            elif model.state != WorkflowState.PENDING_CONFIRMATION.value:
                return f"Request {model.request_id} is in state {model.state} and cannot be rejected."
            self._transition_state(model, WorkflowState.REJECTED.value)
            model.last_error = "Rejected from Discord confirmation flow."
            self.audit_service.record(
                session,
                workflow_request_id=model.request_id,
                profile_id=model.profile_id,
                profile_version=model.profile_version,
                event_type="REJECTED",
                actor_type=actor_type,
                actor_id=actor_id,
                state=model.state,
                message=rejection_message,
            )
            session.flush()
            detached = self._to_response(model)
        current = self.get_model(request_id)
        if current:
            self._safe_status_update(current, f"Request {request_id} was rejected in Discord.")
        return f"Request {detached.request_id} rejected."

    def _is_authorized_actor(self, actor_id: str) -> bool:
        return actor_id in self.settings.discord_allowed_user_ids

    def _validate_confirmation_attempt(
        self,
        *,
        session: Session,
        model: WorkflowRequestModel | None,
        actor_id: str,
        token: str,
        action: str,
    ) -> str | None:
        if model is None:
            return "Request was not found."
        if model.state != WorkflowState.PENDING_CONFIRMATION.value:
            return f"Request {model.request_id} is in state {model.state} and cannot be {action}d."
        if not self._is_authorized_actor(actor_id):
            self.audit_service.record(
                session,
                workflow_request_id=model.request_id,
                profile_id=model.profile_id,
                profile_version=model.profile_version,
                event_type="UNAUTHORIZED_CONFIRMATION_ATTEMPT",
                actor_type="discord_user",
                actor_id=actor_id,
                state=model.state,
                message=f"Unauthorized Discord actor attempted to {action} a trade request.",
            )
            return f"You are not authorized to {action} FinKernel trade requests."
        if model.confirmation_token != token:
            noun = "approval" if action == "approve" else "rejection"
            self.audit_service.record(
                session,
                workflow_request_id=model.request_id,
                profile_id=model.profile_id,
                profile_version=model.profile_version,
                event_type="INVALID_CONFIRMATION_TOKEN",
                actor_type="discord_user",
                actor_id=actor_id,
                state=model.state,
                message=f"Discord {noun} used an invalid request token.",
            )
            return "Invalid confirmation token."
        return None

    def _transition_state(self, model: WorkflowRequestModel, new_state: str) -> None:
        previous_state = model.state
        model.state = new_state
        model.updated_at = datetime.now(timezone.utc)
        self.observability_service.record_state_transition(previous_state=previous_state, new_state=new_state)
        logger.info(
            "workflow_transition request_id=%s from_state=%s to_state=%s request_source=%s broker_order_id=%s",
            model.request_id,
            previous_state,
            new_state,
            model.request_source,
            model.broker_order_id,
        )

    def _normalize_connector_error(self, exc: Exception) -> dict:
        if isinstance(exc, BrokerConnectorError):
            return exc.to_dict()
        return {
            "code": "UNKNOWN_CONNECTOR_ERROR",
            "message": str(exc),
            "status_code": None,
            "response_body": None,
            "retryable": False,
        }

    def _safe_status_update(self, workflow_request: WorkflowRequestModel, message: str) -> None:
        try:
            self.confirmation_channel.send_status_update(workflow_request, message)
        except Exception:
            pass

    def _persist_profile_denial(
        self,
        *,
        workflow_request_id: str | None,
        profile: PersonaProfile,
        action: str,
        reason_code: str,
        message: str,
    ) -> None:
        with self._session_scope() as session:
            self.profile_authorizer.record_denial(
                session=session,
                workflow_request_id=workflow_request_id,
                profile=profile,
                action=action,
                reason_code=reason_code,
                message=message,
            )

    def _to_response(self, model: WorkflowRequestModel | None) -> TradeRequestResponse | None:
        if model is None:
            return None
        return TradeRequestResponse(
            request_id=model.request_id,
            owner_id=model.owner_id,
            profile_id=model.profile_id,
            profile_version=model.profile_version,
            state=model.state,
            symbol=model.symbol,
            side=model.side,
            quantity=model.quantity,
            limit_price=model.limit_price,
            order_type=model.order_type,
            stop_price=None,
            take_profit=None,
            stop_loss=None,
            trail_percent=None,
            trail_price=None,
            market=model.market,
            broker=model.broker,
            policy_decision=model.policy_decision,
            policy_reason_code=model.policy_reason_code,
            policy_explanation=model.policy_explanation,
            request_source=model.request_source,
            broker_order_id=model.broker_order_id,
            broker_status=model.broker_status,
            last_error_code=model.last_error_code,
            last_error=model.last_error,
            idempotency_key=model.idempotency_key,
            created_at=model.created_at,
            updated_at=model.updated_at,
        )

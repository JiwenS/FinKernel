from __future__ import annotations

from contextlib import contextmanager
from datetime import UTC, datetime
import logging
from typing import Iterator

from sqlalchemy.orm import Session, sessionmaker

from finkernel.audit.service import AuditService
from finkernel.schemas.control_plane import (
    AuditEventListResponse,
    AuditEventResponse,
    BrokerOrderSnapshot,
    ReconciliationResult,
    ReconciliationStatus,
    WorkflowRequestListResponse,
    WorkflowRequestSummary,
)
from finkernel.schemas.profile import PersonaProfile, ProfileAction
from finkernel.schemas.workflow import WorkflowState
from finkernel.services.authorization import AuthorizationError, ProfileAuthorizer
from finkernel.services.interfaces import BrokerClient
from finkernel.services.observability import ObservabilityService
from finkernel.storage.models import WorkflowRequestModel
from finkernel.storage.repositories import AuditRepository, WorkflowRepository

logger = logging.getLogger(__name__)


class ControlPlaneService:
    def __init__(
        self,
        *,
        session_factory: sessionmaker[Session],
        workflow_repository: WorkflowRepository | None = None,
        audit_repository: AuditRepository | None = None,
        audit_service: AuditService | None = None,
        observability_service: ObservabilityService | None = None,
        broker_client: BrokerClient,
        profile_authorizer: ProfileAuthorizer | None = None,
    ) -> None:
        self.session_factory = session_factory
        self.workflow_repository = workflow_repository or WorkflowRepository()
        self.audit_repository = audit_repository or AuditRepository()
        self.audit_service = audit_service or AuditService()
        self.observability_service = observability_service or ObservabilityService()
        self.broker_client = broker_client
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

    def list_requests(
        self,
        *,
        profile: PersonaProfile,
        state: str | None = None,
        symbol: str | None = None,
        account_id: str | None = None,
        created_from: datetime | None = None,
        created_to: datetime | None = None,
        limit: int = 50,
    ) -> WorkflowRequestListResponse:
        try:
            self.profile_authorizer._ensure_action(profile, ProfileAction.OBSERVE)
            if account_id:
                self.profile_authorizer._ensure_account(profile, account_id)
            if symbol:
                self.profile_authorizer._ensure_symbol(profile, symbol)
        except AuthorizationError as exc:
            self._persist_denial(
                workflow_request_id=None,
                profile=profile,
                action="observe",
                reason_code=exc.reason_code,
                message=str(exc),
            )
            raise
        with self._session_scope() as session:
            items, total = self.workflow_repository.list_requests(
                session,
                state=state,
                symbols=[symbol.upper()] if symbol else (profile.allowed_symbols or None),
                account_ids=[account_id] if account_id else profile.allowed_accounts,
                created_from=created_from,
                created_to=created_to,
                limit=limit,
            )
            return WorkflowRequestListResponse(items=[self._to_summary(item) for item in items], total=total)

    def get_request(self, request_id: str, *, profile: PersonaProfile) -> WorkflowRequestSummary | None:
        with self._session_scope() as session:
            model = self.workflow_repository.get(session, request_id)
            if model is None:
                return None
            try:
                self.profile_authorizer.ensure_request_visible(session=session, profile=profile, request=model)
            except AuthorizationError as exc:
                self._persist_denial(
                    workflow_request_id=model.request_id,
                    profile=profile,
                    action="observe",
                    reason_code=exc.reason_code,
                    message=str(exc),
                )
                raise
            return self._to_summary(model)

    def list_audit_events(
        self,
        *,
        profile: PersonaProfile,
        workflow_request_id: str | None = None,
        event_type: str | None = None,
        limit: int = 100,
    ) -> AuditEventListResponse:
        with self._session_scope() as session:
            try:
                self.profile_authorizer._ensure_action(profile, ProfileAction.OBSERVE)
            except AuthorizationError as exc:
                self._persist_denial(
                    workflow_request_id=workflow_request_id,
                    profile=profile,
                    action="observe",
                    reason_code=exc.reason_code,
                    message=str(exc),
                )
                raise
            if workflow_request_id:
                request = self.workflow_repository.get(session, workflow_request_id)
                if request is None:
                    return AuditEventListResponse(items=[], total=0)
                try:
                    self.profile_authorizer.ensure_request_visible(session=session, profile=profile, request=request)
                except AuthorizationError as exc:
                    self._persist_denial(
                        workflow_request_id=request.request_id,
                        profile=profile,
                        action="observe",
                        reason_code=exc.reason_code,
                        message=str(exc),
                    )
                    raise
            items, total = self.audit_repository.list_events(
                session,
                workflow_request_id=workflow_request_id,
                event_type=event_type,
                account_ids=profile.allowed_accounts,
                symbols=profile.allowed_symbols or None,
                actor_id_for_unscoped_events=profile.profile_id,
                limit=limit,
            )
            return AuditEventListResponse(items=[self._to_audit_response(item) for item in items], total=total)

    def reconcile_request(self, request_id: str, *, profile: PersonaProfile, actor_id: str | None = None) -> ReconciliationResult:
        with self._session_scope() as session:
            model = self.workflow_repository.get(session, request_id)
            if model is None:
                raise ValueError(f"Workflow request {request_id} was not found.")
            try:
                self.profile_authorizer.ensure_action_allowed_for_request(
                    session=session,
                    profile=profile,
                    request=model,
                    action=ProfileAction.RECONCILE,
                )
            except AuthorizationError as exc:
                self._persist_denial(
                    workflow_request_id=model.request_id,
                    profile=profile,
                    action="reconcile",
                    reason_code=exc.reason_code,
                    message=str(exc),
                )
                raise

            result = self._reconcile_model(session, model, actor_id=actor_id or profile.profile_id)
            return result

    def reconcile_inflight_requests(self, *, actor_id: str = "system-startup") -> list[ReconciliationResult]:
        with self._session_scope() as session:
            items = self.workflow_repository.list_inflight_requests(session)
            return [self._reconcile_model(session, model, actor_id=actor_id) for model in items]

    def refresh_request(self, request_id: str, *, profile: PersonaProfile, actor_id: str | None = None) -> ReconciliationResult:
        with self._session_scope() as session:
            model = self.workflow_repository.get(session, request_id)
            if model is None:
                raise ValueError(f"Workflow request {request_id} was not found.")
            try:
                self.profile_authorizer.ensure_action_allowed_for_request(
                    session=session,
                    profile=profile,
                    request=model,
                    action=ProfileAction.REFRESH,
                )
            except AuthorizationError as exc:
                self._persist_denial(
                    workflow_request_id=model.request_id,
                    profile=profile,
                    action="refresh",
                    reason_code=exc.reason_code,
                    message=str(exc),
                )
                raise
        return self.reconcile_request(request_id, profile=profile, actor_id=actor_id or f"{profile.profile_id}-refresh")

    def refresh_active_requests(self, *, actor_id: str = "system-refresh-loop") -> list[ReconciliationResult]:
        with self._session_scope() as session:
            items = self.workflow_repository.list_active_requests(session)
            return [self._reconcile_model(session, model, actor_id=actor_id) for model in items]

    def cancel_request(self, request_id: str, *, profile: PersonaProfile, actor_id: str | None = None) -> ReconciliationResult:
        with self._session_scope() as session:
            model = self.workflow_repository.get(session, request_id)
            if model is None:
                raise ValueError(f"Workflow request {request_id} was not found.")
            try:
                self.profile_authorizer.ensure_action_allowed_for_request(
                    session=session,
                    profile=profile,
                    request=model,
                    action=ProfileAction.CANCEL,
                )
            except AuthorizationError as exc:
                self._persist_denial(
                    workflow_request_id=model.request_id,
                    profile=profile,
                    action="cancel",
                    reason_code=exc.reason_code,
                    message=str(exc),
                )
                raise
            if not self._is_cancelable(model):
                raise ValueError(f"Workflow request {request_id} is not cancelable in state {model.state}.")
            if not model.broker_order_id:
                raise ValueError(f"Workflow request {request_id} has no broker order id to cancel.")

            model.state = WorkflowState.CANCEL_REQUESTED.value
            self.audit_service.record(
                session,
                workflow_request_id=model.request_id,
                profile_id=model.profile_id,
                profile_version=model.profile_version,
                event_type="CANCEL_REQUESTED",
                actor_type="system",
                actor_id=actor_id or profile.profile_id,
                state=model.state,
                message="Cancel requested for workflow order.",
                payload={"broker_order_id": model.broker_order_id, "profile_id": profile.profile_id, "owner_id": profile.owner_id},
            )
            session.flush()

        try:
            self.broker_client.cancel_order(broker_order_id=model.broker_order_id)
        except Exception as exc:
            with self._session_scope() as session:
                current = self.workflow_repository.get(session, request_id)
                if current is not None:
                    current.last_error_code = "CANCEL_FAILED"
                    current.last_error = str(exc)
                    self.audit_service.record(
                        session,
                        workflow_request_id=current.request_id,
                        profile_id=current.profile_id,
                        profile_version=current.profile_version,
                        event_type="CANCEL_FAILED",
                        actor_type="system",
                        actor_id=actor_id or profile.profile_id,
                        state=current.state,
                        message="Cancel request failed at broker.",
                        payload={"error": str(exc), "profile_id": profile.profile_id},
                    )
            raise

        with self._session_scope() as session:
            current = self.workflow_repository.get(session, request_id)
            if current is None:
                raise ValueError(f"Workflow request {request_id} disappeared after cancel dispatch.")
            current.state = WorkflowState.CANCELING.value
            self.audit_service.record(
                session,
                workflow_request_id=current.request_id,
                profile_id=current.profile_id,
                profile_version=current.profile_version,
                event_type="CANCEL_DISPATCHED",
                actor_type="system",
                actor_id=actor_id or profile.profile_id,
                state=current.state,
                message="Cancel submitted to broker.",
                payload={"broker_order_id": current.broker_order_id, "profile_id": profile.profile_id},
            )
            session.flush()

        return self.reconcile_request(request_id, profile=profile, actor_id=actor_id or profile.profile_id)

    def _reconcile_model(self, session: Session, model: WorkflowRequestModel, *, actor_id: str) -> ReconciliationResult:
        local_before = model.state
        now = datetime.now(UTC)

        if model.state in {
            WorkflowState.REQUESTED.value,
            WorkflowState.POLICY_EVALUATED.value,
            WorkflowState.PENDING_CONFIRMATION.value,
            WorkflowState.REJECTED.value,
        }:
            model.reconciliation_status = ReconciliationStatus.SKIPPED.value
            model.reconciliation_reason = "No broker reconciliation is required before broker submission."
            model.last_reconciled_at = now
            self.audit_service.record(
                session,
                workflow_request_id=model.request_id,
                profile_id=model.profile_id,
                profile_version=model.profile_version,
                event_type="RECONCILIATION_SKIPPED",
                actor_type="system",
                actor_id=actor_id,
                state=model.state,
                message=model.reconciliation_reason,
            )
            self.observability_service.record_reconciliation_outcome(outcome=ReconciliationStatus.SKIPPED.value)
            logger.info(
                "reconciliation_outcome request_id=%s status=%s local_state=%s broker_order_id=%s actor_id=%s",
                model.request_id,
                ReconciliationStatus.SKIPPED.value,
                model.state,
                model.broker_order_id,
                actor_id,
            )
            return self._build_result(model, local_before, ReconciliationStatus.SKIPPED, model.reconciliation_reason, now)

        snapshot = self._fetch_snapshot(model)
        if snapshot is not None and snapshot.status == "broker_error":
            model.reconciliation_status = ReconciliationStatus.BROKER_ERROR.value
            model.reconciliation_reason = "Broker lookup failed during reconciliation."
            model.last_reconciled_at = now
            self.audit_service.record(
                session,
                workflow_request_id=model.request_id,
                profile_id=model.profile_id,
                profile_version=model.profile_version,
                event_type="RECONCILIATION_BROKER_ERROR",
                actor_type="system",
                actor_id=actor_id,
                state=model.state,
                message=model.reconciliation_reason,
                payload=snapshot.raw_response,
            )
            self.observability_service.record_reconciliation_outcome(outcome=ReconciliationStatus.BROKER_ERROR.value)
            logger.warning(
                "reconciliation_outcome request_id=%s status=%s local_state=%s broker_order_id=%s actor_id=%s",
                model.request_id,
                ReconciliationStatus.BROKER_ERROR.value,
                model.state,
                model.broker_order_id,
                actor_id,
            )
            return self._build_result(model, local_before, ReconciliationStatus.BROKER_ERROR, model.reconciliation_reason, now)
        if snapshot is None:
            model.state = WorkflowState.DRIFTED.value
            model.reconciliation_status = ReconciliationStatus.NOT_FOUND.value
            model.reconciliation_reason = "Broker order was not found during reconciliation."
            model.last_reconciled_at = now
            self.audit_service.record(
                session,
                workflow_request_id=model.request_id,
                profile_id=model.profile_id,
                profile_version=model.profile_version,
                event_type="RECONCILIATION_DRIFTED",
                actor_type="system",
                actor_id=actor_id,
                state=model.state,
                message=model.reconciliation_reason,
            )
            self.observability_service.record_reconciliation_outcome(outcome=ReconciliationStatus.NOT_FOUND.value)
            logger.warning(
                "reconciliation_outcome request_id=%s status=%s local_state=%s broker_order_id=%s actor_id=%s",
                model.request_id,
                ReconciliationStatus.NOT_FOUND.value,
                model.state,
                model.broker_order_id,
                actor_id,
            )
            return self._build_result(model, local_before, ReconciliationStatus.NOT_FOUND, model.reconciliation_reason, now)

        desired_state = self._map_broker_status_to_local(snapshot.status)
        if desired_state == WorkflowState.DRIFTED.value:
            model.state = desired_state
            status = ReconciliationStatus.DRIFTED
            reason = f"Broker status {snapshot.status} does not map cleanly to the local state model."
        else:
            model.state = desired_state
            status = ReconciliationStatus.MATCHED
            reason = f"Broker status {snapshot.status} reconciled successfully."

        model.broker_order_id = snapshot.broker_order_id or model.broker_order_id
        model.broker_status = snapshot.status
        model.reconciliation_status = status.value
        model.reconciliation_reason = reason
        model.last_reconciled_at = now
        self.audit_service.record(
            session,
            workflow_request_id=model.request_id,
            profile_id=model.profile_id,
            profile_version=model.profile_version,
            event_type="RECONCILIATION_COMPLETED" if status is ReconciliationStatus.MATCHED else "RECONCILIATION_DRIFTED",
            actor_type="system",
            actor_id=actor_id,
            state=model.state,
            message=reason,
            payload=snapshot.raw_response,
        )
        self.observability_service.record_reconciliation_outcome(outcome=status.value)
        logger.info(
            "reconciliation_outcome request_id=%s status=%s local_before=%s local_after=%s broker_status=%s broker_order_id=%s actor_id=%s request_source=%s",
            model.request_id,
            status.value,
            local_before,
            model.state,
            snapshot.status,
            model.broker_order_id,
            actor_id,
            model.request_source,
        )
        return self._build_result(model, local_before, status, reason, now)

    def _fetch_snapshot(self, model: WorkflowRequestModel) -> BrokerOrderSnapshot | None:
        try:
            return self.broker_client.get_order(
                broker_order_id=model.broker_order_id,
                client_order_id=model.request_id,
            )
        except Exception as exc:
            return BrokerOrderSnapshot(
                broker_order_id=model.broker_order_id or "",
                client_order_id=model.request_id,
                status="broker_error",
                raw_response={"error": str(exc)},
            )

    def _map_broker_status_to_local(self, broker_status: str) -> str:
        normalized = broker_status.lower()
        if normalized in {"accepted", "new", "pending_new", "pending_replace"}:
            return WorkflowState.ACKED.value
        if normalized == "partially_filled":
            return WorkflowState.PARTIALLY_FILLED.value
        if normalized == "filled":
            return WorkflowState.FILLED.value
        if normalized in {"pending_cancel"}:
            return WorkflowState.CANCELING.value
        if normalized in {"canceled"}:
            return WorkflowState.CANCELED.value
        if normalized in {"done_for_day", "expired"}:
            return WorkflowState.EXPIRED.value
        if normalized in {"rejected", "suspended", "calculated"}:
            return WorkflowState.FAILED.value
        return WorkflowState.DRIFTED.value

    def _build_result(
        self,
        model: WorkflowRequestModel,
        local_before: str,
        status: ReconciliationStatus,
        reason: str,
        reconciled_at: datetime,
    ) -> ReconciliationResult:
        return ReconciliationResult(
            request_id=model.request_id,
            local_state_before=local_before,
            local_state_after=model.state,
            reconciliation_status=status,
            reconciliation_reason=reason,
            broker_order_id=model.broker_order_id,
            broker_status=model.broker_status,
            request_source=model.request_source,
            reconciled_at=reconciled_at,
        )

    def _to_summary(self, model: WorkflowRequestModel | None) -> WorkflowRequestSummary:
        if model is None:
            raise ValueError("Workflow request is required.")
        return WorkflowRequestSummary(
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
            reconciliation_status=model.reconciliation_status,
            reconciliation_reason=model.reconciliation_reason,
            last_reconciled_at=model.last_reconciled_at,
            is_terminal=self._is_terminal(model.state),
            is_cancelable=self._is_cancelable(model),
        )

    def _to_audit_response(self, model) -> AuditEventResponse:
        return AuditEventResponse(
            id=model.id,
            workflow_request_id=model.workflow_request_id,
            profile_id=model.profile_id,
            profile_version=model.profile_version,
            event_type=model.event_type,
            actor_type=model.actor_type,
            actor_id=model.actor_id,
            state=model.state,
            decision=model.decision,
            reason_code=model.reason_code,
            message=model.message,
            payload=model.payload,
            created_at=model.created_at,
        )

    def _persist_denial(
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

    def _is_terminal(self, state: str) -> bool:
        return state in {
            WorkflowState.REJECTED.value,
            WorkflowState.FAILED.value,
            WorkflowState.CANCELED.value,
            WorkflowState.FILLED.value,
            WorkflowState.EXPIRED.value,
        }

    def _is_cancelable(self, model: WorkflowRequestModel) -> bool:
        if not model.broker_order_id:
            return False
        return model.state in {
            WorkflowState.ACKED.value,
            WorkflowState.PARTIALLY_FILLED.value,
            WorkflowState.SUBMITTED.value,
            WorkflowState.SUBMITTING.value,
        }

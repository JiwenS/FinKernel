from __future__ import annotations

from datetime import datetime

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from .models import (
    AuditEventModel,
    DiscoverySessionModel,
    ProfileContextualRuleModel,
    ProfileDraftModel,
    ProfileLongMemoryModel,
    ProfileShortMemoryModel,
    ProfileVersionModel,
    StrategyModel,
    SuggestionModel,
    WorkflowRequestModel,
)


class WorkflowRepository:
    def get(self, session: Session, request_id: str) -> WorkflowRequestModel | None:
        return session.get(WorkflowRequestModel, request_id)

    def get_by_idempotency_key(self, session: Session, idempotency_key: str) -> WorkflowRequestModel | None:
        stmt = select(WorkflowRequestModel).where(WorkflowRequestModel.idempotency_key == idempotency_key)
        return session.execute(stmt).scalar_one_or_none()

    def add(self, session: Session, model: WorkflowRequestModel) -> WorkflowRequestModel:
        session.add(model)
        session.flush()
        session.refresh(model)
        return model

    def list_requests(
        self,
        session: Session,
        *,
        state: str | None = None,
        symbols: list[str] | None = None,
        account_ids: list[str] | None = None,
        created_from: datetime | None = None,
        created_to: datetime | None = None,
        limit: int = 50,
    ) -> tuple[list[WorkflowRequestModel], int]:
        stmt = select(WorkflowRequestModel)
        count_stmt = select(func.count()).select_from(WorkflowRequestModel)

        filters = []
        if state:
            filters.append(WorkflowRequestModel.state == state)
        if symbols:
            filters.append(WorkflowRequestModel.symbol.in_([symbol.upper() for symbol in symbols]))
        if account_ids:
            filters.append(WorkflowRequestModel.account_id.in_(account_ids))
        if created_from:
            filters.append(WorkflowRequestModel.created_at >= created_from)
        if created_to:
            filters.append(WorkflowRequestModel.created_at <= created_to)

        for condition in filters:
            stmt = stmt.where(condition)
            count_stmt = count_stmt.where(condition)

        stmt = stmt.order_by(WorkflowRequestModel.created_at.desc()).limit(limit)
        items = list(session.execute(stmt).scalars().all())
        total = int(session.execute(count_stmt).scalar_one())
        return items, total

    def list_inflight_requests(self, session: Session) -> list[WorkflowRequestModel]:
        inflight_states = ("SUBMITTING", "SUBMITTED", "CANCEL_REQUESTED", "CANCELING", "DRIFTED")
        stmt = (
            select(WorkflowRequestModel)
            .where(WorkflowRequestModel.state.in_(inflight_states))
            .order_by(WorkflowRequestModel.updated_at.desc())
        )
        return list(session.execute(stmt).scalars().all())

    def list_active_requests(self, session: Session) -> list[WorkflowRequestModel]:
        terminal_states = ("REJECTED", "FAILED", "CANCELED", "FILLED", "EXPIRED")
        stmt = (
            select(WorkflowRequestModel)
            .where(~WorkflowRequestModel.state.in_(terminal_states))
            .where(WorkflowRequestModel.broker_order_id.is_not(None))
            .order_by(WorkflowRequestModel.updated_at.desc())
        )
        return list(session.execute(stmt).scalars().all())


class AuditRepository:
    def add(self, session: Session, model: AuditEventModel) -> AuditEventModel:
        session.add(model)
        session.flush()
        return model

    def list_events(
        self,
        session: Session,
        *,
        workflow_request_id: str | None = None,
        event_type: str | None = None,
        account_ids: list[str] | None = None,
        symbols: list[str] | None = None,
        actor_id_for_unscoped_events: str | None = None,
        limit: int = 100,
    ) -> tuple[list[AuditEventModel], int]:
        stmt = select(AuditEventModel).outerjoin(
            WorkflowRequestModel,
            AuditEventModel.workflow_request_id == WorkflowRequestModel.request_id,
        )
        count_stmt = select(func.count()).select_from(AuditEventModel).outerjoin(
            WorkflowRequestModel,
            AuditEventModel.workflow_request_id == WorkflowRequestModel.request_id,
        )
        if workflow_request_id:
            stmt = stmt.where(AuditEventModel.workflow_request_id == workflow_request_id)
            count_stmt = count_stmt.where(AuditEventModel.workflow_request_id == workflow_request_id)
        if event_type:
            stmt = stmt.where(AuditEventModel.event_type == event_type)
            count_stmt = count_stmt.where(AuditEventModel.event_type == event_type)
        if account_ids or symbols or actor_id_for_unscoped_events:
            scoped_conditions = []
            request_scopes = []
            if account_ids:
                request_scopes.append(WorkflowRequestModel.account_id.in_(account_ids))
            if symbols:
                request_scopes.append(WorkflowRequestModel.symbol.in_([symbol.upper() for symbol in symbols]))
            if request_scopes:
                scoped_conditions.append((AuditEventModel.workflow_request_id.is_not(None)) & request_scopes[0])
                for condition in request_scopes[1:]:
                    scoped_conditions[-1] = scoped_conditions[-1] & condition
            if actor_id_for_unscoped_events:
                scoped_conditions.append(
                    (AuditEventModel.workflow_request_id.is_(None)) & (AuditEventModel.actor_id == actor_id_for_unscoped_events)
                )
            if scoped_conditions:
                scope_filter = scoped_conditions[0]
                for condition in scoped_conditions[1:]:
                    scope_filter = or_(scope_filter, condition)
                stmt = stmt.where(scope_filter)
                count_stmt = count_stmt.where(scope_filter)
        stmt = stmt.order_by(AuditEventModel.created_at.desc()).limit(limit)
        items = list(session.execute(stmt).scalars().all())
        total = int(session.execute(count_stmt).scalar_one())
        return items, total


class StrategyRepository:
    def add(self, session: Session, model: StrategyModel) -> StrategyModel:
        session.add(model)
        session.flush()
        session.refresh(model)
        return model

    def get(self, session: Session, strategy_id: str) -> StrategyModel | None:
        return session.get(StrategyModel, strategy_id)

    def list_for_profile(self, session: Session, profile_id: str, *, active_only: bool = False) -> list[StrategyModel]:
        stmt = select(StrategyModel).where(StrategyModel.profile_id == profile_id)
        if active_only:
            stmt = stmt.where(StrategyModel.active.is_(True))
        stmt = stmt.order_by(StrategyModel.created_at.desc())
        return list(session.execute(stmt).scalars().all())

    def list_active(self, session: Session) -> list[StrategyModel]:
        stmt = select(StrategyModel).where(StrategyModel.active.is_(True)).order_by(StrategyModel.created_at.asc())
        return list(session.execute(stmt).scalars().all())


class SuggestionRepository:
    def add(self, session: Session, model: SuggestionModel) -> SuggestionModel:
        session.add(model)
        session.flush()
        session.refresh(model)
        return model

    def get(self, session: Session, suggestion_id: str) -> SuggestionModel | None:
        return session.get(SuggestionModel, suggestion_id)

    def get_by_workflow_request_id(self, session: Session, workflow_request_id: str) -> SuggestionModel | None:
        stmt = select(SuggestionModel).where(SuggestionModel.workflow_request_id == workflow_request_id)
        return session.execute(stmt).scalar_one_or_none()

    def list_for_profile(
        self,
        session: Session,
        profile_id: str,
        *,
        status: str | None = None,
        limit: int = 100,
    ) -> list[SuggestionModel]:
        stmt = select(SuggestionModel).where(SuggestionModel.profile_id == profile_id)
        if status:
            stmt = stmt.where(SuggestionModel.status == status)
        stmt = stmt.order_by(SuggestionModel.created_at.desc()).limit(limit)
        return list(session.execute(stmt).scalars().all())

    def has_open_suggestion_for_strategy(self, session: Session, strategy_id: str) -> bool:
        stmt = select(func.count()).select_from(SuggestionModel).where(
            SuggestionModel.strategy_id == strategy_id,
            SuggestionModel.status.in_(["PENDING", "APPROVED"]),
        )
        return int(session.execute(stmt).scalar_one()) > 0


class ProfileVersionRepository:
    def add(self, session: Session, model: ProfileVersionModel) -> ProfileVersionModel:
        session.add(model)
        session.flush()
        session.refresh(model)
        return model

    def list_all(self, session: Session) -> list[ProfileVersionModel]:
        stmt = select(ProfileVersionModel).order_by(ProfileVersionModel.profile_id.asc(), ProfileVersionModel.version.desc())
        return list(session.execute(stmt).scalars().all())

    def list_for_profile(self, session: Session, profile_id: str) -> list[ProfileVersionModel]:
        stmt = (
            select(ProfileVersionModel)
            .where(ProfileVersionModel.profile_id == profile_id)
            .order_by(ProfileVersionModel.version.desc())
        )
        return list(session.execute(stmt).scalars().all())

    def list_active(self, session: Session, owner_id: str | None = None) -> list[ProfileVersionModel]:
        stmt = select(ProfileVersionModel).where(ProfileVersionModel.status == "active").order_by(ProfileVersionModel.profile_id.asc())
        if owner_id is not None:
            stmt = stmt.where(ProfileVersionModel.owner_id == owner_id)
        return list(session.execute(stmt).scalars().all())

    def count(self, session: Session) -> int:
        stmt = select(func.count()).select_from(ProfileVersionModel)
        return int(session.execute(stmt).scalar_one())


class ProfileContextualRuleRepository:
    def replace_for_profile_version(self, session: Session, profile_id: str, profile_version: int, items: list[ProfileContextualRuleModel]) -> None:
        stmt = select(ProfileContextualRuleModel).where(
            ProfileContextualRuleModel.profile_id == profile_id,
            ProfileContextualRuleModel.profile_version == profile_version,
        )
        for model in session.execute(stmt).scalars().all():
            session.delete(model)
        session.flush()
        for item in items:
            session.add(item)
        session.flush()

    def list_for_profile_version(self, session: Session, profile_id: str, profile_version: int) -> list[ProfileContextualRuleModel]:
        stmt = select(ProfileContextualRuleModel).where(
            ProfileContextualRuleModel.profile_id == profile_id,
            ProfileContextualRuleModel.profile_version == profile_version,
        ).order_by(ProfileContextualRuleModel.id.asc())
        return list(session.execute(stmt).scalars().all())


class ProfileLongMemoryRepository:
    def add(self, session: Session, model: ProfileLongMemoryModel) -> ProfileLongMemoryModel:
        session.add(model)
        session.flush()
        session.refresh(model)
        return model

    def replace_for_profile_version(self, session: Session, profile_id: str, profile_version: int, items: list[ProfileLongMemoryModel]) -> None:
        stmt = select(ProfileLongMemoryModel).where(
            ProfileLongMemoryModel.profile_id == profile_id,
            ProfileLongMemoryModel.profile_version == profile_version,
        )
        for model in session.execute(stmt).scalars().all():
            session.delete(model)
        session.flush()
        for item in items:
            session.add(item)
        session.flush()

    def list_for_profile_version(self, session: Session, profile_id: str, profile_version: int) -> list[ProfileLongMemoryModel]:
        stmt = select(ProfileLongMemoryModel).where(
            ProfileLongMemoryModel.profile_id == profile_id,
            ProfileLongMemoryModel.profile_version == profile_version,
        ).order_by(ProfileLongMemoryModel.id.asc())
        return list(session.execute(stmt).scalars().all())


class ProfileShortMemoryRepository:
    def add(self, session: Session, model: ProfileShortMemoryModel) -> ProfileShortMemoryModel:
        session.add(model)
        session.flush()
        session.refresh(model)
        return model

    def replace_for_profile_version(self, session: Session, profile_id: str, profile_version: int, items: list[ProfileShortMemoryModel]) -> None:
        stmt = select(ProfileShortMemoryModel).where(
            ProfileShortMemoryModel.profile_id == profile_id,
            ProfileShortMemoryModel.profile_version == profile_version,
        )
        for model in session.execute(stmt).scalars().all():
            session.delete(model)
        session.flush()
        for item in items:
            session.add(item)
        session.flush()

    def list_for_profile_version(self, session: Session, profile_id: str, profile_version: int) -> list[ProfileShortMemoryModel]:
        stmt = select(ProfileShortMemoryModel).where(
            ProfileShortMemoryModel.profile_id == profile_id,
            ProfileShortMemoryModel.profile_version == profile_version,
        ).order_by(ProfileShortMemoryModel.id.asc())
        return list(session.execute(stmt).scalars().all())


class DiscoverySessionRepository:
    def upsert(self, session: Session, session_model: DiscoverySessionModel) -> DiscoverySessionModel:
        existing = session.get(DiscoverySessionModel, session_model.session_id)
        if existing is None:
            session.add(session_model)
            session.flush()
            return session_model
        existing.owner_id = session_model.owner_id
        existing.status = session_model.status
        existing.payload = session_model.payload
        session.flush()
        return existing

    def get(self, session: Session, session_id: str) -> DiscoverySessionModel | None:
        return session.get(DiscoverySessionModel, session_id)


class ProfileDraftRepository:
    def upsert(self, session: Session, model: ProfileDraftModel) -> ProfileDraftModel:
        existing = session.get(ProfileDraftModel, model.draft_id)
        if existing is None:
            session.add(model)
            session.flush()
            return model
        existing.session_id = model.session_id
        existing.owner_id = model.owner_id
        existing.payload = model.payload
        session.flush()
        return existing

    def get(self, session: Session, draft_id: str) -> ProfileDraftModel | None:
        return session.get(ProfileDraftModel, draft_id)

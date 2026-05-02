from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .models import (
    DiscoveryConversationTurnModel,
    DiscoveryInterpretationModel,
    DiscoverySessionModel,
    ProfileContextualRuleModel,
    ProfileDraftModel,
    ProfileLongMemoryModel,
    ProfileShortMemoryModel,
    ProfileVersionModel,
)


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
        stmt = select(ProfileVersionModel).where(ProfileVersionModel.profile_id == profile_id).order_by(ProfileVersionModel.version.desc())
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

    def list_for_owner(self, session: Session, owner_id: str, *, statuses: list[str] | None = None) -> list[DiscoverySessionModel]:
        stmt = select(DiscoverySessionModel).where(DiscoverySessionModel.owner_id == owner_id)
        if statuses:
            stmt = stmt.where(DiscoverySessionModel.status.in_(statuses))
        stmt = stmt.order_by(DiscoverySessionModel.updated_at.desc(), DiscoverySessionModel.created_at.desc())
        return list(session.execute(stmt).scalars().all())


class DiscoveryConversationTurnRepository:
    def add(self, session: Session, model: DiscoveryConversationTurnModel) -> DiscoveryConversationTurnModel:
        session.add(model)
        session.flush()
        return model

    def list_for_session(self, session: Session, session_id: str) -> list[DiscoveryConversationTurnModel]:
        stmt = select(DiscoveryConversationTurnModel).where(
            DiscoveryConversationTurnModel.session_id == session_id
        ).order_by(DiscoveryConversationTurnModel.answered_at.asc(), DiscoveryConversationTurnModel.created_at.asc())
        return list(session.execute(stmt).scalars().all())


class DiscoveryInterpretationRepository:
    def add(self, session: Session, model: DiscoveryInterpretationModel) -> DiscoveryInterpretationModel:
        session.add(model)
        session.flush()
        return model

    def list_for_session(self, session: Session, session_id: str) -> list[DiscoveryInterpretationModel]:
        stmt = select(DiscoveryInterpretationModel).where(
            DiscoveryInterpretationModel.session_id == session_id
        ).order_by(DiscoveryInterpretationModel.stored_at.asc(), DiscoveryInterpretationModel.created_at.asc())
        return list(session.execute(stmt).scalars().all())


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

    def list_for_session(self, session: Session, session_id: str) -> list[ProfileDraftModel]:
        stmt = select(ProfileDraftModel).where(ProfileDraftModel.session_id == session_id).order_by(ProfileDraftModel.updated_at.desc(), ProfileDraftModel.created_at.desc())
        return list(session.execute(stmt).scalars().all())

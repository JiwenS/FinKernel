from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy.orm import Session

from finkernel.storage.models import AuditEventModel
from finkernel.storage.repositories import AuditRepository


class AuditService:
    def __init__(self, repository: AuditRepository | None = None) -> None:
        self.repository = repository or AuditRepository()

    def record(
        self,
        session: Session,
        *,
        workflow_request_id: str | None,
        profile_id: str | None = None,
        profile_version: int | None = None,
        event_type: str,
        actor_type: str,
        actor_id: str | None,
        message: str,
        state: str | None = None,
        decision: str | None = None,
        reason_code: str | None = None,
        payload: dict | None = None,
    ) -> None:
        event = AuditEventModel(
            workflow_request_id=workflow_request_id,
            profile_id=profile_id,
            profile_version=profile_version,
            event_type=event_type,
            actor_type=actor_type,
            actor_id=actor_id,
            state=state,
            decision=decision,
            reason_code=reason_code,
            message=message,
            payload=payload,
            created_at=datetime.now(timezone.utc),
        )
        self.repository.add(session, event)

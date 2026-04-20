from __future__ import annotations

from collections.abc import Generator
from contextlib import contextmanager

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker
from sqlalchemy.pool import StaticPool

from finkernel.config import Settings


class Base(DeclarativeBase):
    pass


def build_engine(settings: Settings):
    connect_args: dict[str, object] = {}
    kwargs: dict[str, object] = {"future": True}
    if settings.database_url.startswith("sqlite"):
        connect_args["check_same_thread"] = False
        if ":memory:" in settings.database_url:
            kwargs["poolclass"] = StaticPool
    return create_engine(settings.database_url, connect_args=connect_args, **kwargs)


def build_session_factory(settings: Settings) -> sessionmaker[Session]:
    engine = build_engine(settings)
    return sessionmaker(bind=engine, expire_on_commit=False, autoflush=False, future=True)


def init_database(session_factory: sessionmaker[Session], settings: Settings) -> None:
    from .models import Base as ModelBase

    engine = session_factory.kw["bind"]
    if settings.enable_pgvector and engine.dialect.name == "postgresql":
        with engine.begin() as connection:
            connection.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
    ModelBase.metadata.create_all(bind=engine)
    _apply_lightweight_migrations(engine)


def _apply_lightweight_migrations(engine) -> None:
    inspector = inspect(engine)
    migrations = {
        "workflow_requests": {
            "owner_id": "VARCHAR(64)",
            "profile_id": "VARCHAR(64)",
            "profile_version": "INTEGER",
            "reconciliation_status": "VARCHAR(32)",
            "reconciliation_reason": "TEXT",
            "last_reconciled_at": "TIMESTAMP",
        },
        "strategies": {
            "profile_version": "INTEGER DEFAULT 1",
        },
        "suggestions": {
            "profile_version": "INTEGER DEFAULT 1",
        },
        "audit_events": {
            "profile_id": "VARCHAR(64)",
            "profile_version": "INTEGER",
        },
        "profile_versions": {
            "display_name": "VARCHAR(128)",
            "mandate_summary": "TEXT",
            "persona_style": "VARCHAR(128)",
            "created_from": "VARCHAR(64)",
            "bucket_name": "VARCHAR(128)",
            "supersedes_profile_version": "INTEGER",
            "risk_budget": "VARCHAR(32)",
            "capital_allocation_pct": "NUMERIC(10, 6)",
            "allowed_accounts": "JSON",
            "allowed_markets": "JSON",
            "allowed_symbols": "JSON",
            "forbidden_symbols": "JSON",
            "allowed_actions": "JSON",
            "hitl_required_actions": "JSON",
            "objective_text": "TEXT",
            "horizon_text": "TEXT",
            "liquidity_text": "TEXT",
            "stress_response_text": "TEXT",
            "loss_threshold_text": "TEXT",
            "constraints_text": "TEXT",
            "concentration_text": "TEXT",
            "interaction_style_text": "TEXT",
            "review_cadence_text": "TEXT",
        },
    }
    statements: list[str] = []
    for table_name, additions in migrations.items():
        existing = {column["name"] for column in inspector.get_columns(table_name)}
        statements.extend(
            f"ALTER TABLE {table_name} ADD COLUMN {name} {column_type}"
            for name, column_type in additions.items()
            if name not in existing
        )
    if not statements:
        return
    with engine.begin() as connection:
        for statement in statements:
            connection.execute(text(statement))


@contextmanager
def session_scope(session_factory: sessionmaker[Session]) -> Generator[Session, None, None]:
    session = session_factory()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def check_database(session_factory: sessionmaker[Session]) -> bool:
    with session_scope(session_factory) as session:
        session.execute(text("SELECT 1"))
    return True

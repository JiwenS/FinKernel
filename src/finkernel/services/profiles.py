from __future__ import annotations

from contextlib import contextmanager
from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation
import json
from pathlib import Path
import re
from typing import Iterator

from sqlalchemy.orm import Session, sessionmaker

from finkernel.config import Settings
from finkernel.schemas.profile import (
    AccountBackground,
    AccountEntityType,
    DistilledProfileMemoryResponse,
    ExecutionMode,
    FinancialObjectives,
    InvestmentConstraints,
    LiquidityFrequency,
    MemoryKind,
    PersonaProfile,
    PersonaTraits,
    ProfileLifecycleStatus,
    ProfileOnboardingStatus,
    RiskBoundaries,
)
from finkernel.storage.models import ProfileContextualRuleModel, ProfileLongMemoryModel, ProfileShortMemoryModel, ProfileVersionModel
from finkernel.storage.repositories import (
    ProfileContextualRuleRepository,
    ProfileLongMemoryRepository,
    ProfileShortMemoryRepository,
    ProfileVersionRepository,
)


class ProfileOnboardingRequiredError(LookupError):
    reason_code = "PROFILE_ONBOARDING_REQUIRED"

    def __init__(self, *, owner_id: str | None = None, profile_id: str | None = None) -> None:
        self.owner_id = owner_id
        self.profile_id = profile_id
        target = f" for owner {owner_id}" if owner_id else ""
        requested = f" Requested profile_id={profile_id}." if profile_id else ""
        super().__init__(f"No active profile exists{target}. Start profile onboarding before using profile-bound flows.{requested}")

    def to_detail(self) -> dict[str, str]:
        detail = {"reason_code": self.reason_code, "message": str(self)}
        if self.owner_id:
            detail["owner_id"] = self.owner_id
        if self.profile_id:
            detail["profile_id"] = self.profile_id
        return detail


class InactiveProfileError(LookupError):
    reason_code = "PROFILE_NOT_ACTIVE"

    def __init__(self, profile_id: str) -> None:
        self.profile_id = profile_id
        super().__init__(f"Profile {profile_id} exists but is not active. Complete onboarding or review before using profile-bound flows.")

    def to_detail(self) -> dict[str, str]:
        return {"reason_code": self.reason_code, "message": str(self), "profile_id": self.profile_id}


class ProfileStore:
    def __init__(
        self,
        settings: Settings,
        *,
        session_factory: sessionmaker[Session],
        repository: ProfileVersionRepository | None = None,
        contextual_rule_repository: ProfileContextualRuleRepository | None = None,
        long_memory_repository: ProfileLongMemoryRepository | None = None,
        short_memory_repository: ProfileShortMemoryRepository | None = None,
    ) -> None:
        self.settings = settings
        self.session_factory = session_factory
        self.repository = repository or ProfileVersionRepository()
        self.contextual_rule_repository = contextual_rule_repository or ProfileContextualRuleRepository()
        self.long_memory_repository = long_memory_repository or ProfileLongMemoryRepository()
        self.short_memory_repository = short_memory_repository or ProfileShortMemoryRepository()

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

    def _path(self) -> Path:
        return Path(self.settings.profile_store_path)

    def load_all_versions(self) -> list[PersonaProfile]:
        with self._session_scope() as session:
            return [self._from_model(session, model) for model in self.repository.list_all(session)]

    def save_all_versions(self, profiles: list[PersonaProfile]) -> None:
        with self._session_scope() as session:
            existing = self.repository.list_all(session)
            for model in existing:
                session.delete(model)
            session.flush()
            for profile in profiles:
                self.repository.add(session, self._to_model(profile))

    def load_all(self) -> dict[str, PersonaProfile]:
        resolved: dict[str, PersonaProfile] = {}
        for profile in self.load_all_versions():
            existing = resolved.get(profile.profile_id)
            if existing is None or self._prefer(profile, existing):
                resolved[profile.profile_id] = profile
        return resolved

    def list_active(self, *, owner_id: str | None = None) -> list[PersonaProfile]:
        profiles = [profile for profile in self.load_all_versions() if profile.is_active]
        if owner_id is not None:
            profiles = [profile for profile in profiles if profile.owner_id == owner_id]
        return sorted(profiles, key=lambda profile: (profile.profile_id, profile.version))

    def ensure_active_profiles_exist(self, *, owner_id: str | None = None) -> None:
        if not self.list_active(owner_id=owner_id):
            raise ProfileOnboardingRequiredError(owner_id=owner_id)

    def get_onboarding_status(self, *, owner_id: str | None = None) -> ProfileOnboardingStatus:
        profiles = self.load_all_versions()
        if owner_id is not None:
            profiles = [profile for profile in profiles if profile.owner_id == owner_id]
        active_profiles = [profile for profile in profiles if profile.is_active]
        return ProfileOnboardingStatus(
            owner_id=owner_id,
            onboarding_required=not active_profiles,
            total_profile_count=len(profiles),
            active_profile_count=len(active_profiles),
            active_profile_ids=[profile.profile_id for profile in active_profiles],
            available_profile_ids=sorted({profile.profile_id for profile in profiles}),
            next_step="start_profile_discovery" if not active_profiles else "use_active_profile",
        )

    def get(self, profile_id: str, *, version: int | None = None, require_active: bool = True) -> PersonaProfile:
        profiles = [profile for profile in self.load_all_versions() if profile.profile_id == profile_id]
        if not profiles:
            if require_active and not self.list_active():
                raise ProfileOnboardingRequiredError(profile_id=profile_id)
            raise KeyError(f"Unknown profile_id: {profile_id}")

        if version is not None:
            for profile in profiles:
                if profile.version == version:
                    if require_active and not profile.is_active:
                        raise InactiveProfileError(profile_id)
                    return profile
            raise KeyError(f"Unknown profile version: {profile_id}@v{version}")

        active_profiles = [profile for profile in profiles if profile.is_active]
        if require_active and not active_profiles:
            raise InactiveProfileError(profile_id)
        candidates = active_profiles if active_profiles else profiles
        return max(candidates, key=lambda profile: profile.version)

    def list_versions(self, profile_id: str) -> list[PersonaProfile]:
        profiles = [profile for profile in self.load_all_versions() if profile.profile_id == profile_id]
        if not profiles:
            raise KeyError(f"Unknown profile_id: {profile_id}")
        return sorted(profiles, key=lambda profile: profile.version, reverse=True)

    def append_profile(self, profile: PersonaProfile) -> None:
        with self._session_scope() as session:
            for existing in self.repository.list_for_profile(session, profile.profile_id):
                existing_status = existing.status or (existing.payload or {}).get("status")
                if existing_status == ProfileLifecycleStatus.ACTIVE.value:
                    existing.status = ProfileLifecycleStatus.SUPERSEDED.value
                    if existing.payload:
                        existing.payload["status"] = ProfileLifecycleStatus.SUPERSEDED.value
            stored = self.repository.add(session, self._to_model(profile))
            self._replace_related_content(session, profile, stored.version)

    def save_persona_markdown(self, *, profile_id: str, persona_markdown: str, version: int | None = None) -> PersonaProfile:
        with self._session_scope() as session:
            versions = self.repository.list_for_profile(session, profile_id)
            if not versions:
                raise KeyError(f"Unknown profile_id: {profile_id}")
            if version is not None:
                target_model = next((model for model in versions if model.version == version), None)
                if target_model is None:
                    raise KeyError(f"Unknown profile version: {profile_id}@v{version}")
            else:
                active_versions = [model for model in versions if model.status == ProfileLifecycleStatus.ACTIVE.value]
                target_model = active_versions[0] if active_versions else versions[0]
            payload = dict(target_model.payload or {})
            payload["persona_markdown"] = persona_markdown
            target_model.payload = payload
            session.flush()
            return self._from_model(session, target_model)

    def append_memory(
        self,
        *,
        profile_id: str,
        memory_kind: MemoryKind,
        theme: str,
        content_text: str,
        source_dimension: str | None = None,
        expires_at: datetime | None = None,
    ) -> PersonaProfile:
        with self._session_scope() as session:
            versions = self.repository.list_for_profile(session, profile_id)
            active_model = next((model for model in versions if model.status == ProfileLifecycleStatus.ACTIVE.value), None)
            if active_model is None:
                raise InactiveProfileError(profile_id)
            if memory_kind is MemoryKind.LONG_TERM:
                self.long_memory_repository.add(
                    session,
                    ProfileLongMemoryModel(
                        profile_id=profile_id,
                        profile_version=active_model.version,
                        theme=theme,
                        content_text=content_text,
                        source_dimension=source_dimension,
                        last_confirmed_at=datetime.now(UTC),
                    ),
                )
            else:
                self.short_memory_repository.add(
                    session,
                    ProfileShortMemoryModel(
                        profile_id=profile_id,
                        profile_version=active_model.version,
                        theme=theme,
                        content_text=content_text,
                        source_dimension=source_dimension,
                        expires_at=expires_at,
                    ),
                )
            session.flush()
            return self._from_model(session, active_model)

    def search_memory(
        self,
        *,
        profile_id: str,
        query: str,
        memory_kind: MemoryKind | None = None,
        include_expired: bool = False,
    ) -> list[dict]:
        needle = query.lower().strip()
        if not needle:
            return []
        profile = self.get(profile_id, require_active=False)
        items: list[dict] = []
        if memory_kind in (None, MemoryKind.LONG_TERM):
            for item in profile.long_term_memories:
                haystack = f"{item.get('theme', '')} {item.get('summary', '')}".lower()
                if needle in haystack:
                    items.append({"memory_kind": MemoryKind.LONG_TERM.value, **item})
        if memory_kind in (None, MemoryKind.SHORT_TERM):
            for item in self._active_or_all_short_memories(profile.short_term_memories, include_expired=include_expired):
                haystack = f"{item.get('theme', '')} {item.get('summary', '')}".lower()
                if needle in haystack:
                    items.append({"memory_kind": MemoryKind.SHORT_TERM.value, **item})
        return items

    def distill_memory(self, *, profile_id: str) -> DistilledProfileMemoryResponse:
        profile = self.get(profile_id, require_active=False)
        long_summary = [
            f"{item.get('theme')}: {item.get('summary')}"
            for item in profile.long_term_memories[:5]
            if item.get("summary")
        ]
        short_summary = [
            f"{item.get('theme')}: {item.get('summary')}"
            for item in self._active_or_all_short_memories(profile.short_term_memories, include_expired=False)[:5]
            if item.get("summary")
        ]
        return DistilledProfileMemoryResponse(
            profile_id=profile.profile_id,
            version=profile.version,
            long_term_summary=long_summary,
            short_term_summary=short_summary,
        )

    def bootstrap_from_seed(self) -> None:
        with self._session_scope() as session:
            if self.repository.count(session) > 0:
                return
            for profile in self._load_seed_profiles():
                stored = self.repository.add(session, self._to_model(profile))
                self._replace_related_content(session, profile, stored.version)

    def _prefer(self, candidate: PersonaProfile, existing: PersonaProfile) -> bool:
        if candidate.is_active != existing.is_active:
            return candidate.is_active
        return candidate.version > existing.version

    def _load_seed_profiles(self) -> list[PersonaProfile]:
        path = self._path()
        if not path.exists():
            return []
        data = json.loads(path.read_text(encoding="utf-8"))
        return [PersonaProfile.model_validate(item) for item in data.get("profiles", [])]

    def _to_model(self, profile: PersonaProfile) -> ProfileVersionModel:
        return ProfileVersionModel(
            profile_id=profile.profile_id,
            owner_id=profile.owner_id,
            version=profile.version,
            status=profile.status.value,
            display_name=profile.display_name,
            mandate_summary=profile.mandate_summary,
            persona_style=profile.persona_style,
            created_from=profile.created_from,
            supersedes_profile_version=profile.supersedes_profile_version,
            risk_budget=profile.risk_budget.value,
            forbidden_symbols=profile.investment_constraints.blocked_tickers,
            target_annual_return_pct=self._decimal_to_storage(profile.financial_objectives.target_annual_return_pct),
            investment_horizon_years=profile.financial_objectives.investment_horizon_years,
            annual_liquidity_need=self._decimal_to_storage(profile.financial_objectives.annual_liquidity_need),
            liquidity_frequency=profile.financial_objectives.liquidity_frequency.value if profile.financial_objectives.liquidity_frequency else None,
            max_drawdown_limit_pct=self._decimal_to_storage(profile.risk_boundaries.max_drawdown_limit_pct),
            max_annual_volatility_pct=self._decimal_to_storage(profile.risk_boundaries.max_annual_volatility_pct),
            max_leverage_ratio=self._decimal_to_storage(profile.risk_boundaries.max_leverage_ratio),
            single_asset_cap_pct=self._decimal_to_storage(profile.risk_boundaries.single_asset_cap_pct),
            blocked_sectors=profile.investment_constraints.blocked_sectors,
            blocked_tickers=profile.investment_constraints.blocked_tickers,
            base_currency=profile.investment_constraints.base_currency,
            tax_residency=profile.investment_constraints.tax_residency,
            account_entity_type=profile.account_background.account_entity_type.value if profile.account_background.account_entity_type else None,
            aum_allocated=self._decimal_to_storage(profile.account_background.aum_allocated),
            execution_mode=profile.account_background.execution_mode.value if profile.account_background.execution_mode else None,
            financial_literacy_text=profile.persona_traits.financial_literacy,
            wealth_origin_dna_text=profile.persona_traits.wealth_origin_dna,
            behavioral_risk_profile_text=profile.persona_traits.behavioral_risk_profile,
            payload={
                "persona_evidence": profile.persona_evidence,
                "persona_markdown": profile.persona_markdown,
            },
        )

    def _from_model(self, session: Session, model: ProfileVersionModel) -> PersonaProfile:
        payload = model.payload or {}
        contextual_rules = [
            {"rule_text": item.rule_text, "reason": item.reason_text, "confidence": item.confidence}
            for item in self.contextual_rule_repository.list_for_profile_version(session, model.profile_id, model.version)
        ]
        long_term_memories = [
            {
                "theme": item.theme,
                "summary": item.content_text,
                "source_dimension": item.source_dimension,
                "last_confirmed_at": item.last_confirmed_at.isoformat() if item.last_confirmed_at else None,
            }
            for item in self.long_memory_repository.list_for_profile_version(session, model.profile_id, model.version)
        ]
        short_term_memories = [
            {
                "theme": item.theme,
                "summary": item.content_text,
                "source_dimension": item.source_dimension,
                "effective_from": item.effective_from.isoformat(),
                "expires_at": item.expires_at.isoformat() if item.expires_at else None,
            }
            for item in self.short_memory_repository.list_for_profile_version(session, model.profile_id, model.version)
        ]
        short_term_memories = self._active_or_all_short_memories(short_term_memories, include_expired=False)
        legacy_hard_rules = payload.get("hard_rules", {})
        return PersonaProfile(
            profile_id=model.profile_id,
            owner_id=model.owner_id,
            version=model.version,
            status=ProfileLifecycleStatus(model.status or payload.get("status", ProfileLifecycleStatus.ACTIVE.value)),
            display_name=model.display_name or payload.get("display_name") or model.profile_id,
            mandate_summary=model.mandate_summary or payload.get("mandate_summary") or "",
            persona_style=model.persona_style or payload.get("persona_style") or "default",
            created_from=model.created_from or payload.get("created_from"),
            supersedes_profile_version=model.supersedes_profile_version or payload.get("supersedes_profile_version"),
            risk_budget=model.risk_budget or payload.get("risk_budget") or "medium",
            financial_objectives=FinancialObjectives(
                target_annual_return_pct=self._storage_to_decimal(model.target_annual_return_pct),
                investment_horizon_years=model.investment_horizon_years or self._coerce_int(legacy_hard_rules.get("financial_objectives", {}).get("time_horizon")),
                annual_liquidity_need=self._storage_to_decimal(model.annual_liquidity_need),
                liquidity_frequency=self._coerce_liquidity_frequency(model.liquidity_frequency),
            ),
            risk_boundaries=RiskBoundaries(
                max_drawdown_limit_pct=self._storage_to_decimal(model.max_drawdown_limit_pct),
                max_annual_volatility_pct=self._storage_to_decimal(model.max_annual_volatility_pct),
                max_leverage_ratio=self._storage_to_decimal(model.max_leverage_ratio),
                single_asset_cap_pct=self._storage_to_decimal(model.single_asset_cap_pct),
            ),
            investment_constraints=InvestmentConstraints(
                blocked_sectors=model.blocked_sectors or [],
                blocked_tickers=model.blocked_tickers or model.forbidden_symbols or payload.get("forbidden_symbols") or [],
                base_currency=model.base_currency,
                tax_residency=model.tax_residency,
            ),
            account_background=AccountBackground(
                account_entity_type=AccountEntityType(model.account_entity_type) if model.account_entity_type else None,
                aum_allocated=self._storage_to_decimal(model.aum_allocated),
                execution_mode=ExecutionMode(model.execution_mode) if model.execution_mode else None,
            ),
            persona_traits=PersonaTraits(
                financial_literacy=model.financial_literacy_text,
                wealth_origin_dna=model.wealth_origin_dna_text,
                behavioral_risk_profile=model.behavioral_risk_profile_text or model.stress_response_text,
            ),
            contextual_rules=contextual_rules,
            long_term_memories=long_term_memories,
            short_term_memories=short_term_memories,
            persona_evidence=payload.get("persona_evidence") or [],
            persona_markdown=payload.get("persona_markdown"),
        )

    def _replace_related_content(self, session: Session, profile: PersonaProfile, profile_version: int) -> None:
        self.contextual_rule_repository.replace_for_profile_version(
            session,
            profile.profile_id,
            profile_version,
            [
                ProfileContextualRuleModel(
                    profile_id=profile.profile_id,
                    profile_version=profile_version,
                    rule_text=item.get("rule_text") or item.get("rule") or "",
                    reason_text=item.get("reason"),
                    confidence=item.get("confidence"),
                )
                for item in profile.contextual_rules
                if item.get("rule_text") or item.get("rule")
            ],
        )
        self.long_memory_repository.replace_for_profile_version(
            session,
            profile.profile_id,
            profile_version,
            [
                ProfileLongMemoryModel(
                    profile_id=profile.profile_id,
                    profile_version=profile_version,
                    theme=item.get("theme"),
                    content_text=item.get("summary") or item.get("content_text") or "",
                    source_dimension=item.get("source_dimension"),
                    last_confirmed_at=datetime.now(UTC),
                )
                for item in profile.long_term_memories
                if item.get("summary") or item.get("content_text")
            ],
        )
        self.short_memory_repository.replace_for_profile_version(
            session,
            profile.profile_id,
            profile_version,
            [
                ProfileShortMemoryModel(
                    profile_id=profile.profile_id,
                    profile_version=profile_version,
                    theme=item.get("theme"),
                    content_text=item.get("summary") or item.get("content_text") or "",
                    source_dimension=item.get("source_dimension"),
                    expires_at=self._parse_datetime(item.get("expires_at")),
                )
                for item in profile.short_term_memories
                if item.get("summary") or item.get("content_text")
            ],
        )

    def _active_or_all_short_memories(self, items: list[dict], *, include_expired: bool) -> list[dict]:
        if include_expired:
            return items
        now = datetime.now(UTC)
        active_items: list[dict] = []
        for item in items:
            expires_at = self._parse_datetime(item.get("expires_at"))
            if expires_at is None or expires_at >= now:
                active_items.append(item)
        return active_items

    def _parse_datetime(self, value) -> datetime | None:
        if value in (None, ""):
            return None
        if isinstance(value, datetime):
            parsed = value
        else:
            parsed = datetime.fromisoformat(str(value))
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=UTC)
        return parsed

    def _decimal_to_storage(self, value: Decimal | None):
        if value is None:
            return None
        return float(value)

    def _storage_to_decimal(self, value) -> Decimal | None:
        if value in (None, ""):
            return None
        try:
            return Decimal(str(value))
        except (InvalidOperation, ValueError):
            return None

    def _coerce_int(self, value) -> int | None:
        if value in (None, ""):
            return None
        match = None
        if isinstance(value, str):
            match = re.search(r"(\d+)", value)
        if match is not None:
            return int(match.group(1))
        try:
            return int(value)
        except (TypeError, ValueError):
            return None

    def _coerce_liquidity_frequency(self, value: str | None) -> LiquidityFrequency | None:
        if not value:
            return None
        try:
            return LiquidityFrequency(value)
        except ValueError:
            return None

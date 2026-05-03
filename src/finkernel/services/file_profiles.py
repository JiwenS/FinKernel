from __future__ import annotations

from datetime import UTC, datetime
import json
from pathlib import Path
import re

from finkernel.config import Settings
from finkernel.schemas.profile import (
    DistilledProfileMemoryResponse,
    MemoryKind,
    PersonaProfile,
    ProfileLifecycleStatus,
    ProfileOnboardingStatus,
)
from finkernel.services.profiles import InactiveProfileError, ProfileOnboardingRequiredError
from finkernel.storage.files import ensure_directory, read_json, write_json_atomic


class FileProfileStore:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.root = Path(settings.profile_data_dir)

    def load_all_versions(self) -> list[PersonaProfile]:
        profiles: list[PersonaProfile] = []
        for path in sorted(self._profiles_root().glob("*/versions/v*/profile.json")):
            profiles.append(PersonaProfile.model_validate(read_json(path, default={})))
        return profiles

    def save_all_versions(self, profiles: list[PersonaProfile]) -> None:
        for profile in profiles:
            self._write_profile_version(profile)
        self._write_index()

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
        for existing in self.list_versions(profile.profile_id) if self._profile_dir(profile.profile_id).exists() else []:
            if existing.is_active:
                superseded = existing.model_copy(update={"status": ProfileLifecycleStatus.SUPERSEDED})
                self._write_profile_version(superseded)
        self._write_profile_version(profile)
        self._write_index()

    def save_persona_markdown(self, *, profile_id: str, persona_markdown: str, version: int | None = None) -> PersonaProfile:
        versions = self.list_versions(profile_id)
        if version is not None:
            target = next((profile for profile in versions if profile.version == version), None)
            if target is None:
                raise KeyError(f"Unknown profile version: {profile_id}@v{version}")
        else:
            active = [profile for profile in versions if profile.is_active]
            target = active[0] if active else versions[0]
        updated = target.model_copy(update={"persona_markdown": persona_markdown})
        self._write_profile_version(updated)
        self._write_index()
        return updated

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
        profile = self.get(profile_id)
        item = {
            "theme": theme,
            "summary": content_text,
            "source_dimension": source_dimension,
        }
        if memory_kind is MemoryKind.LONG_TERM:
            item["last_confirmed_at"] = datetime.now(UTC).isoformat()
            updated = profile.model_copy(update={"long_term_memories": [*profile.long_term_memories, item]})
        else:
            item["effective_from"] = datetime.now(UTC).isoformat()
            item["expires_at"] = expires_at.isoformat() if expires_at else None
            updated = profile.model_copy(update={"short_term_memories": [*profile.short_term_memories, item]})
        self._write_profile_version(updated)
        return updated

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
                if needle in f"{item.get('theme', '')} {item.get('summary', '')}".lower():
                    items.append({"memory_kind": MemoryKind.LONG_TERM.value, **item})
        if memory_kind in (None, MemoryKind.SHORT_TERM):
            for item in self._active_or_all_short_memories(profile.short_term_memories, include_expired=include_expired):
                if needle in f"{item.get('theme', '')} {item.get('summary', '')}".lower():
                    items.append({"memory_kind": MemoryKind.SHORT_TERM.value, **item})
        return items

    def distill_memory(self, *, profile_id: str) -> DistilledProfileMemoryResponse:
        profile = self.get(profile_id, require_active=False)
        return DistilledProfileMemoryResponse(
            profile_id=profile.profile_id,
            version=profile.version,
            long_term_summary=[
                f"{item.get('theme')}: {item.get('summary')}"
                for item in profile.long_term_memories[:5]
                if item.get("summary")
            ],
            short_term_summary=[
                f"{item.get('theme')}: {item.get('summary')}"
                for item in self._active_or_all_short_memories(profile.short_term_memories, include_expired=False)[:5]
                if item.get("summary")
            ],
        )

    def bootstrap_from_seed(self) -> None:
        if self.load_all_versions():
            return
        path = Path(self.settings.profile_store_path)
        if not path.exists():
            self._write_index()
            return
        data = json.loads(path.read_text(encoding="utf-8"))
        self.save_all_versions([PersonaProfile.model_validate(item) for item in data.get("profiles", [])])

    def check(self) -> bool:
        ensure_directory(self.root)
        probe = self.root / ".write-test"
        probe.write_text("ok", encoding="utf-8")
        probe.unlink(missing_ok=True)
        return True

    def _profiles_root(self) -> Path:
        return self.root / "profiles"

    def _profile_dir(self, profile_id: str) -> Path:
        return self._profiles_root() / self._safe_name(profile_id)

    def _version_dir(self, profile: PersonaProfile) -> Path:
        return self._profile_dir(profile.profile_id) / "versions" / f"v{profile.version:03d}"

    def _write_profile_version(self, profile: PersonaProfile) -> None:
        version_dir = self._version_dir(profile)
        write_json_atomic(version_dir / "profile.json", profile.model_dump(mode="json"))
        write_json_atomic(version_dir / "profile_sources.json", self._source_payload(profile))
        write_json_atomic(version_dir / "profile_context_pack.json", self._context_pack(profile))
        if profile.persona_markdown:
            self._write_text_atomic(version_dir / "profile.md", profile.persona_markdown)
            self._write_text_atomic(version_dir / "profile_context_pack.md", self._context_pack_markdown(profile))
        if profile.is_active:
            write_json_atomic(
                self._profile_dir(profile.profile_id) / "active.json",
                {
                    "profile_id": profile.profile_id,
                    "version": profile.version,
                    "path": str((version_dir / "profile.json").as_posix()),
                },
            )

    def _write_index(self) -> None:
        profiles = self.load_all_versions()
        write_json_atomic(
            self.root / "profiles-index.json",
            {
                "schema_version": 1,
                "profiles": [
                    {
                        "profile_id": profile.profile_id,
                        "owner_id": profile.owner_id,
                        "version": profile.version,
                        "status": profile.status.value,
                        "display_name": profile.display_name,
                    }
                    for profile in sorted(profiles, key=lambda item: (item.profile_id, item.version))
                ],
            },
        )

    def _source_payload(self, profile: PersonaProfile) -> dict:
        return {
            "schema_version": 1,
            "profile_id": profile.profile_id,
            "version": profile.version,
            "persona_evidence": profile.persona_evidence,
            "contextual_rules": profile.contextual_rules,
            "long_term_memories": profile.long_term_memories,
            "short_term_memories": profile.short_term_memories,
        }

    def _context_pack(self, profile: PersonaProfile) -> dict:
        return {
            "schema_version": 1,
            "profile_id": profile.profile_id,
            "version": profile.version,
            "display_name": profile.display_name,
            "mandate_summary": profile.mandate_summary,
            "risk_budget": profile.risk_budget.value,
            "financial_objectives": profile.financial_objectives.model_dump(mode="json"),
            "risk_boundaries": profile.risk_boundaries.model_dump(mode="json"),
            "investment_constraints": profile.investment_constraints.model_dump(mode="json"),
            "account_background": profile.account_background.model_dump(mode="json"),
            "persona_traits": profile.persona_traits.model_dump(mode="json"),
            "contextual_rules": profile.contextual_rules,
        }

    def _context_pack_markdown(self, profile: PersonaProfile) -> str:
        return "\n".join(
            [
                f"# {profile.display_name}",
                "",
                profile.mandate_summary,
                "",
                f"- Profile ID: {profile.profile_id}",
                f"- Version: {profile.version}",
                f"- Risk budget: {profile.risk_budget.value}",
                f"- Base currency: {profile.investment_constraints.base_currency or 'unspecified'}",
                f"- Execution mode: {profile.account_background.execution_mode.value if profile.account_background.execution_mode else 'unspecified'}",
                "",
                "## Profile Markdown",
                "",
                profile.persona_markdown or "",
            ]
        )

    def _write_text_atomic(self, path: Path, content: str) -> None:
        ensure_directory(path.parent)
        temporary_path = path.with_name(f".{path.name}.tmp")
        temporary_path.write_text(content, encoding="utf-8")
        temporary_path.replace(path)

    def _prefer(self, candidate: PersonaProfile, existing: PersonaProfile) -> bool:
        if candidate.is_active != existing.is_active:
            return candidate.is_active
        return candidate.version > existing.version

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

    def _safe_name(self, value: str) -> str:
        cleaned = re.sub(r"[^A-Za-z0-9_.-]+", "_", value).strip("._")
        return cleaned or "profile"

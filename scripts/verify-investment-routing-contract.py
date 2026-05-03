from __future__ import annotations

import json
from pathlib import Path

from finkernel.config import Settings
from finkernel.main import build_runtime


ROOT = Path(__file__).resolve().parents[1]


def read(relative_path: str) -> str:
    return (ROOT / relative_path).read_text(encoding="utf-8")


def main() -> None:
    skill_body = read("SKILL.md")
    routing_body = read("docs/investment-conversation-routing.md")
    integration_body = read("docs/upper-layer-agent-integration.md")

    assert "get_profile_onboarding_status" in skill_body
    assert "assess_persona" in skill_body
    assert "get_risk_profile_summary" in skill_body
    assert "save_profile_persona_markdown" in skill_body
    assert "Do not give generic ETF / T-bill / market advice first" in skill_body

    assert "get_profile_onboarding_status" in routing_body
    assert "start_profile_discovery" in routing_body
    assert "get_risk_profile_summary" in routing_body
    assert "web research" in routing_body.lower()

    assert "get_profile_onboarding_status" in integration_body
    assert "get_profile_persona_markdown" in integration_body
    assert "get_risk_profile_summary" in integration_body

    tmp_dir = ROOT / "tmp_mcp"
    tmp_dir.mkdir(exist_ok=True)
    profiles_path = tmp_dir / "routing-contract-profiles.json"
    profiles_path.write_text(json.dumps({"profiles": []}), encoding="utf-8")

    settings = Settings(
        environment="test",
        storage_backend="file",
        profile_data_dir=str(tmp_dir / "routing-contract-data"),
        database_url="postgresql+psycopg://finkernel:change-me@localhost:5432/finkernel",
        enable_pgvector=True,
        profile_store_path=str(profiles_path),
    )
    instructions = build_runtime(settings)["mcp_server"].instructions.lower()
    assert "first check profile onboarding status" in instructions
    assert "start profile discovery" in instructions
    assert "persona markdown" in instructions
    assert "risk profile summary" in instructions

    print("risk-profile-routing-contract: OK")


if __name__ == "__main__":
    main()

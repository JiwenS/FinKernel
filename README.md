# FinKernel

FinKernel is a Python/FastAPI service focused on one job: building and maintaining a **personal risk profile** that downstream agents and apps can trust before giving investment guidance.

The product surface is intentionally narrow:

- profile onboarding
- guided risk-profile discovery
- profile review and versioning
- persona markdown authoring
- long-term and short-term memory capture
- MCP + HTTP access for host agents

Everything outside that scope has been removed from the active product path.

## Current Delivery Phase

Phase 1 is the personal risk profile foundation.

In this phase, FinKernel only owns onboarding, discovery, review/versioning,
persona artifacts, and profile memory needed for profile-aware investment
guidance. Broader investment planning, recommendation generation, market
research orchestration, and execution flows are outside the current phase.

## Read This First

- Docs index:
  - English: `docs/README.en.md`
  - 简体中文: `docs/README.zh-CN.md`
- `docs/README.md`
- `docs/setup-and-run.md`
- `docs/persona-profiles.md`
- `docs/persona-agent-workflow.md`
- `docs/investment-conversation-routing.md`
- `docs/upper-layer-agent-integration.md`
- `docs/host-agent-runtime-integration.md`
- `docs/troubleshooting.md`
- `prompts/finkernel_system_routing.md`
- `SKILL.md`

## Core APIs

HTTP:

- `GET /api/health`
- `GET /api/profiles/onboarding-status`
- `POST /api/profiles/assess-persona`
- `GET /api/profiles/{profile_id}`
- `GET /api/profiles/{profile_id}/risk-summary`
- `GET /api/profiles/{profile_id}/persona.md`
- `GET /api/profiles/{profile_id}/persona-sources`
- `PUT /api/profiles/{profile_id}/persona`
- `GET /api/profiles/{profile_id}/versions`
- `POST /api/profiles/discovery/sessions`
- `GET /api/profiles/discovery/sessions/{session_id}/next-question`
- `POST /api/profiles/discovery/sessions/{session_id}/answers`
- `POST /api/profiles/discovery/sessions/{session_id}/draft`
- `POST /api/profiles/discovery/drafts/{draft_id}/confirm`
- `POST /api/profiles/{profile_id}/review`
- `POST /api/profiles/{profile_id}/memories`
- `GET /api/profiles/{profile_id}/memories/search`
- `POST /api/profiles/{profile_id}/memories/distill`

MCP:

- `http://localhost:8000/api/mcp/`

## Quick Start

1. Bootstrap a local clone:
   - `powershell -ExecutionPolicy Bypass -File .\scripts\bootstrap-local.ps1`
2. Start the app:
   - `powershell -ExecutionPolicy Bypass -File .\scripts\run-local.ps1`
3. Confirm health:
   - `http://localhost:8000/api/health`
4. If you skipped automatic agent registration, register `config/host-agent-mcp-http.local.json` or `config/host-agent-mcp-stdio.local.json` and inject `prompts/finkernel_system_routing.md`.
5. Start profile discovery or use the orchestration entrypoint:
   - `POST /api/profiles/assess-persona`
   - `POST /api/profiles/discovery/sessions`

## Configuration

- `config/persona-profiles.json` stores seed risk profiles.
- `config/persona-profiles.example.json` is the template.
- `config/host-agent-mcp-http.example.json` and `config/host-agent-mcp-stdio.example.json` show how to register FinKernel as an MCP server.
- `scripts/bootstrap-local.ps1` creates `.venv`, installs dependencies, guides `.env` setup, initializes PostgreSQL + `vector`, writes local HTTP/stdio MCP configs, and prepares an agent bundle for Codex/OpenClaw/custom clients.
- `scripts/run-local.ps1` starts the local FastAPI runtime on `http://localhost:8000`.

## Documentation Contract

FinKernel is only considered complete when implementation, prompts, and documentation all describe the same product: a personal risk profile system.

At minimum, every change should keep these surfaces aligned:

- API behavior
- MCP tool behavior
- routing prompt
- onboarding and review workflow docs
- seeded profile examples

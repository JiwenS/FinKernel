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

## Read This First

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

1. Create a local env file if needed.
2. Start the app:
   - `uvicorn finkernel.main:app --reload`
3. Confirm health:
   - `http://localhost:8000/api/health`
4. Start profile discovery:
   - `POST /api/profiles/discovery/sessions`

## Configuration

- `config/persona-profiles.json` stores seed risk profiles.
- `config/persona-profiles.example.json` is the template.
- `config/host-agent-mcp-http.example.json` and `config/host-agent-mcp-stdio.example.json` show how to register FinKernel as an MCP server.

## Documentation Contract

FinKernel is only considered complete when implementation, prompts, and documentation all describe the same product: a personal risk profile system.

At minimum, every change should keep these surfaces aligned:

- API behavior
- MCP tool behavior
- routing prompt
- onboarding and review workflow docs
- seeded profile examples

# Setup And Run

## Fastest local path

Run one command from the repo root:

- `powershell -ExecutionPolicy Bypass -File .\scripts\bootstrap-local.ps1`

That bootstrap script will:

- create `.venv` if needed
- install `.[dev]`
- guide `.env` setup one field at a time
- initialize PostgreSQL and enable the `vector` extension
- copy `config/persona-profiles.example.json` into `config/persona-profiles.json` if missing
- write `config/host-agent-mcp-http.local.json` and `config/host-agent-mcp-stdio.local.json`
- inject a ready-to-copy FinKernel skill bundle for the selected host agent
- prioritize four first-class agents: `Codex`, `Claude Code`, `OpenClaw`, and `Hermes`
- automatically register MCP for supported agents when their CLI is available
- fall back to a `Custom MCP client` export path for every other host runtime

## Manual local setup

1. Create and activate a Python 3.12 virtual environment.
2. Install the package in editable mode:
   - `pip install -e .[dev]`
3. Provision a PostgreSQL database and enable the `vector` extension.
4. Copy `.env.example` to `.env` and set a PostgreSQL `DATABASE_URL`.
5. Optionally copy `config/persona-profiles.example.json` into your own seed file.

## Run the HTTP app

- `powershell -ExecutionPolicy Bypass -File .\scripts\run-local.ps1`
- `uvicorn finkernel.main:app --reload`

Health check:

- `GET http://localhost:8000/api/health`

## Run the MCP server over stdio

- `powershell -ExecutionPolicy Bypass -File .\scripts\run-mcp-stdio.ps1`

## Connect a host agent

1. Run `scripts/bootstrap-local.ps1` and pick one of the four first-class agents:
   - `Codex`: installs the FinKernel skill into `~/.codex/skills` and tries `codex mcp add`
   - `Claude Code`: installs the FinKernel skill into `~/.claude/skills` and tries `claude mcp add --transport http`
   - `OpenClaw`: installs the FinKernel skill into `~/.openclaw/skills` and tries `openclaw mcp set`
   - `Hermes`: installs the FinKernel skill into `~/.hermes/skills` and tries `hermes config set mcp_servers.finkernel.url`
2. If you need a manual example instead, use `config/host-agent-mcp-http.local.json`, `config/host-agent-mcp-stdio.local.json`, `config/host-agent-mcp-http.example.json`, or `config/host-agent-mcp-stdio.example.json`.
3. Keep `prompts/finkernel_system_routing.md` available to the host runtime.
4. Use `prompts/persona_assessment.md` as the host-side assessment prompt template.
5. Use `SKILL.md` as the top-level profile-building skill.
6. For a single-entry orchestration flow, start with `assess_persona`.

## Useful local checks

- `pytest`
- `python .\scripts\verify-investment-routing-contract.py`

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
- inject a ready-to-copy bundle for the selected host agent
- optionally register FinKernel with Codex automatically

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

1. If you used the bootstrap script, use `config/host-agent-mcp-http.local.json` or `config/host-agent-mcp-stdio.local.json`.
2. If you need a manual example instead, use `config/host-agent-mcp-http.example.json` or `config/host-agent-mcp-stdio.example.json`.
3. Inject `prompts/finkernel_system_routing.md` into the host runtime.
4. Use `prompts/persona_assessment.md` as the host-side assessment prompt template.
5. Use `SKILL.md` as the top-level profile-building skill.
6. For a single-entry orchestration flow, start with `assess_persona`.

## Useful local checks

- `pytest`
- `python .\scripts\verify-investment-routing-contract.py`

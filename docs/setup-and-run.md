# Setup And Run

## Official local path

FinKernel v1 supports two local installation paths:

- Lite file storage, recommended for individual local profile generation
- Docker/PostgreSQL Server mode, optional for advanced local service testing

The host machine should have:

- one of the supported host-agent CLIs if you want automatic registration: `codex`, `claude`, `openclaw`, or `hermes`

Docker is only required for Server mode.

## Lite local setup

Lite mode is the default application configuration:

- `STORAGE_BACKEND=file`
- `PROFILE_DATA_DIR=.finkernel`

In Lite mode FinKernel writes local profile artifacts under `.finkernel/` and
does not initialize PostgreSQL.

Current generated artifacts include:

- `.finkernel/profiles/<profile_id>/versions/v001/profile.json`
- `.finkernel/profiles/<profile_id>/versions/v001/profile.md`
- `.finkernel/profiles/<profile_id>/versions/v001/profile_sources.json`
- `.finkernel/profiles/<profile_id>/versions/v001/profile_context_pack.json`
- `.finkernel/profiles/<profile_id>/versions/v001/profile_context_pack.md`
- `.finkernel/discovery/sessions/<session_id>/state.json`
- `.finkernel/discovery/sessions/<session_id>/turns.jsonl`
- `.finkernel/discovery/sessions/<session_id>/interpretations.jsonl`

For the storage contract, see `docs/local-file-storage-lite.md`.

Run the Lite bootstrap from the repo root:

- `powershell -ExecutionPolicy Bypass -File .\scripts\bootstrap.ps1`

That script will:

- ask whether to install Lite mode or Server mode
- create `.venv` if needed
- install FinKernel into the local virtual environment
- create `.env` with file storage defaults if it does not exist
- ensure `config/persona-profiles.json` exists as a blank seed file
- create `.finkernel/` for local profile artifacts
- write `config/host-agent-mcp-stdio.local.json`
- verify the MCP stdio runtime without starting Docker

## Direct mode selection

To skip the prompt, pass the mode explicitly:

- `powershell -ExecutionPolicy Bypass -File .\scripts\bootstrap.ps1 -Mode Lite`
- `powershell -ExecutionPolicy Bypass -File .\scripts\bootstrap.ps1 -Mode Server`

`scripts/bootstrap-lite.ps1` and `scripts/bootstrap-local.ps1` remain available
as compatibility wrappers, but `scripts/bootstrap.ps1` is the preferred user
entrypoint.

## Server local setup

The Server-mode path is Docker-oriented:

Run one command from the repo root:

- `powershell -ExecutionPolicy Bypass -File .\scripts\bootstrap.ps1 -Mode Server`

That bootstrap script will:

- guide `.env` setup one field at a time
- ensure `config/persona-profiles.json` exists as a blank local profile store
- run `docker compose up -d --build --remove-orphans`
- wait for PostgreSQL and the FinKernel HTTP app to become healthy
- write `config/host-agent-mcp-http.local.json`
- inject a ready-to-copy FinKernel skill bundle for the selected host agent
- prioritize four first-class agents: `Codex`, `Claude Code`, `OpenClaw`, and `Hermes`
- automatically register HTTP MCP for supported agents when their CLI is available
- fall back to a `Custom MCP client` export path for every other host runtime

## Restart the stack later

After the first bootstrap, you can bring the Docker stack back up with:

- `powershell -ExecutionPolicy Bypass -File .\scripts\run-local.ps1`

Health check:

- `GET http://localhost:8000/api/health`

MCP endpoint:

- `http://localhost:8000/api/mcp/`

If you changed `APP_PORT` in `.env`, use that port instead of `8000`.

## Uninstall the local stack

To remove the FinKernel Docker stack, generated local files, and installed FinKernel profile skill bundles:

- `powershell -ExecutionPolicy Bypass -File .\scripts\uninstall-local.ps1`

Helpful switches:

- `-Yes`: skip the confirmation prompt
- `-KeepEnv`: keep `.env`
- `-KeepSeedData`: keep `config/persona-profiles.json`
- `-KeepAgentBundles`: keep installed `finkernel-profile` bundles
- `-SkipAgentUnregistration`: keep MCP registrations in host agents
- `-KeepDockerVolumes`: keep Docker volumes
- `-KeepLocalImage`: keep the locally built Docker image

## Manual Docker path

The supported manual Server-mode path is Docker-based:

1. Copy `.env.example` to `.env`.
2. Set `STORAGE_BACKEND=database`.
3. Set at least `APP_PORT`, `POSTGRES_DB`, `POSTGRES_USER`, and `POSTGRES_PASSWORD`.
4. Ensure `config/persona-profiles.json` exists, or copy the blank scaffold from `config/persona-profiles.example.json`.
5. Run `docker compose up -d --build`.
6. Wait for `GET /api/health` to return `200`.

## Connect a host agent

1. Run `scripts/bootstrap.ps1`.
2. For Lite mode, use `config/host-agent-mcp-stdio.local.json`.
3. For Server mode, pick one of the four first-class agents:
   - `Codex`: installs the FinKernel skill into `~/.codex/skills` and tries `codex mcp add`
   - `Claude Code`: installs the FinKernel skill into `~/.claude/skills` and tries `claude mcp add --transport http`
   - `OpenClaw`: installs the FinKernel skill into `~/.openclaw/skills` and tries `openclaw mcp set`
   - `Hermes`: installs the FinKernel skill into `~/.hermes/skills` and tries `hermes config set mcp_servers.finkernel.url`
4. If you need a manual HTTP example instead, use `config/host-agent-mcp-http.local.json` or `config/host-agent-mcp-http.example.json`.
5. Keep `prompts/finkernel_system_routing.md` available to the host runtime.
6. Use `prompts/profile_assessment.md` as the host-side assessment prompt template.
7. Use `SKILL.md` as the top-level profile-building skill.
8. For a single-entry orchestration flow, start with `assess_profile`, or legacy `assess_persona`.

## Useful local checks

- `powershell -ExecutionPolicy Bypass -File .\scripts\bootstrap.ps1 -Mode Lite -SkipInstall`
- `docker compose ps`
- `docker compose logs app --tail 200`
- `pytest`
- `python .\scripts\verify-investment-routing-contract.py`

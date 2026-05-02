# Setup And Run

## Official local path

FinKernel v1 supports one official local installation path:

- Docker-only

The host machine should have:

- Docker
- one of the supported host-agent CLIs if you want automatic registration: `codex`, `claude`, `openclaw`, or `hermes`

## Fastest local setup

Run one command from the repo root:

- `powershell -ExecutionPolicy Bypass -File .\scripts\bootstrap-local.ps1`

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

The supported manual alternative is still Docker-based:

1. Copy `.env.example` to `.env`.
2. Set at least `APP_PORT`, `POSTGRES_DB`, `POSTGRES_USER`, and `POSTGRES_PASSWORD`.
3. Ensure `config/persona-profiles.json` exists, or copy the blank scaffold from `config/persona-profiles.example.json`.
4. Run `docker compose up -d --build`.
5. Wait for `GET /api/health` to return `200`.

## Connect a host agent

1. Run `scripts/bootstrap-local.ps1` and pick one of the four first-class agents:
   - `Codex`: installs the FinKernel skill into `~/.codex/skills` and tries `codex mcp add`
   - `Claude Code`: installs the FinKernel skill into `~/.claude/skills` and tries `claude mcp add --transport http`
   - `OpenClaw`: installs the FinKernel skill into `~/.openclaw/skills` and tries `openclaw mcp set`
   - `Hermes`: installs the FinKernel skill into `~/.hermes/skills` and tries `hermes config set mcp_servers.finkernel.url`
2. If you need a manual example instead, use `config/host-agent-mcp-http.local.json` or `config/host-agent-mcp-http.example.json`.
3. Keep `prompts/finkernel_system_routing.md` available to the host runtime.
4. Use `prompts/profile_assessment.md` as the host-side assessment prompt template.
5. Use `SKILL.md` as the top-level profile-building skill.
6. For a single-entry orchestration flow, start with `assess_persona`.

## Useful local checks

- `docker compose ps`
- `docker compose logs app --tail 200`
- `pytest`
- `python .\scripts\verify-investment-routing-contract.py`

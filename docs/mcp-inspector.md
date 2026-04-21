# MCP Inspector

FinKernel exposes MCP over Streamable HTTP at:

- `http://localhost:8000/api/mcp/`

If you changed `APP_PORT` in `.env`, substitute that port instead of `8000`.

This repo includes a local MCP Inspector install and a ready-to-use config at:

- `config/mcp-inspector.json`

## Prerequisites

- FinKernel is running locally and healthy through Docker:
  - `.\scripts\run-local.ps1`
- Node is installed

## Open the Inspector UI

From the repo root:

```powershell
npm run mcp:inspector
```

Or via the PowerShell helper:

```powershell
.\scripts\run-mcp-inspector.ps1
```

The Inspector UI should open on:

- `http://localhost:6274`

Use the preloaded server config named `finkernel`.

If `6274` or `6277` is already in use, the helper script automatically picks the next free localhost ports and prints them before launch.

## Run a CLI smoke test

List the tools exposed by the local MCP endpoint:

```powershell
.\scripts\run-mcp-inspector.ps1 -Cli --method tools/list
```

## Custom CLI calls

Examples:

```powershell
.\scripts\run-mcp-inspector.ps1 -Cli --method tools/list
.\scripts\run-mcp-inspector.ps1 -Cli --method tools/call --tool-name list_profiles
```

The repo helper intentionally routes CLI mode through the lower-level Inspector CLI entrypoint, because the package's top-level `--cli` wrapper is currently flaky in this environment.

## Transport choice

- For the first release, FinKernel's supported local MCP transport is **HTTP MCP** only.
- Host-agent registration and Inspector workflows should both point at `http://localhost:<APP_PORT>/api/mcp/`.

## Node version note

The installed Inspector version currently declares:

- `Node >= 22.7.5`

If you hit runtime issues under Node 20, upgrade Node first before debugging FinKernel's MCP behavior.

# MCP Inspector

FinKernel exposes MCP over Streamable HTTP at:

- `http://localhost:8000/api/mcp/`

FinKernel now also exposes a local stdio MCP entrypoint for clients that do not handle HTTP MCP well:

- `.\scripts\run-mcp-stdio.ps1`
- or `.\.venv\Scripts\python.exe -m finkernel.transport.mcp.stdio_runner`

This repo includes a local MCP Inspector install and a ready-to-use config at:

- `config/mcp-inspector.json`

## Prerequisites

- FinKernel is running locally and healthy:
  - `.\scripts\e2e-healthcheck.ps1`
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
npm run mcp:tools
```

Or:

```powershell
.\scripts\e2e-mcp-tools.ps1
```

## Custom CLI calls

Examples:

```powershell
.\scripts\run-mcp-inspector.ps1 -Cli --method tools/list
.\scripts\run-mcp-inspector.ps1 -Cli --method tools/call --tool-name list_profiles
```

The repo helper intentionally routes CLI mode through the lower-level Inspector CLI entrypoint, because the package's top-level `--cli` wrapper is currently flaky in this environment.

## When to use stdio vs HTTP

- Use **HTTP MCP** when you want remote/service-style integration, browser-based Inspector usage, or compatibility with remote MCP clients.
- Use **stdio MCP** when your GPT/client stack handles local spawned MCP servers better than HTTP transports.
- Both transports share the same database-backed profile/discovery state and the same tool surface.

## Node version note

The installed Inspector version currently declares:

- `Node >= 22.7.5`

If you hit runtime issues under Node 20, upgrade Node first before debugging FinKernel's MCP behavior.

# Local File Storage Lite

FinKernel Lite is the default local profile path for individual users and host
agents. It keeps the profile discovery workflow unchanged while removing the
need for Docker, PostgreSQL, ports, and health-check orchestration.

## Product intent

Lite mode should feel like a local profile generator:

1. the user downloads the project
2. a host agent starts the FinKernel profile workflow
3. FinKernel stores the working snapshot incrementally on disk
4. FinKernel generates a draft when coverage is sufficient
5. the user confirms the draft
6. FinKernel writes portable profile artifacts for other financial AI systems

Server mode remains available for multi-user, remote, or team deployments.

## Configuration

Lite mode is selected by:

```text
STORAGE_BACKEND=file
PROFILE_DATA_DIR=.finkernel
```

The database settings can stay present for Server mode, but Lite mode does not
open a database connection or initialize database tables.

## Bootstrap

Run:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\bootstrap.ps1 -Mode Lite
```

The unified bootstrap can also be run without `-Mode` and will ask whether to
install Lite or Server mode. In Lite mode, the script creates local storage, installs the package into `.venv`, writes
`config/host-agent-mcp-stdio.local.json`, and verifies the MCP stdio runtime
without starting Docker.

Host agents can use the generated stdio config:

```json
{
  "mcpServers": {
    "finkernel": {
      "command": ".venv\\Scripts\\python.exe",
      "args": ["-m", "finkernel.transport.mcp.stdio_runner"],
      "env": {
        "STORAGE_BACKEND": "file",
        "PROFILE_DATA_DIR": ".finkernel"
      }
    }
  }
}
```

## File layout

The default local layout is:

```text
.finkernel/
  profiles-index.json
  profiles/
    <profile_id>/
      active.json
      versions/
        v001/
          profile.json
          profile.md
          profile_sources.json
          profile_context_pack.json
          profile_context_pack.md
  discovery/
    sessions/
      <session_id>/
        state.json
        turns.jsonl
        interpretations.jsonl
        drafts/
          <draft_id>/
            draft.json
    drafts/
      <draft_id>/
        draft.json
```

## What each file means

- `state.json` stores the current discovery session and working profile
  snapshot.
- `turns.jsonl` stores accepted user-answer turns, one turn per line.
- `interpretations.jsonl` stores accepted interpretation packets, one packet per
  line.
- `draft.json` stores the pending profile draft before user confirmation.
- `profile.json` is the canonical machine-readable profile.
- `profile.md` is the human-readable profile markdown.
- `profile_sources.json` stores evidence, contextual rules, and memories.
- `profile_context_pack.json` is a compact machine-readable context bundle for
  other financial AI systems.
- `profile_context_pack.md` is a prompt-friendly context bundle.

## Database responsibilities replaced by files

The previous database-backed runtime stored:

- confirmed profile versions
- profile markdown
- profile evidence
- contextual rules
- long-term and short-term memories
- discovery sessions and working snapshots
- conversation turns
- accepted interpretation packets
- pending drafts

Lite mode stores the same business objects as local files. The simplified
runtime changes storage and deployment mechanics, not the profile discovery
state machine.

## Tradeoffs

Lite mode is preferred for:

- single-user local profile creation
- fast host-agent onboarding
- easy profile export
- transparent local artifacts

Server mode is still preferred for:

- many concurrent users
- remote HTTP clients
- centralized administration
- database migrations and operational controls

The file backend uses atomic writes for JSON documents and append-only JSONL for
turns and interpretation packets. If multiple host agents write to the same
profile at the same time, future work should add a lock file around write
operations.

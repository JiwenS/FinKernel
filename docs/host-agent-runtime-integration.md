# Host Agent Runtime Integration

The host runtime must do two things:

1. register FinKernel as an MCP server
2. inject a FinKernel-first routing prompt

If only one of those happens, the host may still skip FinKernel and answer like a generic finance chatbot.

For the current delivery plan, this runtime integration is specifically about Phase 1 risk-profile flows, not a full end-to-end investment orchestration stack.

## Registration example

- `config/host-agent-mcp-http.example.json`

## Fastest local integration

If the user cloned the repo and wants a working local install with host-agent registration in one pass, start here:

1. run `powershell -ExecutionPolicy Bypass -File .\scripts\bootstrap-local.ps1`
2. let the installer start the Docker stack and wait for `http://localhost:<APP_PORT>/api/health`
3. let the installer fast-path one of the four first-class agents: `Codex`, `Claude Code`, `OpenClaw`, or `Hermes`
4. let the installer auto-register HTTP MCP when that agent's CLI is available, or fall back to the generated bundle + local HTTP MCP config for a custom host
5. inject `prompts/finkernel_system_routing.md`
6. use `prompts/persona_assessment.md` for the assessment conversation layer
7. use `SKILL.md` as the host-side skill entrypoint

The bootstrap script prepares `.env`, ensures the local blank profile store file exists, runs Docker Compose, waits for the app to become healthy, emits a local HTTP MCP config, writes a FinKernel skill bundle into the selected agent directory, and attempts agent-specific HTTP MCP registration for Codex, Claude Code, OpenClaw, or Hermes.

## Important runtime facts

- FinKernel currently exposes MCP tools, not MCP resources.
- The bootstrap registration alias is `finkernel`.
- After MCP registration or skill updates, start a new host session so the tool surface is reloaded cleanly.

For profile-building conversations, the host should not probe local files,
shell commands, `.env`, or database state as a substitute for the FinKernel
tool surface.

## Prompt layer

- `prompts/finkernel_system_routing.md`
- `prompts/persona_assessment.md`

## Dedicated profile-building entrypoint

For conversations whose primary goal is to build, complete, or refresh the profile itself, prefer:

- `assess_persona`

That tool lets the host treat FinKernel as a single orchestration surface: it decides whether FinKernel should add a persona from scratch, continue an update, ask the user to choose a section to refresh, or move into draft confirmation.

If `assess_persona` is not available in the current session, the host should
stop and report that FinKernel MCP tools are not mounted, rather than falling
back to repo inspection or local persistence probing.

## Expected first tool call

For profile-aware investment conversations, the first tool call should be:

- `get_profile_onboarding_status`

After a profile exists, the host should read:

- `get_profile`
- `get_profile_persona_markdown`
- `get_risk_profile_summary`

If the conversation is about correction or review, the host should also consider:

- `get_profile_persona_sources`
- `review_profile`
- `search_profile_memory`

# Host Agent Runtime Integration

The host runtime must do two things:

1. register FinKernel as an MCP server
2. inject a FinKernel-first routing prompt

If only one of those happens, the host may still skip FinKernel and answer like
a generic finance chatbot.

For the current delivery plan, this runtime integration is specifically about
Phase 1 risk-profile flows, not a full end-to-end investment orchestration
stack.

## Registration examples

- `config/host-agent-mcp-http.example.json`
- `config/host-agent-mcp-stdio.example.json`

## Fastest local integration

If the user cloned the repo and wants a working local install with host-agent
registration in one pass, start here:

1. run `powershell -ExecutionPolicy Bypass -File .\scripts\bootstrap-local.ps1`
2. let the installer fast-path one of the four first-class agents: `Codex`, `Claude Code`, `OpenClaw`, or `Hermes`
3. let the installer auto-register MCP when that agent's CLI is available, or fall back to the generated bundle + local MCP configs for a custom host
4. inject `prompts/finkernel_system_routing.md`
5. use `prompts/persona_assessment.md` for the assessment conversation layer
6. use `SKILL.md` as the host-side skill entrypoint

The bootstrap script prepares `.venv`, installs dependencies, guides `.env`
setup, initializes PostgreSQL with the `vector` extension, seeds local profile
data, emits local HTTP + stdio MCP configs, writes a FinKernel skill bundle
into the selected agent directory, and attempts agent-specific MCP registration
for Codex, Claude Code, OpenClaw, or Hermes.

## Prompt layer

- `prompts/finkernel_system_routing.md`
- `prompts/persona_assessment.md`

## Dedicated profile-building entrypoint

For conversations whose primary goal is to build, complete, or refresh the
profile itself, prefer:

- `assess_persona`

That tool lets the host treat FinKernel as a single orchestration surface: it
decides whether FinKernel should add a persona from scratch, continue an update,
ask the user to choose a section to refresh, or move into draft confirmation.

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

# Host Agent Runtime Integration

This guide covers the missing step that often causes FinKernel to be skipped:
the host agent runtime must both:

1. register FinKernel as a live MCP server, and
2. inject a FinKernel-first routing prompt into the host agent's system instructions

If only one of those is present, the agent may still answer as a generic finance
chatbot.

## Why this guide exists

FinKernel already exposes the correct MCP tools and routing contracts, but those
contracts only work when the host agent can actually see the tools and is told to
prefer them.

The common failure mode looks like this:

- FinKernel is running locally
- the repo contains `SKILL.md` and routing docs
- but the active agent session does not have the FinKernel MCP server registered
- or the agent has the tools available but is not instructed to use them first

In that situation, the model will usually:

1. answer with generic investment guidance
2. optionally browse the web for current finance facts
3. skip `get_profile_onboarding_status`

That is a host-runtime integration problem, not a FinKernel tool-surface problem.

## Required integration layers

### 1. MCP registration

The host runtime must register FinKernel as a named MCP server.

Ready-to-copy examples live here:

- `config/host-agent-mcp-http.example.json`
- `config/host-agent-mcp-stdio.example.json`

Use HTTP MCP when the host supports remote or service-style MCP connections.
Use stdio MCP when the host prefers spawning a local MCP server process.

### 2. System prompt routing

The host runtime must inject a system prompt that forces investment and
portfolio-management requests through FinKernel before generic advice.

Ready-to-copy template:

- `prompts/finkernel_system_routing.md`

### 3. Runtime smoke test

Before trusting the integration, verify all three of these:

1. the host can list FinKernel tools
2. the first tool call for investment intent is `get_profile_onboarding_status`
3. the host does not jump straight to generic ETF / rate / stock-picking advice

## Baseline registration examples

### HTTP MCP

Example file:

- `config/host-agent-mcp-http.example.json`

Expected server:

- name: `finkernel`
- transport: `streamable-http`
- url: `http://localhost:8000/api/mcp/`

### stdio MCP

Example file:

- `config/host-agent-mcp-stdio.example.json`

Expected command:

- `.\.venv\Scripts\python.exe -m finkernel.transport.mcp.stdio_runner`

If the host runtime launches the server itself, make sure the working directory
is the repo root so the local environment and config files resolve correctly.

## Required routing behavior

For user requests such as:

- "I want to invest 20k"
- "help me manage this money"
- "should I rebalance"
- "review my risk"
- "what should I do with this portfolio"

the host agent should behave like this:

1. call `get_profile_onboarding_status`
2. if onboarding is required, start discovery before giving profile-scoped advice
3. if a profile exists, resolve the active profile
4. read:
   - `get_profile`
   - `get_profile_persona_markdown`
   - `get_risk_summary`
   - `get_portfolio_snapshot` when holdings or cash matter
5. only then call:
   - `create_strategy_from_text`
   - `run_advisor_once`
   - `list_suggestions`
   - `simulate_trade`

## Strong recommendation for host policy

Do not silently fall back to generic investment advice when FinKernel is expected
to govern the conversation but its MCP server is missing or unavailable.

Instead, prefer one of these behaviors:

- surface a clear integration error to the operator
- tell the user the FinKernel advisory system is currently unavailable
- ask the host layer to retry MCP registration

This makes routing failures visible instead of masking them with plausible but
unscoped finance chat.

## Smoke-test checklist

After wiring the host runtime, run this checklist:

1. Start FinKernel and confirm `/api/health` reports `mcp_enabled = true`
2. Connect the host runtime using one of the example MCP configs
3. Confirm the host can list tools and sees:
   - `get_profile_onboarding_status`
   - `create_strategy_from_text`
   - `run_advisor_once`
   - `get_risk_summary`
4. Send a test prompt like:
   - "I have an account and want investment advice"
5. Confirm the host's first FinKernel call is:
   - `get_profile_onboarding_status`
6. Confirm the host does not start with generic finance advice or web search

## Related guides

- `docs/investment-conversation-routing.md`
- `docs/upper-layer-agent-integration.md`
- `docs/mcp-inspector.md`
- `SKILL.md`

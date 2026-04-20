# Host Agent Runtime Integration

The host runtime must do two things:

1. register FinKernel as an MCP server
2. inject a FinKernel-first routing prompt

If only one of those happens, the host may still skip FinKernel and answer like
a generic finance chatbot.

## Registration examples

- `config/host-agent-mcp-http.example.json`
- `config/host-agent-mcp-stdio.example.json`

## Prompt layer

- `prompts/finkernel_system_routing.md`

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

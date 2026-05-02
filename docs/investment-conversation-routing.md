# Investment Conversation Routing

This document defines how an upper-layer agent should route natural-language
investment conversations into FinKernel.

It reflects Phase 1 scope: FinKernel's job right now is to establish, read, and
maintain the user's personal risk profile before any profile-aware advice is
given.

## Core rule

When the user asks for profile-aware investment guidance:

1. do **not** start with generic investment advice
2. do **not** start with web search
3. first resolve onboarding and active-profile state

## Required first call

The first MCP read should be:

- `get_profile_onboarding_status`

For explicit persona-building or persona-maintenance requests, start with:

- `assess_persona`

## If no active profile exists

1. explain that profile-scoped advice requires a personal risk profile first
2. prefer `assess_persona` as the orchestration entrypoint into profile creation
3. continue the returned profile-building flow until the draft is ready
4. confirm the draft once the profile markdown artifact is ready

The lower-level discovery tools:

- `start_profile_discovery`
- `get_profile_discovery_state`
- `submit_profile_discovery_interpretation`

remain available for workflow-layer integrations, but they are not the preferred
host-visible entrypoint for normal profile-building conversations.

## If an active profile exists

Read:

- `get_profile`
- `get_profile_persona_markdown`
- `get_risk_profile_summary`

If the answer depends on recent context, also read:

- `search_profile_memory`
- `distill_profile_memory`

Only after that should the host decide whether web research materially adds value.

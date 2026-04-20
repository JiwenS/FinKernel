---
name: finkernel-agent
description: "Route onboarding, risk-profile review, and persona-authoring conversations into FinKernel MCP-backed workflows."
version: "2.0.0"
user-invocable: true
---

# FinKernel Agent Skill

## Purpose

This skill is the top-level execution surface for host agents integrating FinKernel.

FinKernel stores onboarding state, profile evidence, persona markdown, version history,
and long-term / short-term memory for a user's personal risk profile.

The agent using this skill is responsible for:

1. routing profile-aware investment conversations into FinKernel first
2. checking onboarding state before giving profile-scoped guidance
3. reading the right profile context before answering
4. maintaining persona markdown as the canonical human-readable artifact
5. using review and memory tools when new evidence changes the profile

## Core operating rule

If the user is implicitly asking for profile-aware investment guidance, do **not**
start with generic web-style investment advice.

First route through FinKernel:

1. check onboarding / active profile state
2. resolve the active profile
3. read profile-aware context
4. only then give profile-scoped guidance

Use general market research only **after** FinKernel context is loaded and only when
fresh external facts materially affect the answer.

## Tool routing

### Onboarding / profile selection

- MCP `get_profile_onboarding_status`
- MCP `list_profiles`
- MCP `start_profile_discovery`
- MCP `get_next_profile_question`
- MCP `submit_profile_discovery_answer`
- MCP `generate_profile_draft`
- MCP `confirm_profile_draft`

### Read profile context

- MCP `get_profile`
- MCP `get_profile_persona_sources`
- MCP `get_profile_persona_markdown`
- MCP `get_risk_profile_summary`
- MCP `list_profile_versions`
- MCP `search_profile_memory`
- MCP `distill_profile_memory`

### Write profile artifacts

- MCP `save_profile_persona_markdown`
- MCP `append_profile_memory`
- MCP `review_profile`

### Prompt assets

- `prompts/persona_analyzer.md`
- `prompts/persona_builder.md`
- `prompts/persona_merger.md`
- `prompts/persona_correction.md`

## Main routing flow

1. Call `get_profile_onboarding_status`.
2. If onboarding is required:
   - explain that FinKernel needs profile context first
   - start discovery
   - continue question / answer flow until draft is ready
   - generate the draft
   - write `persona_markdown` when needed
   - confirm the draft
3. If an active profile exists:
   - resolve the governing profile
   - read `get_profile`
   - read `get_profile_persona_markdown`
   - read `get_risk_profile_summary`
   - read memory when relevant
4. If the user corrects or updates the profile:
   - start `review_profile` or append memory
   - rebuild markdown if necessary
   - save the updated artifact

## Execution rules

1. Treat conversation evidence as the primary source of truth.
2. Treat long-term and short-term memory as supporting context.
3. Preserve time-sensitive constraints in prose and memory.
4. Use merge/correction prompts whenever new evidence changes prior conclusions.
5. Do not give generic ETF / T-bill / market advice first when profile-aware FinKernel routing is available.

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

Current delivery scope: Phase 1 is risk-profile work only. Use this skill to
complete onboarding, retrieve or revise the active profile, maintain persona
artifacts, and capture profile memory before any broader investment workflow.

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

### Primary orchestration

- MCP `assess_persona`

Use `assess_persona` as the default single entrypoint for
profile-building conversations. It should tell the host whether:

1. there is no active persona yet and FinKernel should add one from scratch
2. an active persona exists but still needs an update pass to become complete
3. the active persona is complete and the user should choose whether to reassess or update a section
4. a draft is ready for persona writing + confirmation
5. no changes were requested and the current active persona remains in force

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

- `prompts/persona_assessment.md`
- `prompts/persona_analyzer.md`
- `prompts/persona_builder.md`
- `prompts/persona_merger.md`
- `prompts/persona_correction.md`

## Main routing flow

1. For profile-building or profile-maintenance requests, call `assess_persona`.
2. If it returns `question_pending`:
   - ask the returned question
   - submit the answer with `submit_profile_discovery_answer`
   - call `assess_persona` again
   - keep going until every required section is covered
3. If it returns `awaiting_update_selection`:
   - present the returned `update_options`
   - send the selected `update_choice` back through `assess_persona`
4. If it returns `draft_ready`:
   - read the draft and evidence
   - write or refresh `persona_markdown`
   - call `confirm_profile_draft`
5. If it returns `persona_complete`:
   - continue using the current active persona
6. For profile-aware investment guidance, still preserve the strict read-first flow:
   - `get_profile_onboarding_status`
   - `get_profile`
   - `get_profile_persona_markdown`
   - `get_risk_profile_summary`

## Execution rules

1. Treat conversation evidence as the primary source of truth.
2. Treat long-term and short-term memory as supporting context.
3. Preserve time-sensitive constraints in prose and memory.
4. Use merge/correction prompts whenever new evidence changes prior conclusions.
5. Do not give generic ETF / T-bill / market advice first when profile-aware FinKernel routing is available.

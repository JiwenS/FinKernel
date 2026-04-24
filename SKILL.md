---
name: finkernel-profile
description: "Build, review, and maintain a user's FinKernel profile through MCP-backed persona workflows."
version: "2.0.0"
user-invocable: true
---

# FinKernel Profile Skill

## Trigger Conditions

Use this skill when the user is trying to do any of the following:

- /FinKernel Profile
- build a financial profile 
- continue an incomplete profile
- refresh or revise an existing profile
- correct profile conclusions
- append new profile memory
- request profile-aware investment guidance

Compatible hosts:

- Claude Code
- OpenClaw
- Hermes
- Codex

Host-visible entrypoint:

- `/FinKernel Profile`

## Purpose

This skill is the primary execution surface for building and maintaining a
financial profile.

FinKernel stores:

- onboarding state
- structured profile boundaries
- persona evidence
- persona markdown
- version history
- long-term memory
- short-term memory

## Tool Usage Rules

### Primary orchestration

- MCP `assess_persona`

`assess_persona` is the default single entrypoint for profile-building
conversations. It decides whether FinKernel should:

1. add a persona from scratch
2. continue an incomplete persona
3. ask the user to choose a section to update
4. move into draft confirmation
5. keep the current active persona unchanged

### Discovery and confirmation tools

- MCP `start_profile_discovery`
- MCP `get_next_profile_question`
- MCP `submit_profile_discovery_answer`
- MCP `generate_profile_draft`
- MCP `confirm_profile_draft`

Use these only when the host is intentionally operating at the lower-level
workflow layer. For normal profile conversations, prefer `assess_persona`.

### Read profile context

- MCP `get_profile_onboarding_status`
- MCP `list_profiles`
- MCP `get_profile`
- MCP `get_profile_persona_sources`
- MCP `get_profile_persona_markdown`
- MCP `get_risk_profile_summary`
- MCP `list_profile_versions`
- MCP `search_profile_memory`
- MCP `distill_profile_memory`

### Write or revise profile artifacts

- MCP `save_profile_persona_markdown`
- MCP `append_profile_memory`
- MCP `review_profile`

### Prompt assets

- `prompts/persona_assessment.md`
- `prompts/persona_analyzer.md`
- `prompts/persona_builder.md`
- `prompts/persona_merger.md`
- `prompts/persona_correction.md`

## Main Flow

### Step 1: Start with `assess_persona`

For profile-building or profile-maintenance requests:

1. call `assess_persona`
2. inspect the returned `status`, `reason`, `notes`, and `next_question`
3. continue only through the returned FinKernel state machine

### Step 2: Handle question-driven construction

If `assess_persona` returns `question_pending`:

1. ask the returned question
2. submit the answer with `submit_profile_discovery_answer`
3. call `assess_persona` again
4. repeat until the returned status changes

### Step 3: Handle update selection

If `assess_persona` returns `awaiting_update_selection`:

1. present the returned `update_options`
2. collect the user's section choice or `no_changes`
3. send the selected `update_choice` back through `assess_persona`

### Step 4: Draft authoring and confirmation

If `assess_persona` returns `draft_ready`:

1. read the draft and `persona_evidence`
2. use `prompts/persona_analyzer.md` to structure the evidence
3. use `prompts/persona_builder.md` to write or refresh `persona_markdown`
4. confirm the draft with `confirm_profile_draft`

### Step 5: Completed state

If `assess_persona` returns `persona_complete`:

- continue using the current active profile
- do not restart discovery unless the user asks for a revision

## Profile-Aware Guidance Flow

If the user is asking for profile-aware investment guidance rather than profile
construction itself, the minimum read-first sequence is:

1. `get_profile_onboarding_status`
2. `get_profile`
3. `get_profile_persona_markdown`
4. `get_risk_profile_summary`

Only after this context is loaded should the host respond with profile-scoped
guidance.

## Append And Correct Flow

### Append new memory

Use `append_profile_memory` when the user is adding a new durable fact or a
time-sensitive context item without requiring a full profile rebuild.

Examples:

- a new recurring liquidity event
- a temporary travel or cash-flow constraint
- a durable behavioral observation worth saving

### Correct conclusions

When the user says the current profile is wrong, incomplete, or outdated:

1. read current profile context
2. determine whether this is a local correction or a true reassessment
3. if it changes structured boundaries or major traits, go back through `assess_persona`
4. if it is only a markdown correction, use `prompts/persona_correction.md` and `save_profile_persona_markdown`

### Merge updates into an existing persona

When prior conclusions and new evidence both matter:

1. read current markdown, evidence, and memory
2. use `prompts/persona_merger.md`
3. preserve still-valid conclusions
4. explicitly reconcile contradictory evidence instead of silently overwriting it

## Failure Handling

If FinKernel tools are not available in the current session:

1. stop immediately
2. report that FinKernel MCP tools are not mounted in this session
3. tell the user to verify the local MCP server registration and start a new host session

Do not:

- call `list_mcp_resources` as the primary diagnostic path
- guess server names
- scan repo files to continue the workflow
- read local profile JSON or database state as a substitute for MCP tool access

## Execution Rules

1. Treat direct conversation evidence as the primary source of truth.
2. Treat long-term and short-term memory as supporting context, not replacements for dialogue.
3. Preserve time-sensitive constraints in prose and memory.
4. Keep structured boundaries and narrative traits separate.
5. Use merge or correction prompts whenever new evidence changes prior conclusions.

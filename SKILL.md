---
name: finkernel-profile
description: "Build, review, and maintain a user's FinKernel profile through MCP-backed profile workflows."
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
- profile evidence
- profile markdown
- version history
- long-term memory
- short-term memory

The discovery experience should feel like one continuous chat. Internal profile
updates, conflict checks, and progress tracking should happen in the background
unless the user explicitly asks to inspect the current profile state.

## User-Visible Wording Protocol

Do not expose internal runtime labels or tool mechanics to the user.

Do not say:

- `draft_ready`
- `pending draft`
- `Used Finkernel`
- `tool call`
- raw backend conflict notes
- raw remaining gap lists

Use stable product phrasing instead:

- when discovery is sufficiently covered:
  - "信息已经足够，我会整理一版画像草稿给你确认。"
- when the draft has been written:
  - "下面是画像草稿。请你确认是否保存为正式 profile，或者指出需要修改的地方。"
- before saving the active profile:
  - "如果你确认这版草稿，我再把它保存为正式 profile。"
- after explicit user confirmation and successful save:
  - "已保存为正式 profile，后续我会默认按这版画像工作。"

Never confirm a draft as the active profile unless the user has explicitly
approved the shown draft. `confirm_profile_draft` must include
`user_confirmed=true` only after that explicit approval.

## Critical Rules

1. The first tool call for profile-building or profile-maintenance requests must be `assess_profile` when available, or legacy `assess_persona`.
2. FinKernel currently exposes a tool-only surface, not an MCP resource surface.
3. The MCP registration alias used by bootstrap is `finkernel`.
4. Do not start profile construction by listing MCP resources, reading local files, inspecting `.env`, probing the database, or running shell discovery.
5. If neither `assess_profile` nor legacy `assess_persona` is available in the current session, stop and report that FinKernel MCP tools are not mounted in this session.
6. Do not simulate the profile workflow by scanning repo files or local persisted data when MCP tools are unavailable.

## Tool Usage Rules

### Primary orchestration

- MCP `assess_profile`
- MCP `assess_persona` legacy alias

`assess_profile` is the default single entrypoint for profile-building
conversations. It decides whether FinKernel should:

1. add a persona from scratch
2. continue an incomplete profile
3. ask the user to choose a section to update
4. move into draft confirmation
5. keep the current active profile unchanged

### Discovery and confirmation tools

- MCP `start_profile_discovery`
- MCP `get_profile_discovery_state`
- MCP `submit_profile_discovery_interpretation`
- MCP `generate_profile_draft`
- MCP `confirm_profile_draft`

Use these only when the host is intentionally operating at the lower-level
workflow layer. For normal profile conversations, prefer `assess_profile`.

### Read profile context

- MCP `get_profile_onboarding_status`
- MCP `list_profiles`
- MCP `get_profile`
- MCP `get_profile_markdown`
- MCP `get_profile_sources`
- MCP `get_profile_persona_sources`
- MCP `get_profile_persona_markdown`
- MCP `get_risk_profile_summary`
- MCP `list_profile_versions`
- MCP `search_profile_memory`
- MCP `distill_profile_memory`

### Write or revise profile artifacts

- MCP `save_profile_markdown`
- MCP `save_profile_persona_markdown`
- MCP `append_profile_memory`
- MCP `review_profile`

### Prompt assets

- `prompts/profile_assessment.md`
- `prompts/profile_analyzer.md`
- `prompts/profile_builder.md`
- `prompts/discovery_question_generator.md`
- `prompts/discovery_answer_extractor.md`
- `prompts/profile_narrative_builder.md`
- `prompts/profile_merger.md`
- `prompts/profile_correction.md`

## Main Flow

### Step 1: Start with `assess_profile`

For profile-building or profile-maintenance requests:

1. call `assess_profile` if available, otherwise call legacy `assess_persona`
2. inspect the returned `status`, `reason`, `notes`, and `discovery_state`
3. continue only through the returned FinKernel state machine

### Step 2: Run the discovery loop section by section

If `assess_profile` or legacy `assess_persona` returns `question_pending`:

1. read `discovery_state.current_section`
2. if `discovery_state.starter_question` is present, ask that starter question
3. otherwise use `prompts/discovery_question_generator.md` to generate one dynamic follow-up question for the current section
4. collect the user's answer
5. use `prompts/discovery_answer_extractor.md` to produce a strict interpretation packet
6. submit the packet with `submit_profile_discovery_interpretation`
7. read the updated discovery state internally
8. stay in the same section until it is covered
9. move to the next section only after the current section is sufficiently covered
10. call `assess_profile` again when you need the higher-level state machine to advance

Do not:

- dump the current working profile after every turn
- report raw remaining gaps or conflict notes to the user as backend state
- interrupt the interview with draft fragments before the user asks for them or the flow is complete

### Step 3: Handle update selection

If `assess_profile` or legacy `assess_persona` returns `awaiting_update_selection`:

1. present the returned `update_options`
2. collect the user's section choice or `no_changes`
3. send the selected `update_choice` back through `assess_profile`

### Step 4: Draft authoring and confirmation

If `assess_profile` or legacy `assess_persona` returns `draft_ready`:

1. say: "信息已经足够，我会整理一版画像草稿给你确认。"
2. read the draft and `draft_source`
3. use `prompts/profile_analyzer.md` to structure the evidence
4. use `prompts/profile_builder.md` to write or refresh the final profile markdown artifact
5. show the profile markdown draft to the user
6. ask the user to confirm or request changes
7. call `confirm_profile_draft` with `user_confirmed=true` only after explicit user approval

### Step 5: Completed state

If `assess_profile` or legacy `assess_persona` returns `persona_complete`:

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
3. if it changes structured boundaries or major traits, go back through `assess_profile`
4. if it is only a markdown correction, use `prompts/profile_correction.md` and `save_profile_markdown`

### Merge updates into an existing profile

When prior conclusions and new evidence both matter:

1. read current markdown, evidence, and memory
2. use `prompts/profile_merger.md`
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
6. Use `discovery_question_generator` for follow-up wording and `discovery_answer_extractor` for semantic interpretation.
7. Do not give generic ETF / T-bill / market advice first when profile-aware FinKernel routing is available.
8. Use internal conflicts, uncertainty, and remaining gaps to shape the next clarifying question rather than surfacing those mechanics to the user on every turn.

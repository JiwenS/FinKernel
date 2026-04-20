---
name: finkernel-agent
description: "Route investment, portfolio-management, onboarding, and persona-authoring conversations into FinKernel MCP-backed workflows."
version: "1.0.0"
user-invocable: true
---

# FinKernel Agent Skill

## Purpose

This skill is the top-level execution surface for upper-layer agents integrating
FinKernel.

FinKernel itself stores onboarding state, profile evidence, memory, versions,
simulation facts, strategies, suggestions, workflow requests, and execution state.
The agent using this skill is responsible for:

1. routing natural-language investment intent into the correct FinKernel workflow
2. checking onboarding / profile state before giving profile-scoped advice
3. reading the right profile, risk, and portfolio context before making recommendations
4. using the advisor / suggestion flow when the user is asking for deployable guidance
5. creating and maintaining `persona_markdown` artifacts when persona work is needed

## Core operating rule

If the user is implicitly asking **this system** to help manage money, deploy capital,
rebalance a portfolio, or make profile-aware investment decisions, do **not** start
with generic web-style investment advice.

First route through FinKernel:

1. check onboarding / active profile state
2. resolve the active profile
3. read profile-aware context
4. only then generate profile-scoped recommendations or advisor suggestions

Use general market research only **after** FinKernel context is loaded and only when
fresh external facts materially affect the answer.

## Trigger conditions

Use this skill when the user asks to:

- invest money, deploy capital, or allocate a budget
- manage funds, manage a portfolio, or rebalance positions
- review risk, profile fit, or portfolio posture
- decide what to buy / sell inside FinKernel's paper-trading workflow
- create a new persona
- generate or rewrite `persona.md`
- review or update a persona
- correct a persona that is wrong
- evolve an existing persona after new evidence appears

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
- MCP `list_profile_versions`
- MCP `get_portfolio_snapshot`
- MCP `get_risk_summary`
- MCP `search_profile_memory`
- MCP `distill_profile_memory`

### Write persona artifact
- MCP `save_profile_persona_markdown`

### Memory support
- MCP `append_profile_memory`

### Advisor / decision-support flow
- MCP `create_strategy`
- MCP `create_strategy_from_text`
- MCP `list_strategies`
- MCP `run_advisor_once`
- MCP `list_suggestions`
- MCP `get_suggestion`
- MCP `simulate_trade`

### Workflow follow-up
- MCP `list_requests`
- MCP `get_request`
- MCP `approve_suggestion`
- MCP `reject_suggestion`
- MCP `refresh_request`
- MCP `reconcile_request`
- MCP `cancel_request`

### Prompt assets
- `prompts/persona_analyzer.md`
- `prompts/persona_builder.md`
- `prompts/persona_merger.md`
- `prompts/persona_correction.md`

## Language rule

- Detect the user's dominant language from the evidence.
- Write the final persona in that language.
- This applies to all languages.

## Main routing flows

### A. Investment / capital-allocation intent

For requests like:

- "我想做一笔 20000 美金的投资"
- "帮我管理一下这笔钱"
- "我该怎么配置仓位"
- "should I rebalance"
- "what would you do with this portfolio"

follow this sequence:

1. Call `get_profile_onboarding_status` **before** recommending specific allocations.
2. If onboarding is required:
   - explain that FinKernel needs the user's risk / objective profile first
   - if the host already provides a stable `owner_id`, call `start_profile_discovery`
   - if no host identity is bound yet, ask for the minimum stable owner label once, then start discovery
   - continue with `get_next_profile_question` + `submit_profile_discovery_answer`
   - call `generate_profile_draft`
   - author `persona_markdown` with the prompt sequence when needed
   - finalize with `confirm_profile_draft`
3. If exactly one active profile exists:
   - use that profile automatically
4. If multiple active profiles exist:
   - prefer an explicitly named profile
   - otherwise ask the user which profile should govern the recommendation before giving specific allocation advice
5. Before recommending actions under an active profile, read:
   - `get_profile`
   - `get_profile_persona_markdown`
   - `get_risk_summary`
   - `get_portfolio_snapshot` when current holdings / cash matter
6. For broad "what should I do with this capital" requests, prefer:
   - `create_strategy_from_text`
   - `run_advisor_once`
   - `list_suggestions`
7. For hypothetical order sizing or projected impact, prefer `simulate_trade`.
8. Only after the above may you add external market color or web research if it materially changes the answer.

### B. Persona create / review / correction

#### Create flow

1. Run discovery until ready
2. Generate profile draft
3. Read `suggested_profile.persona_evidence`
4. Run `persona_analyzer.md`
5. Run `persona_builder.md`
6. Confirm the draft with `persona_markdown`

#### Review / evolve flow

1. Start review on the current profile
2. Generate review draft
3. Read:
   - current persona markdown
   - new persona evidence
   - active memory
4. Run `persona_analyzer.md`
5. Run `persona_merger.md`
6. Run `persona_builder.md`
7. Confirm the review draft with updated `persona_markdown`

#### Correction flow

1. Read the current persona source packet
2. Capture the correction statement as new evidence
3. Run `persona_correction.md`
4. If broader changes are needed, run `persona_merger.md`
5. Run `persona_builder.md`
6. Write back with `save_profile_persona_markdown`

## Execution rules

1. Treat conversation evidence as the primary source of truth.
2. Treat long-term and short-term memory as supporting context.
3. Do not let structured enforcement fields dictate personality interpretation.
4. Preserve time-sensitive constraints in prose.
5. Use merge/correction prompts whenever new evidence changes prior conclusions.
6. Do not give generic ETF / T-bill / market advice first when profile-aware FinKernel routing is available.
7. Treat profile-aware investment guidance as a FinKernel-first workflow, not a freeform chat answer.

## Artifact rules

- `persona_markdown` is the human/agent-readable canonical artifact.
- `persona_evidence` is the supporting evidence packet.
- Versions should be preserved through FinKernel profile versioning.
- The agent should not overwrite the persona blindly when review evidence conflicts; it should merge consciously.

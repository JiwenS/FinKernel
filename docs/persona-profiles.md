# Persona Profiles

Persona profiles are both:

- declarative control objects for FinKernel enforcement
- shared narrative documents for humans and agents

Phase 6 introduces a first-use onboarding path:

- if no active profile exists, profile-bound flows should redirect to onboarding
- onboarding can create the first active profile through a guided discovery session
- the existing file-backed profile store remains supported as a local seed/import path

They are stored in:
- `config/persona-profiles.json`

The machine-facing container can stay JSON for import/export, but the preferred
human/agent-readable representation is the rendered markdown document exposed as
`persona_markdown`.
FinKernel also exposes the rendered markdown document directly at:

- `GET /api/profiles/{profile_id}/persona.md`
- `GET /api/profiles/{profile_id}/persona-sources`
- MCP: `get_profile_persona_markdown`
- MCP: `get_profile_persona_sources`

## What a profile defines
- `profile_id`
- `owner_id`
- `version`
- `status`
- `display_name`
- `mandate_summary`
- `persona_style`
- `bucket_name`
- `risk_budget`
- `capital_allocation_pct`
- `allowed_accounts`
- `allowed_markets`
- `allowed_symbols`
- `forbidden_symbols`
- `allowed_actions`
- `hitl_required_actions`
- rendered `persona_markdown`
- optional layered memory payloads such as:
  - `hard_rules`
  - `contextual_rules`
  - `long_term_memories`
  - `short_term_memories`

## Markdown-first persona representation

`persona_markdown` is the primary shared context for downstream agents and user-facing
surfaces. It should be synthesized from discovery / review dialogue evidence first,
not reverse-rendered from structured fields.

The fixed-schema fields still matter, but only for cases where FinKernel needs
deterministic enforcement or database-friendly indexing:

- account / market / symbol scope
- action permissions and HITL gates
- lifecycle and version metadata
- capital allocation and risk-envelope controls

If a piece of meaning is contextual, time-bound, or difficult to normalize without
loss, prefer natural-language markdown over inventing a new tag.

In practice, the intended direction is:

- conversation / review evidence -> persona markdown
- persona markdown + selected evidence -> structured projections for enforcement

not the other way around.

FinKernel does **not** call a model to author personas.
Instead, upper-layer agents should:

1. read dialogue evidence and memory from FinKernel
2. use the prompts under `prompts/`
3. author `persona_markdown` themselves
4. write the final artifact back into FinKernel

The prompts explicitly instruct the agent to follow the user's dominant language.
This is not limited to Chinese or English.

## Long-term vs short-term memory

FinKernel now distinguishes between:

- `long_term_memories`
  - stable user traits and narrative background
  - examples: chronic risk aversion, sector sensitivity, durable communication preference
- `short_term_memories`
  - temporary context with higher short-horizon relevance
  - examples: upcoming trip, near-term cash need, temporary caution after recent volatility

The intended runtime interpretation is:
- hard rules define non-negotiable boundaries
- short-term memory influences the current recommendation horizon
- long-term memory provides stable background and weighting

Rendered markdown should keep these memory layers explicit so temporary constraints
do not get mistaken for durable traits.

## Four-dimensional evaluation

Rendered persona documents should organize their interpretation around four fixed
evaluation pillars:

1. financial objectives
2. risk posture
3. constraints and concentration
4. background and collaboration

This keeps the output readable for humans while preserving a stable frame for agents.

## Lifecycle
Profiles can now carry lifecycle metadata such as:
- `draft`
- `discovery_in_progress`
- `pending_user_confirmation`
- `active`
- `under_review`
- `superseded`
- `archived`

## What a profile does **not** define
- imperative trading logic
- autonomous advisor behavior
- direct buy/sell recommendations authored by FinKernel

## Current sample profiles
- `growth`
- `low-risk`
- `research`

## Example intent
- `growth` — can observe, simulate, request execution, refresh, reconcile, cancel inside its declared scope and uses its declared capital slice
- `low-risk` — restricted to a more conservative symbol set and only sees its declared capital slice
- `research` — observe/refresh/reconcile only

## Binding rule
Every relevant request must declare:
- `x-profile-id`

FinKernel then resolves the profile and enforces:
- account scope
- symbol scope
- action scope
- HITL requirement
- capital/bucket allocation for simulation/risk outputs

## Why capital allocation matters

Two personas can point at the same underlying broker account but still manage different conceptual portfolio slices.

`capital_allocation_pct` gives FinKernel a declarative capital envelope for:
- cash shown in simulation
- buying power shown in simulation
- equity framing in risk summaries

This prevents every persona from implicitly seeing the full broker account as its usable capital.

## Onboarding / discovery surfaces

HTTP:
- `GET /api/profiles/onboarding-status`
- `GET /api/profiles/{profile_id}`
- `GET /api/profiles/{profile_id}/persona.md`
- `GET /api/profiles/{profile_id}/persona-sources`
- `PUT /api/profiles/{profile_id}/persona`
- `GET /api/profiles/{profile_id}/versions`
- `POST /api/profiles/{profile_id}/review`
- `POST /api/profiles/discovery/sessions`
- `GET /api/profiles/discovery/sessions/{session_id}/next-question`
- `POST /api/profiles/discovery/sessions/{session_id}/answers`
- `POST /api/profiles/discovery/sessions/{session_id}/draft`
- `POST /api/profiles/discovery/drafts/{draft_id}/confirm`

MCP:
- `get_profile_onboarding_status`
- `get_profile`
- `get_profile_persona_markdown`
- `get_profile_persona_sources`
- `save_profile_persona_markdown`
- `list_profile_versions`
- `review_profile`
- `start_profile_discovery`
- `get_next_profile_question`
- `submit_profile_discovery_answer`
- `generate_profile_draft`
- `confirm_profile_draft`

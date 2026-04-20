# Persona Agent Workflow

This document describes the intended workflow for an upper-layer AI agent that authors
`persona_markdown` using FinKernel as the evidence store and artifact substrate.

## Core principle

FinKernel does **not** generate persona prose itself.

Instead:

1. FinKernel stores discovery answers, memory, versions, and the current persona artifact.
2. The upper-layer agent reads the source packet from FinKernel.
3. The upper-layer agent uses the prompts under `prompts/` to analyze and write persona text.
4. The upper-layer agent writes the final markdown artifact back into FinKernel.

## Inputs the agent should use

Read these from FinKernel:

- current profile via `get_profile` / `GET /api/profiles/{profile_id}`
- persona source packet via `get_profile_persona_sources` / `GET /api/profiles/{profile_id}/persona-sources`
- current persona artifact via `get_profile_persona_markdown` / `GET /api/profiles/{profile_id}/persona.md`
- historical versions via `list_profile_versions`
- active long-term / short-term memory already included in the source packet

Read these from the repository:

- `prompts/persona_analyzer.md`
- `prompts/persona_builder.md`
- `prompts/persona_merger.md`
- `prompts/persona_correction.md`
- `SKILL.md`

## Recommended authoring flow

### A. Initial onboarding flow

1. Start discovery
2. Answer all discovery questions
3. Generate profile draft
4. Read `suggested_profile.persona_evidence` from the draft
5. Run the analyzer prompt on the evidence and memory
6. Run the builder prompt to produce final `persona_markdown`
7. Confirm the draft with `persona_markdown`

### B. Review / update flow

1. Start review for an existing profile
2. Generate the review draft
3. Read:
   - old `persona_markdown`
   - new `persona_evidence`
   - current memory
4. Run analyzer + merger + builder
5. Confirm the review draft with the updated `persona_markdown`

### C. Direct correction flow

If the user says the persona is wrong:

1. read the current persona source packet
2. gather the correction as new evidence
3. run the correction prompt
4. if needed, run the merger prompt
5. regenerate the persona using the builder prompt
6. write back with `save_profile_persona_markdown`

## Tool routing

### HTTP

- `GET /api/profiles/{profile_id}`
- `GET /api/profiles/{profile_id}/persona-sources`
- `GET /api/profiles/{profile_id}/persona.md`
- `PUT /api/profiles/{profile_id}/persona`
- `GET /api/profiles/{profile_id}/versions`
- discovery / review endpoints under `/api/profiles/discovery/...`

### MCP

- `get_profile`
- `get_profile_persona_sources`
- `get_profile_persona_markdown`
- `save_profile_persona_markdown`
- `list_profile_versions`
- discovery / review tools

## Writing rules the agent should follow

- Use conversation evidence as the primary source of truth.
- Use the user's dominant language for the final persona.
- This language rule applies to all languages, not only Chinese or English.
- Distinguish stable traits from temporary context.
- Preserve time-sensitive constraints in prose.
- Do not turn the persona into YAML/JSON style text.
- Treat structured control fields as operational boundaries, not as the source of personality.

## Where routing rules should live

- `SKILL.md` is the top-level agent-facing orchestration layer.
- `prompts/*.md` are single-stage reasoning / writing assets.
- `docs/*.md` explain the system to maintainers and integrators.

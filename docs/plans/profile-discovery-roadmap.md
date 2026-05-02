# Profile Discovery Roadmap

This plan tracks the gap between the current implementation and
`docs/profile-discovery-architecture.md`.

The architecture direction is already clear: FinKernel profile discovery should
be an agent-first adaptive interview. The backend should store sessions,
turns, accepted interpretation packets, working profile state, coverage, drafts,
and final profile versions. The agent and prompt layer should handle semantic
interpretation and dynamic follow-up wording.

## Current baseline

The current implementation already includes:

- four Phase 1 discovery sections:
  - `financial_objectives`
  - `risk`
  - `constraints`
  - `background`
- structured discovery dimensions for each section
- discovery sessions, turns, accepted interpretations, working snapshots, and
  section coverage
- HTTP and MCP tools for profile assessment, discovery state, interpretation
  submission, draft generation, and draft confirmation
- prompt assets for discovery question generation and answer extraction
- tests that cover the direct packet-submission workflow and key validation
  failures

## Remaining gaps

### 1. Agent orchestration is not yet a product-grade loop

The runtime can accept agent-produced interpretation packets, but there is not
yet a reusable host adapter or runner that guarantees this loop:

1. inspect discovery state
2. ask starter question or generate one follow-up
3. collect the answer
4. run answer extraction
5. submit the interpretation packet
6. read updated state silently
7. continue or generate the final profile markdown

### 2. Dynamic follow-up generation is defined but not fully exercised

Follow-up behavior is documented in `prompts/discovery_question_generator.md`,
but tests mostly submit complete synthetic packets. The system still needs
tests and examples that exercise real multi-turn discovery within one section.

### 3. Coverage and confidence need a stronger engineering contract

Coverage exists as section and dimension state, but confidence remains a simple
label-to-score mapping. Conflict and gap details need a more explicit
dimension-level structure so the next question can target the right unresolved
issue.

### 4. Structured field contracts need to be stricter

Runtime validation checks decimal, integer, enum, and list formats, but the
field contract is not yet published as a standalone schema reference. The agent
prompt tells the model what shape to return, but future hosts should also have a
deterministic contract they can validate against.

### 5. Draft assembly is incremental in state, not yet incremental in artifact

Accepted interpretation packets update the working snapshot incrementally, but
draft generation still happens as a late-stage assembly step. The next design
step is to expose a stable draft source packet that can be audited before final
profile markdown confirmation.

### 6. Legacy persona naming still leaks through compatibility surfaces

The preferred product term is `profile`, while `persona` is a sublayer inside
that profile. Existing APIs and storage fields still expose names such as
`assess_persona`, `PersonaProfile`, `persona_markdown`, and `persona_evidence`.
Those names can remain for compatibility, but new product surfaces should use
profile-first terminology.

## Implementation plan

### P0: Stabilize the discovery contract

- Publish the interpretation packet contract as a first-class document.
- Add dimension-level remaining gap and conflict fields while preserving current
  packet compatibility.
- Validate that structured gap and conflict dimensions belong to the submitted
  section.
- Add tests for dimension-level gap/conflict handling and invalid issue scope.

### P1: Build a reference agent discovery loop

- Add a host-side reference runner or integration fixture that follows the
  documented discovery loop.
- Exercise starter question, dynamic follow-up generation, answer extraction,
  interpretation submission, and state refresh.
- Add multi-turn tests where one section starts incomplete, receives a
  clarifying follow-up, and only then becomes covered.

### P2: Design confidence and coverage v1

- Define field-level confidence, section-level confidence, evidence quality, and
  conflict state semantics.
- Clarify how partial profile updates compute section progress.
- Keep semantic judgment agent-produced while making MCP validation and state
  transitions deterministic.

### P3: Formalize draft source and markdown confirmation

- Expose a stable draft source packet assembled from working snapshot,
  evidence, memories, contextual rules, and accepted interpretations.
- Define `profile_builder` input and output requirements more strictly.
- Add an audit path that shows which final profile fields came from which
  accepted interpretation packets.

### P4: Clean up naming compatibility

- Add profile-first aliases for persona-named tools and fields where practical.
- Mark legacy names as compatibility surfaces in docs and tool descriptions.
- Prefer `profile markdown` and `profile evidence` in new docs, prompts, and
  user-facing copy.

## Progress log

### 2026-04-28

P0 has started and the first contract hardening pass is complete:

- added `docs/profile-discovery-interpretation-contract.md`
- added `dimension_remaining_gaps` and `dimension_conflict_notes`
- preserved compatibility with legacy `remaining_gaps` and `conflict_notes`
- added validation that dimension-scoped issues belong to the submitted section
- added tests for dimension-level gaps, invalid issue scope, and unresolved
  conflicts blocking `section_complete`

P1 has now started:

- added `src/finkernel/services/profile_discovery_loop.py`
- added a reference loop with injected question generation, answer collection,
  and answer extraction collaborators
- added a multi-turn test where `financial_objectives` starts incomplete, uses
  a dynamic follow-up, and only then becomes covered before draft generation

P2 has now started:

- added `docs/profile-discovery-confidence-coverage.md`
- defined the first engineering contract for coverage score, confidence score,
  evidence score, section evidence quality, and conflict blocking

P2 minimal runtime exposure is complete:

- added `evidence_score` to dimension state
- added `evidence_quality_label` and `blocked_by_conflicts` to section coverage
- kept draft readiness unchanged while exposing better host-facing audit state

P3 has now started:

- added `docs/profile-draft-source-contract.md`
- added `ProfileDraftSourcePacket`
- embedded `draft_source` on `ProfileDraft`
- updated `prompts/profile_builder.md` to treat `draft_source` as the canonical
  profile markdown input bundle
- added `field_sources` to map normalized profile fields back to accepted
  interpretation packets and evidence excerpts

P4 has now started:

- added profile-first aliases for profile assessment, profile markdown reads,
  profile sources, profile markdown saves, and draft confirmation
- kept legacy persona-named tools, fields, and routes for compatibility
- updated host-facing docs and skill instructions to prefer profile-first names

The next execution focus is hardening compatibility tests around legacy and
profile-first aliases.

# Profile Draft Source Contract

This document defines the stable source packet used to write final profile
markdown.

For the broader discovery architecture, see
`docs/profile-discovery-architecture.md`.

## Purpose

`ProfileDraftSourcePacket` is the canonical input bundle for
`prompts/profile_builder.md`.

It prevents profile markdown generation from depending on scattered runtime
state or hidden host memory. A host can read the draft, pass the draft source to
the profile builder prompt, then confirm the resulting markdown with
`confirm_profile_draft`.

## Source packet shape

The draft source is embedded on `ProfileDraft` as `draft_source`.

It contains:

- `session_id`
- `owner_id`
- `workflow_kind`
- `source_profile_id`
- `readiness`
- `section_coverage`
- `working_profile_snapshot`
- `conversation_turns`
- `accepted_interpretations`
- `field_sources`
- `evidence_count`
- `long_term_memory_count`
- `short_term_memory_count`
- `contextual_rule_count`

## Builder input order

When writing profile markdown, the host should treat the source packet in this
priority order:

1. `accepted_interpretations[].packet.evidence_snippets`
2. `working_profile_snapshot.persona_evidence`
3. confirmed structured fields inside `working_profile_snapshot`
4. contextual rules
5. long-term memories
6. short-term memories
7. prior profile context when `source_profile_id` is present

The final markdown should not invent facts that are absent from this source
packet or prior confirmed profile context.

## Field source audit

`field_sources` maps normalized profile fields back to accepted interpretation
packets.

Each item contains:

- `field_path`
- `dimensions`
- `interpretation_ids`
- `evidence_excerpts`

Example field paths:

- `financial_objectives.target_annual_return_pct`
- `risk_boundaries.max_drawdown_limit_pct`
- `investment_constraints.blocked_tickers`
- `persona_traits.behavioral_risk_profile`

Hosts should use `field_sources` to audit final profile markdown and to explain
why a profile field was included when the user asks for provenance.

## Confirmation rule

`confirm_profile_draft` stores the final profile version using:

- the suggested structured profile from the draft
- the supplied final profile markdown
- an explicit `user_confirmed=true` confirmation from the host after the user
  approves the shown draft
- the draft source as the audit basis available in the saved draft payload

The markdown remains the user-facing artifact. The draft source remains the
host/runtime-facing audit artifact.

## Compatibility

Existing compatibility fields such as `persona_markdown` and `persona_evidence`
remain in API payloads. New documentation should describe them as profile
markdown and profile evidence unless referring to exact legacy field names.

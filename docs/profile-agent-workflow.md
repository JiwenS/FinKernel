# Profile Agent Workflow

This document describes the intended workflow for an upper-layer AI agent that
authors or revises the final profile markdown artifact.

This workflow belongs to Phase 1, where profile authoring exists to support the
personal risk profile system rather than a broader investment-planning stack.

## Conversation rule

During discovery, the user should experience one continuous interview rather
than repeated intermediate profile readouts.

That means:

- the agent keeps asking natural follow-up questions
- internal profile updates happen silently after each answer
- conflicts and remaining gaps guide the next question internally
- the full profile markdown is shown only when discovery is complete or when
  the user explicitly asks to inspect it

## Current prompt assets

- `prompts/profile_assessment.md`
- `prompts/profile_analyzer.md`
- `prompts/profile_builder.md`
- `prompts/discovery_question_generator.md`
- `prompts/discovery_answer_extractor.md`
- `prompts/profile_narrative_builder.md`
- `prompts/profile_merger.md`
- `prompts/profile_correction.md`
- `SKILL.md`

## Create flow

1. Call `assess_profile` if available, otherwise call legacy `assess_persona`.
2. Use `prompts/profile_assessment.md` to keep the host wording aligned with the returned state.
3. Read `discovery_state` and identify the current section, its targeted dimensions, its outstanding dimensions, and the recent accepted interpretation history.
4. If a starter question is present, ask it. Otherwise use `prompts/discovery_question_generator.md` to produce one dynamic follow-up question.
5. After the user answers, use `prompts/discovery_answer_extractor.md` to create a strict interpretation packet.
6. Submit the interpretation packet to FinKernel and read back the updated discovery state, including section coverage and recent accepted interpretations.
7. Repeat until the draft is ready.
8. Read the draft and its `draft_source` packet.
9. Use `prompts/profile_analyzer.md` to structure the evidence.
10. Use `prompts/profile_builder.md` to write the final markdown in the investment profile template format.
11. Confirm the draft with the final profile markdown artifact.

The host should treat steps 5 and 6 as internal orchestration steps. Do not
turn every internal update into a user-facing status dump.

The reference implementation for this loop lives in
`src/finkernel/services/profile_discovery_loop.py`. It exists to make the
expected host behavior testable: starter question, dynamic follow-up generation,
answer extraction, interpretation submission, state refresh, and optional draft
generation.

When a draft is ready, `ProfileDraft.draft_source` is the canonical source
packet for final markdown generation. It contains the working profile snapshot,
section coverage, accepted interpretation packets, and conversation turns needed
by `prompts/profile_builder.md`.

## Review flow

1. Call `assess_profile` if available, otherwise call legacy `assess_persona`.
2. If the profile is complete, present the returned update options and collect a section choice or full reassessment.
3. Use the same discovery loop as create flow: starter question if present, otherwise dynamic follow-up generation, then extraction and interpretation submission.
4. Continue until the draft is ready.
5. Read current markdown, new evidence, and memory.
6. Use `prompts/profile_merger.md` when prior and new signals need reconciliation.
7. Rebuild the markdown and confirm the new version.

## Correction flow

1. Read the current profile source packet.
2. Translate the correction into explicit profile evidence.
3. Use `prompts/profile_correction.md`.
4. Save the updated markdown when the change does not require a full new version.

## Adaptive discovery direction

The discovery loop described in `docs/profile-discovery-architecture.md` uses:

- one open-ended starter question per section
- dynamic follow-up questioning based on the user's actual answers
- prompt-guided extraction of structured fields, evidence, and memory
- section completion based on information sufficiency rather than a static questionnaire

## Semantic boundary

This workflow assumes that text-heavy judgments such as:

- remaining gaps
- confidence
- contradictions
- durable versus temporary context

are first produced by the prompt-guided agent layer.

The deterministic FinKernel layer should accept and persist those judgments,
not pretend to infer them from free-form text on its own.

Those judgments are mainly used to steer the next question, not to interrupt
the user with backend terminology during the interview.

## Naming rule

In this workflow:

- `profile` refers to the overall object and final markdown artifact
- `persona` refers only to the personality and behavioral layer inside that profile

Profile-first tool aliases such as `assess_profile`, `get_profile_markdown`,
`get_profile_sources`, and `save_profile_markdown` should be preferred for new
host integrations. Legacy tool and field names such as `assess_persona` or
`persona_markdown` may still appear for compatibility, but they should not
change the product meaning.

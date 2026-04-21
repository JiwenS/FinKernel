# Persona Agent Workflow

This document describes the intended workflow for an upper-layer AI agent that
authors or revises `persona_markdown`.

This workflow belongs to Phase 1, where persona authoring exists to support the
personal risk profile system rather than a broader investment-planning stack.

## Prompt assets

- `prompts/persona_assessment.md`
- `prompts/persona_analyzer.md`
- `prompts/persona_builder.md`
- `prompts/persona_merger.md`
- `prompts/persona_correction.md`
- `SKILL.md`

## Create flow

1. Call `assess_persona`.
2. Continue the returned add flow until the draft is ready.
3. Use `prompts/persona_assessment.md` to keep the host wording aligned with the returned state.
4. Read the draft and `persona_evidence`.
5. Use `prompts/persona_analyzer.md` to structure the evidence.
6. Use `prompts/persona_builder.md` to write the final markdown.
7. Confirm the draft with `persona_markdown`.

## Review flow

1. Call `assess_persona`.
2. If the persona is complete, present the returned update options and collect a section choice or full reassessment.
3. Continue the returned update flow until the draft is ready.
4. Read current markdown, new evidence, and memory.
5. Use `prompts/persona_merger.md` when prior and new signals need reconciliation.
6. Rebuild the markdown and confirm the new version.

## Correction flow

1. Read the current profile source packet.
2. Translate the correction into explicit profile evidence.
3. Use `prompts/persona_correction.md`.
4. Save the updated markdown when the change does not require a full new version.

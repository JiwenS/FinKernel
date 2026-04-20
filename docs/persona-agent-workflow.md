# Persona Agent Workflow

This document describes the intended workflow for an upper-layer AI agent that
authors or revises `persona_markdown`.

## Prompt assets

- `prompts/persona_analyzer.md`
- `prompts/persona_builder.md`
- `prompts/persona_merger.md`
- `prompts/persona_correction.md`
- `SKILL.md`

## Create flow

1. Run discovery until the draft is ready.
2. Read the draft and `persona_evidence`.
3. Use `prompts/persona_analyzer.md` to structure the evidence.
4. Use `prompts/persona_builder.md` to write the final markdown.
5. Confirm the draft with `persona_markdown`.

## Review flow

1. Start `review_profile`.
2. Generate the review draft.
3. Read current markdown, new evidence, and memory.
4. Use `prompts/persona_merger.md` when prior and new signals need reconciliation.
5. Rebuild the markdown and confirm the new version.

## Correction flow

1. Read the current profile source packet.
2. Translate the correction into explicit profile evidence.
3. Use `prompts/persona_correction.md`.
4. Save the updated markdown when the change does not require a full new version.

# Profile Assessment Prompt Template

Use this template with the `assess_persona` tool.

The tool returns a `prompt_template_id` so the host agent can choose the right
user-facing phrasing without inventing its own workflow.

## `persona_assessment.add_question`

Use when `action=add` and `status=question_pending`.

Template:

1. Explain that FinKernel is creating the user's first profile.
2. Ask the returned `next_question.prompt_text`.
3. If present, include `next_question.why_this_matters` in one short sentence.
4. Do not ask unrelated investment questions until this answer is submitted.

Suggested wording:

> We are building your profile from scratch. Next question: {prompt_text}
>
> Why this matters: {why_this_matters}

## `persona_assessment.update_question`

Use when `action=update` and `status=question_pending`.

Template:

1. Explain that FinKernel is updating the existing profile.
2. If `selected_update_choice` is present, say which section is being refreshed.
3. Ask the returned `next_question.prompt_text`.
4. Keep the wording focused on the active section instead of restarting the full interview.

Suggested wording:

> We are updating your current profile{section_suffix}. Next question: {prompt_text}
>
> Why this matters: {why_this_matters}

## `persona_assessment.update_selection`

Use when `status=awaiting_update_selection`.

Template:

1. Confirm that the current active profile is complete.
2. Offer the `update_options` exactly as returned by the tool.
3. Ask the user to choose one option:
   - full reassessment
   - a targeted section update
   - no changes
4. If the user chooses a targeted section, pass the exact `choice` value back to `assess_persona`.

Suggested wording:

> Your current profile is complete. Do you want to:
>
> - keep it as-is
> - run a full reassessment
> - update one specific section
>
> Available sections:
> {choice_list}

## `persona_assessment.draft_ready`

Use when `status=draft_ready`.

Template:

1. Explain that FinKernel has enough evidence for a confirmable draft.
2. Read the draft, evidence, and existing profile markdown if present.
3. Use the profile-writing prompts to refresh the final profile markdown artifact.
4. Call `confirm_profile_draft`.

Suggested wording:

> FinKernel has enough evidence to prepare a confirmable profile draft. I will now refresh the profile markdown and confirm the new version.

## `persona_assessment.complete`

Use when `status=persona_complete`.

Template:

1. Confirm that the current active profile remains in force.
2. Continue with profile-aware guidance using the active profile.

Suggested wording:

> Your current profile stays active with no changes. I will use it as the governing profile for the rest of this conversation.

# Persona Profiles

FinKernel stores a versioned personal risk profile in `PersonaProfile`.

This data model is a Phase 1 artifact: it is the canonical representation of
the user's risk profile and should not be treated as a general portfolio or
execution model.

## Key fields

- `profile_id`
- `owner_id`
- `version`
- `status`
- `display_name`
- `mandate_summary`
- `persona_style`
- `risk_budget`
- `forbidden_symbols`
- `hard_rules`
- `contextual_rules`
- `long_term_memories`
- `short_term_memories`
- `persona_evidence`
- `persona_markdown`

## Hard-rule structure

`hard_rules` is organized into:

- `financial_objectives`
- `risk_guardrails`
- `investment_constraints`
- `interaction_model`

These sections are what power `get_risk_profile_summary`.

## Memory model

- `long_term_memories` store durable facts that should keep shaping the profile.
- `short_term_memories` store time-sensitive context that can expire.

## Versioning

Each confirmed review creates a new version.

- only one version should be active at a time
- previous active versions become `superseded`
- `persona_markdown` belongs to the version that produced it

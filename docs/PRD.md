# FinKernel PRD

## Product focus

FinKernel now exists to produce a durable, reviewable, machine-readable and
human-readable **personal risk profile**.

This profile should answer:

- what the money is for
- what downside feels unacceptable
- what liquidity obligations matter
- what concentration or exclusion rules should shape future guidance
- how the user wants advice framed and revisited

## In scope

- guided onboarding across core risk dimensions
- profile draft generation
- explicit user confirmation into an active version
- versioned profile review
- persona markdown maintenance
- long-term and short-term profile memory
- MCP and HTTP access for host agents

## Out of scope

- order execution
- broker integration
- simulation engines
- suggestion approval workflows
- control-plane reconciliation

## Success criteria

1. A new user can complete discovery and confirm an active profile.
2. A host agent can retrieve a stable risk-profile summary before giving advice.
3. Profile revisions create a new version instead of silently overwriting history.
4. Persona markdown stays aligned with the structured profile and evidence.

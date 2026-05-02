# Upper-Layer Agent Integration

FinKernel is responsible for profile onboarding, risk-profile retrieval,
profile evidence storage, and profile markdown maintenance.

That is the full Phase 1 boundary: upper-layer agents should treat FinKernel as
the dedicated risk-profile layer first, and only add broader investment logic
after profile context is resolved.

An upper-layer agent should use FinKernel before presenting profile-aware
investment guidance.

## HTTP contract

- `GET /api/profiles/onboarding-status`
- `POST /api/profiles/assess-persona`
- `GET /api/profiles/{profile_id}`
- `GET /api/profiles/{profile_id}/risk-summary`
- `GET /api/profiles/{profile_id}/persona.md`
- `GET /api/profiles/{profile_id}/persona-sources`
- `PUT /api/profiles/{profile_id}/persona`
- `POST /api/profiles/discovery/sessions`
- `GET /api/profiles/discovery/sessions/{session_id}/state`
- `POST /api/profiles/discovery/sessions/{session_id}/interpretation`
- `POST /api/profiles/discovery/sessions/{session_id}/draft`
- `POST /api/profiles/discovery/drafts/{draft_id}/confirm`
- `POST /api/profiles/{profile_id}/review`
- `POST /api/profiles/{profile_id}/memories`
- `GET /api/profiles/{profile_id}/memories/search`
- `POST /api/profiles/{profile_id}/memories/distill`

## MCP equivalents

- `assess_persona`
- `get_profile_onboarding_status`
- `get_profile`
- `get_profile_persona_markdown`
- `get_risk_profile_summary`
- `review_profile`

## Integration rule

Do not give final profile-aware guidance until one of these is true:

1. onboarding has completed and an active profile exists
2. the host agent has explicitly told the user that FinKernel profile context is unavailable

## Recommended read sequence

1. `GET /api/profiles/onboarding-status`
2. `GET /api/profiles/{profile_id}`
3. `GET /api/profiles/{profile_id}/persona.md`
4. `GET /api/profiles/{profile_id}/risk-summary`
5. optional memory reads when the answer depends on current context

For dedicated profile-building flows, the host may instead use
`POST /api/profiles/assess-persona` as the single orchestration checkpoint
before each discovery-state refresh, draft, or update prompt.

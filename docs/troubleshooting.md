# Troubleshooting

## No active profile exists

Symptom:

- profile reads return `PROFILE_ONBOARDING_REQUIRED`

Fix:

- start `POST /api/profiles/discovery/sessions`
- continue discovery until the draft is confirmed

## Discovery draft is not ready

Symptom:

- draft generation returns `DISCOVERY_NOT_READY`

Fix:

- inspect `GET /api/profiles/discovery/sessions/{session_id}/state`
- keep submitting interpretation packets until every required section is covered before generating the draft

## MCP tools are registered but not used first

Symptom:

- the host agent gives generic finance advice before reading FinKernel

Fix:

- register FinKernel MCP
- inject `prompts/finkernel_system_routing.md`
- verify the first profile-aware tool call is `get_profile_onboarding_status`

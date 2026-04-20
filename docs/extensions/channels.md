# Adding a Channel Connector

Channel/HITL plugins should fit the existing channel interface in:
- `src/finkernel/services/interfaces.py`

Current required channel methods:
- `send_confirmation(...)`
- `send_status_update(...)`

## Where channel code lives
- `src/finkernel/connectors/channels/`

## Recommended workflow
1. Create a new module under `src/finkernel/connectors/channels/`
2. Implement confirmation send and status-update send
3. Ensure actor identity from the channel can be mapped back into the workflow path
4. Preserve HITL semantics — the channel does not become an execution shortcut
5. Add tests and update docs/examples

## Required behaviors
- Preserve request correlation
- Preserve actor attribution
- Keep channel-specific config externalized
- Never bypass workflow state machine or human approval requirement

## Minimal skeleton
See:
- `examples/channel_connector_skeleton.py`

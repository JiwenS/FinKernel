# FinKernel Phase 2 Operator Control Plane

This runbook covers the read/control surfaces that come after the first real Alpaca paper order:

- request list/detail
- audit lookup
- reconcile against Alpaca
- refresh from Alpaca
- cancel an eligible live order
- startup recovery for in-flight requests

## Active profile binding

Phase 4 adds a required declarative profile binding for control-plane and execution requests:

- `x-profile-id: <profile_id>`

Profiles are loaded from:

- `config/persona-profiles.json`

The profile defines which accounts, symbols, and action classes are allowed.

## Endpoints

Use the API prefix configured for the service, typically `/api`.

- `GET /api/requests`
  - List recent workflow requests.
  - Use this first when you need to find the `request_id`.
- `GET /api/requests/{request_id}`
  - Fetch the canonical request record.
  - This should include workflow state, broker identifiers, request source, and terminal error fields.
- `GET /api/requests/{request_id}/audit`
  - Fetch the audit trail for one request.
  - Use this to answer who/what/when for policy, HITL, submission, and failure events.
- `POST /api/requests/{request_id}/reconcile`
  - Compare local state with Alpaca truth.
  - Use this for stuck, ambiguous, or drifted requests.
- `POST /api/requests/{request_id}/refresh`
  - Force a broker-backed status refresh for one request.
  - Use this when you want the latest current state without waiting for the background loop.
- `POST /api/requests/{request_id}/cancel`
  - Attempt to cancel an eligible live order.
  - Use this only for orders that are still open/cancelable.

All of these endpoints should now be called with `x-profile-id`.

## What reconciliation does

Reconciliation is a read-first repair action.

- It compares local workflow truth with broker truth.
- It records the reconciliation outcome.
- It may mark a request as matched, drifted, missing, or broker-error.
- It does **not** create a new trade or bypass policy/HITL.

## Startup recovery

On restart, the service should scan any in-flight requests and reconcile them before they are treated as final.

Typical recovery targets:

- `SUBMITTING`
- `SUBMITTED`
- any request with a broker order ID that is not yet terminal locally

Recovery should:

1. load the request from PostgreSQL
2. query Alpaca using `broker_order_id` or `client_order_id`
3. compare broker truth with local truth
4. persist the reconciliation result
5. leave unrecoverable cases explicit instead of guessing

Do not expect the request to stay silently stale after restart.

## Operator workflow

### 1) Find the request

```text
GET /api/requests
```

Filter by request state, symbol, account, or recent time window if needed.

### 2) Inspect the request

```text
GET /api/requests/{request_id}
GET /api/requests/{request_id}/audit
```

Look for:

- `request_source`
- `broker_order_id`
- current workflow state
- last error / reason code
- approval and submission audit events

### 3) Reconcile if the state looks wrong

```text
POST /api/requests/{request_id}/reconcile
```

Use this when the request is:

- stuck in `SUBMITTING`
- stuck in `SUBMITTED`
- marked successful locally but the broker disagrees
- missing a broker order ID
- recovering after a restart

### 3b) Refresh when you just need the latest broker-backed status

```text
POST /api/requests/{request_id}/refresh
```

Use this for:
- orders that are still open
- validating whether an ACKED order is still `new`
- checking whether a broker-side state moved to partially filled / filled / canceled

### 3c) Cancel an eligible live order

```text
POST /api/requests/{request_id}/cancel
```

Use this when:
- the request is still open/cancelable
- the operator wants to stop execution before fill
- you need a broker-backed cancellation path with audit

### 4) Re-check the result

Read the request again and confirm the state changed for a clear reason.

## Rules of thumb

- Prefer read + reconcile over manual DB edits.
- Prefer refresh + reconcile over manual DB edits.
- Treat `PENDING_CONFIRMATION` as a local workflow state, not a broker state.
- Treat drift as an explicit signal, not a hidden failure.
- Keep operator actions idempotent and auditable.
- Use app logs to correlate `request_id`, `request_source`, `broker_order_id`, and reconciliation outcome without opening the database.

## Escalate when

- Alpaca returns repeated lookup errors
- the request has no broker identifier and should have one
- local and broker state cannot be aligned automatically
- audit data is missing for a request that should be traceable

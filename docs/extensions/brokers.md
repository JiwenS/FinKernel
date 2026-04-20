# Adding a Broker Connector

Broker plugins should fit the broker adapter surface in:
- `src/finkernel/services/interfaces.py`
- `src/finkernel/connectors/brokers/base.py`
- `src/finkernel/connectors/brokers/registry.py`

Current required broker methods:
- `submit_order(...)`
- `get_order(...)`
- `cancel_order(...)`
- `get_account_summary()`
- `list_positions()`
- `get_latest_prices(symbols)`

## Where broker code lives
- `src/finkernel/connectors/brokers/`

## Recommended workflow
1. Create a new module under `src/finkernel/connectors/brokers/`
2. Implement the broker adapter methods
3. Expose a stable `broker_slug`
4. Normalize broker payloads into FinKernel schemas
5. Map broker errors into explicit connector error taxonomy
6. Register the adapter in `BrokerRegistry`
7. Add unit tests and one integration path
8. Update docs and examples

## Required behaviors
- Respect current workflow contracts
- Preserve raw broker payloads for audit/reconciliation
- Keep base URLs and identifiers configurable
- Never bypass policy/HITL/workflow logic
- Support the current MVP execution path: Alpaca paper + limit order
- Keep the adapter extensible for future advanced order types even if the current MVP only executes limit orders

## Minimal skeleton
See:
- `examples/broker_connector_skeleton.py`

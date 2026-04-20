# FinKernel

FinKernel is a Python/FastAPI modular monolith for **advisor-driven paper-trading infrastructure**. It combines a built-in recommendation loop with policy, HITL approval, execution, audit, and reconciliation so a paper-trading agent can run a full suggestion-to-trade workflow safely.

It now exposes both:
- **HTTP APIs** under `/api/...`
- **MCP Streamable HTTP** under `/api/mcp/`

## Read this first
- `docs/README.md` — documentation index
- `docs/setup-and-run.md` — setup, run, and E2E
- `docs/investment-conversation-routing.md` — how natural-language investment requests should route into onboarding, profile, and advisor flows
- `docs/upper-layer-agent-integration.md` — how an external agent should call FinKernel
- `docs/host-agent-runtime-integration.md` — how to register FinKernel MCP with a host agent and force FinKernel-first routing
- `docs/persona-profiles.md` — declarative persona/profile model
- `docs/persona-agent-workflow.md` - agent-authored persona flow and write-back protocol
- `SKILL.md` - top-level agent execution entrypoint for investment routing plus persona create/review/correction flows
- `prompts/finkernel_system_routing.md` - ready-to-copy host system prompt for FinKernel-first investment routing
- `docs/simulation-suggestion-substrate.md` — persona-aware facts, simulation, and candidate-action outputs
- `docs/extensions/brokers.md` — add a broker plugin
- `docs/extensions/channels.md` — add a channel plugin
- `docs/operator-control-plane.md` — request/audit/reconcile/refresh/cancel operations

## Current MVP boundaries

### In scope
- Built-in advisor / recommendation loop
- Strategy storage plus suggestion generation
- Python service boundary (FastAPI-class HTTP/MCP host)
- PostgreSQL as the system of record
- pgvector inside PostgreSQL for optional memory/search workloads
- Redis for transient workflow coordination and idempotency helpers
- Alpaca **paper** trading only
- Discord HITL confirmation flow
- Limit orders only
- Policy-first, workflow-first, audit-first execution

### Explicitly out of scope for the current MVP
- Live-money trading
- Simultaneous multi-broker production support
- Market/stop/advanced order execution
- Rich portfolio optimization and multi-signal strategy engines
- Multiple HITL channels
- A separate vector database unless PostgreSQL + pgvector proves unworkable

## Repository shape

Current code scaffolding follows the approved modular-monolith boundaries under `src/finkernel/`:

- `transport/` - FastAPI / MCP-facing entrypoints
- `policy/` - allow/block/require-confirmation decisions
- `workflow/` - state machine and confirmation lifecycle
- `audit/` - structured trace and decision records
- `identity/` - authn/authz context
- `connectors/brokers/` - broker adapters (V1: Alpaca)
- `connectors/channels/` - HITL adapters (V1: Discord)
- `storage/` - PostgreSQL / Redis integration seams
- `schemas/` - canonical request/response contracts
- `services/` - orchestration services that compose the modules

## Local deployment

`docker-compose.yml` now brings up the full local stack:

- **FinKernel app** via the local `Dockerfile`
- **PostgreSQL 16 + pgvector** via `pgvector/pgvector:pg16`
- **Redis 7** with append-only persistence enabled

This is the fastest path to E2E testing with real Discord + Alpaca paper credentials.

## Quick start

1. Copy the template:
   - PowerShell: `Copy-Item .env.example .env`
2. Fill in the required secrets:
   - `ALPACA_API_KEY`
   - `ALPACA_SECRET_KEY`
   - `DISCORD_BOT_TOKEN`
   - `DISCORD_CHANNEL_ID`
   - `DISCORD_ALLOWED_USER_IDS_CSV`
3. Start the full stack:
   - `docker compose up --build -d`
4. Confirm health:
   - `docker compose ps`
   - `docker compose logs app postgres redis --tail=100`
   - Open `http://localhost:8000/api/health`
   - Or run `.\scripts\e2e-healthcheck.ps1`

### E2E deployment notes
- Inside Docker Compose, the app connects to PostgreSQL and Redis over service DNS (`postgres`, `redis`).
- You still provide real external credentials for:
  - Alpaca paper
  - Discord bot + channel
- For quick local iteration, the app image installs directly from this repo via `pip install .`.

## Fast E2E flow

### 1. Bring the stack up
```powershell
Copy-Item .env.example .env
# edit .env with your real Alpaca + Discord values
docker compose up --build -d
.\scripts\e2e-healthcheck.ps1
```

### 2. Submit a real paper-trade request
```powershell
.\scripts\e2e-submit-limit-order.ps1 -ProfileId growth -Symbol AAPL -Side buy -Quantity 1 -LimitPrice 100.00
```

This creates a workflow item and prints the `request_id`.

### Advisor-first flow

FinKernel now also supports an advisor-led loop:

1. Create a strategy under a profile
2. Run the advisor loop once or let the background loop run
3. Inspect the generated suggestion
4. Approve in Discord or via API
5. Let FinKernel submit the resulting **limit** order to Alpaca paper

Helpful scripts:
- `.\scripts\e2e-create-strategy.ps1`
- `.\scripts\e2e-create-strategy-from-text.ps1`
- `.\scripts\e2e-run-advisor-once.ps1`
- `.\scripts\e2e-get-suggestions.ps1`

### MCP endpoint

If your agent speaks MCP, point it to:

- `http://localhost:8000/api/mcp/`

This MCP surface exposes tools for:
- strategy creation
- advisor execution
- suggestion inspection and approval
- portfolio/risk reads
- request refresh / reconcile / cancel

If you are wiring a host agent or orchestration layer, do not stop at MCP
registration alone. Use:

- `config/host-agent-mcp-http.example.json`
- `config/host-agent-mcp-stdio.example.json`
- `prompts/finkernel_system_routing.md`

The host must both register the MCP server and inject FinKernel-first routing
instructions, otherwise investment questions may still fall back to generic
finance chat or web search.

### 3. Approve in Discord
- Watch your configured Discord channel.
- FinKernel posts an approval message with **Approve / Reject buttons**.
- Preferred path: click the button directly in Discord.
- Fallback path: the message also contains the command format:
  - `!approve <request_id> <token>`
  - `!reject <request_id> <token>`

### 4. Poll final state
```powershell
.\scripts\e2e-get-trade-request.ps1 -ProfileId growth -RequestId <request_id>
```

Expected state progression:
- `PENDING_CONFIRMATION`
- `SUBMITTING`
- `SUBMITTED`
- `ACKED`

If the broker rejects or credentials are wrong, the request ends in `FAILED` with normalized error fields.

## Configuration notes

### PostgreSQL + pgvector
- Default DSN after copying `.env.example`: `postgresql+psycopg://finkernel:change-me@localhost:5432/finkernel`
- Compose uses the `pgvector/pgvector` image so `CREATE EXTENSION IF NOT EXISTS vector;` is available during app bootstrap/migrations.

### Redis
- Default URL: `redis://localhost:6379/0`
- Intended for short-lived confirmation state, replay protection, and idempotency helpers.
- The compose defaults are for **local development only**; Redis is exposed on the host and intentionally has no password in this MVP baseline.

### Alpaca paper
- `ALPACA_BASE_URL` defaults to `https://paper-api.alpaca.markets`
- Keep V1 pinned to paper trading until the policy/audit envelope is proven end-to-end.

### Discord HITL
- V1 assumes a dedicated Discord bot and channel for confirmations.
- Required configuration for the current implementation: `DISCORD_BOT_TOKEN`, `DISCORD_CHANNEL_ID`, `DISCORD_ALLOWED_USER_IDS_CSV`, and optionally `DISCORD_COMMAND_PREFIX`.
- Approval happens directly in Discord using **message buttons**. The bot message also includes fallback text commands such as `!approve <request_id> <token>` or `!reject <request_id> <token>`.
- Only Discord user IDs in `DISCORD_ALLOWED_USER_IDS_CSV` may approve or reject trade requests.

### Minimal `.env` checklist for E2E
- `ALPACA_API_KEY`
- `ALPACA_SECRET_KEY`
- `DISCORD_BOT_TOKEN`
- `DISCORD_CHANNEL_ID`
- `DISCORD_ALLOWED_USER_IDS_CSV`
- Optional tightening:
  - `ALLOWED_SYMBOLS_CSV`
  - `MAX_LIMIT_ORDER_NOTIONAL`
  - `MAX_LIMIT_ORDER_QTY`

## Minimal operating expectations for the current MVP

A successful advisor-led MVP flow should follow this sequence:

1. Persist a declarative strategy for a profile.
2. Run the advisor loop and generate a suggestion.
3. Persist the suggestion and linked workflow request in PostgreSQL.
4. Request human approval in Discord or via the advisory API.
5. Submit a **limit order** to Alpaca paper only after approval.
6. Persist audit and reconciliation outcomes.

## Environment files

- `.env.example` documents the minimum configuration surface.
- `.env` is local-only and ignored by git.

## Documentation contract

FinKernel is not considered complete unless docs and implementation match.

At minimum, every feature round should keep these surfaces synchronized:
- setup/run docs
- integration contract docs
- persona/profile docs
- extension docs
- scripts/examples

See `docs/README.md` for the full documentation map.

## Declarative persona profiles

FinKernel loads **user-defined declarative profiles** from:

- `config/persona-profiles.json`

These profiles define:
- owner id
- profile id / display name
- mandate summary / persona style
- bucket_name
- capital_allocation_pct
- allowed accounts
- allowed symbols / markets
- allowed action classes (`observe`, `request_execution`, `refresh`, `reconcile`, `cancel`)

Requests now bind to a profile via:
- `x-profile-id`

This lets advisor strategies, upper-layer agents, and execution workflows share a single declarative scope model.

## Persona-aware simulation / suggestion substrate

FinKernel exposes a structured decision-support substrate plus first-class advisor objects:
- `GET /api/portfolio/snapshot`
- `GET /api/portfolio/risk-summary`
- `POST /api/simulations/trade`
- `POST /api/candidate-actions/trade`
- `GET /api/alerts`
- `GET /api/strategies`
- `POST /api/strategies`
- `GET /api/suggestions`
- `GET /api/suggestions/{id}`
- `POST /api/suggestions/{id}/approve`
- `POST /api/suggestions/{id}/reject`
- `POST /api/advisor/run-once`

These endpoints are profile-scoped and are meant to feed upper-layer agents with:
- factual snapshots
- projected effects
- candidate actions
- monitoring facts

Simulation endpoints are still non-executing primitives. Direct advisor outputs now live in the strategy/suggestion surfaces and can be approved into execution workflows.

Example simulation:
```powershell
Invoke-RestMethod `
  -Method Post `
  -Uri http://localhost:8000/api/simulations/trade `
  -Headers @{ "x-profile-id" = "growth" } `
  -ContentType "application/json" `
  -Body (Get-Content examples/simulate-trade.json -Raw)
```

## Phase 2 observability notes

- Workflow state transitions are now logged with `request_id`, `request_source`, and `broker_order_id` when available.
- Broker submission outcomes and reconciliation outcomes are logged as structured key/value log lines.
- The app keeps lightweight in-memory counters for:
  - workflow state transitions
  - broker outcomes
  - reconciliation outcomes

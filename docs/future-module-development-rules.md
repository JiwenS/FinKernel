# Future Module Development Rules

This document captures the product and architecture rules that should guide
all FinKernel modules after the current profile foundation phase.

It is intentionally forward-looking. It does **not** mean News, Research,
Trade, Notifications, or managed portfolio workflows are already live.

## Current reality

Phase 1 remains profile-only.

Today, the shipped FinKernel surface is centered on:

- personal risk profile onboarding
- persona authoring and review
- profile memory
- MCP and HTTP retrieval for host agents

Today, the only shipped user-facing skill entry should be `FinKernel Profile`.
Do not expose a separate managed `Agent` entry while FinKernel is still
profile-only.

Future modules should extend this foundation without breaking the operating
rules below.

## Core rules

- Each business capability should have its own direct module entry.
- A managed or autonomous portfolio entry should stay separate from direct module entries.
- Do not make `profile` a universal hard dependency for every module.
- Prerequisites should depend on the user's operating mode, not just on the module name.
- Do not collect business configuration during installation.
- Configure capabilities inline during first use, then continue the interrupted task.
- Every configuration asset must be viewable, editable, and removable later.
- The managed orchestration layer should compose modules, not reimplement module logic.
- Documentation and product copy must clearly separate `live today` from `planned`.

## Entry surface model

FinKernel should evolve toward two entry classes.

### 1. Direct module entries

These are for explicit user intent: "do this task now."

Recommended entry surfaces:

| Entry surface | Primary job | Profile required? | Notes |
| --- | --- | --- | --- |
| `FinKernel Profile` | Build, continue, or revise the user's profile | No | This is the current Phase 1 anchor. |
| `FinKernel News` | Look up news, subscribe to feeds, manage filters | No for one-shot or subscription use | Profile becomes relevant only for personalized or managed flows. |
| `FinKernel Research` | Run a research task such as filing review or event analysis | No for one-shot analysis | Personalized or recurring research may add prerequisites later. |
| `FinKernel Trade` | Submit, amend, cancel, or review a user-directed order | No for explicit manual execution | Autonomous trading requires extra guardrails. |
| `FinKernel Settings` | View, edit, or delete saved config assets | No | Canonical management surface for later changes. |

Direct module entries should stay decoupled whenever the user intent is narrow
and explicit.

### 2. Managed entry

This is for intent such as:

- "manage my portfolio"
- "keep watching this for me"
- "notify me and act when conditions change"
- "run the system for me with guardrails"

Recommended future entry surface:

- `Finkernel Agent` or an equivalent host-visible orchestration label

This managed entry is a future construct. It should not be installed as a
separate primary skill during the current Phase 1 profile-only release.

The managed entry should:

- assess readiness across modules
- identify missing prerequisites
- route the user into the minimum setup needed
- start recurring monitoring or automation only after requirements are satisfied

The managed entry should **not** absorb all module logic into one giant skill or prompt.

## Operating modes

Dependencies should be evaluated by operating mode.

| Operating mode | Typical user intent | Dependency style |
| --- | --- | --- |
| `interactive_one_shot` | "Analyze this earnings report", "Buy 10 shares of AAPL", "Show me NVDA news" | Minimal prerequisites. Only require what is needed for the immediate task. |
| `subscription_monitoring` | "Send me news alerts", "Track this watchlist", "Notify me when price crosses X" | Requires durable source setup and a usable notification policy. |
| `managed_autonomous` | "Manage this portfolio", "Continuously monitor and act within my rules" | Requires cross-module readiness checks, profile context, notification policy, and execution guardrails where applicable. |

This is the main rule that prevents over-gating simple tasks.

## Module prerequisite guidelines

These are the default expectations future modules should follow unless a later
design decision explicitly overrides them.

| Module | One-shot use | Subscription or monitoring use | Managed or autonomous use |
| --- | --- | --- | --- |
| `Profile` | No prerequisites | Not applicable | Required when the system will personalize ongoing judgments or risk-sensitive actions |
| `News` | Needs only the request target and available data sources | Needs source selection, filters, and notification policy | May also require profile or watchlists if alerts become personalized |
| `Research` | Needs the requested topic, symbol, or document | Needs saved coverage scope or recurring triggers | Usually benefits from profile and watchlists when research informs managed decisions |
| `Trade` | Needs broker connectivity, order validation, and explicit user intent | Needs notification policy for fills, failures, or alerts | Requires profile, execution policy, approval policy, broker setup, and notification policy |
| `Notifications` | Optional unless the current task asks for push delivery | Required | Required for any long-running managed loop that must alert the user |

## Configuration rules

Business configuration should be collected inside the module flow that needs it.

### What installation should do

Installation should only set up runtime infrastructure:

- Docker services
- local environment variables
- skill bundles
- MCP registration

### What installation should not do

Installation should not ask for:

- news subscriptions
- notification channels
- notification cadence
- broker credentials
- portfolio policies
- watchlists or coverage universes

### Required first-use behavior

When a user first enters a module and required setup is missing, the module should:

1. explain the missing prerequisite in product language
2. collect only the minimum required setup
3. save the result as a reusable config asset
4. return immediately to the interrupted task

### Required later-management behavior

Every saved configuration asset should be manageable later through
`FinKernel Settings` or another clearly documented management surface.

That means users must be able to:

- view
- edit
- disable
- delete

without waiting to re-trigger the original workflow.

## Notification design

Notifications should be treated as a shared capability, not as a universal
root dependency module.

The model should be split into two concepts:

### Notification channels

Examples:

- email
- SMS
- Telegram
- webhook
- app inbox

### Notification policies

Examples:

- which events should trigger a notification
- which channels should receive them
- cadence or batching behavior
- quiet hours
- urgent-only rules

### Design rule

Other modules should depend on a usable notification policy only when the
specific workflow actually needs push or recurring delivery.

Examples:

- A one-shot news lookup does not need notifications.
- A news subscription does need notifications.
- A manual order entry may not need notifications to be created.
- An automated trading loop does need notifications for approvals, failures,
  fills, or safety interrupts.

## Managed readiness contract

The future managed entry should use a stable readiness-style contract so host
agents and module skills can share the same operating state.

Suggested fields:

```json
{
  "mode": "interactive_one_shot",
  "requested_capability": "news",
  "available_capabilities": ["profile"],
  "missing_requirements": ["notification_policy"],
  "next_required_step": "setup_notifications",
  "requires_user_input": true,
  "requires_approval": false,
  "suggested_entry_surface": "FinKernel Settings",
  "suggested_prompt_template_id": "notification_setup"
}
```

The exact field names can evolve, but the semantics should stay stable:

- what the user is trying to do
- what is already ready
- what is missing
- what step should happen next
- whether the host should ask the user, wait for approval, or continue automatically

## Module implementation rules

Future module implementations should follow these boundaries:

- Each module owns its own state machine and prompt templates.
- Module-specific prompts should stay module-specific.
- The managed entry can call a module setup or execution flow, but should not duplicate it.
- Saved state should be durable and inspectable.
- Long-running loops must have explicit stop, pause, and change-policy controls.
- Any workflow that can trigger money movement must have a clear approval and audit model.

## Recommended build order

The current roadmap should expand in this order:

1. Finish and harden `Profile` as the first complete module.
2. Define a shared readiness and prerequisite contract.
3. Add saved configuration assets for notification channels and notification policies.
4. Add `News` as the first non-profile module.
5. Add `Research` and user-directed `Trade` entry surfaces.
6. Add the managed orchestration entry once at least two or three modules are stable.

## Guardrails for contributors

- Do not claim roadmap modules are production-ready before they exist.
- Do not force users through profile creation for unrelated direct tasks.
- Do not move business setup into `bootstrap-local.ps1`.
- Do not collapse the product into one monolithic agent prompt.
- Do not create hidden configuration that users cannot inspect later.
- Do not make notifications mandatory when the workflow does not need push delivery.

## Relationship to current docs

Use this document together with:

- `docs/PRD.md`
- `docs/persona-agent-workflow.md`
- `docs/investment-conversation-routing.md`
- `docs/upper-layer-agent-integration.md`
- `SKILL.md`

This file is the forward-looking development contract.
Those documents remain the source of truth for the currently shipped
profile-focused behavior.

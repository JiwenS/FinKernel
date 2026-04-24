# Persona Profiles

FinKernel stores a versioned personal risk profile in `PersonaProfile`.

This data model is a Phase 1 artifact: it is the canonical representation of
the user's risk profile and should not be treated as a general portfolio or
execution model.

For the full design contract, see:

- `docs/profile-schema-design.md`

## Key fields

- `profile_id`
- `owner_id`
- `version`
- `status`
- `display_name`
- `mandate_summary`
- `persona_style`
- `risk_budget`
- `financial_objectives`
- `risk_boundaries`
- `investment_constraints`
- `account_background`
- `persona_traits`
- `contextual_rules`
- `long_term_memories`
- `short_term_memories`
- `persona_evidence`
- `persona_markdown`

## Structured boundary model

Structured fields are split into four nested sections:

- `financial_objectives`
- `risk_boundaries`
- `investment_constraints`
- `account_background`

These sections hold the normalized data that future risk and execution systems
can consume directly.

Core examples inside those sections include:

- `target_annual_return_pct`
- `investment_horizon_years`
- `annual_liquidity_need`
- `liquidity_frequency`
- `max_drawdown_limit_pct`
- `max_annual_volatility_pct`
- `max_leverage_ratio`
- `single_asset_cap_pct`
- `blocked_sectors`
- `blocked_tickers`
- `base_currency`
- `tax_residency`
- `account_entity_type`
- `aum_allocated`
- `execution_mode`

## Trait and memory model

- `persona_traits` stores non-structured user characteristics such as
  `financial_literacy`, `wealth_origin_dna`, and `behavioral_risk_profile`
- `long_term_memories` store durable facts that should keep shaping the profile
- `short_term_memories` store time-sensitive context that can expire
- `persona_evidence` keeps direct dialogue excerpts as the source-of-truth layer

## Versioning

Each confirmed review creates a new version.

- only one version should be active at a time
- previous active versions become `superseded`
- `persona_markdown` belongs to the version that produced it

## Derived summary fields

`risk_budget` and `persona_style` are still stored because they are useful
summary handles for host agents and compatibility surfaces, but they are
derived from the richer profile rather than acting as the primary truth layer.

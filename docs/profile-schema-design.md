# Profile Schema Design

This document defines the Phase 1 profile contract that FinKernel should use
for ongoing development.

It replaces the older `hard_rules + forbidden_symbols` mental model with a
clearer split:

- structured boundary data for trading and risk systems
- non-structured traits, memories, and evidence for agent reasoning

## Design goal

The profile has two jobs at the same time:

1. provide machine-usable boundaries that can be enforced by future execution
   and risk engines
2. preserve human nuance, behavioral context, and memory so the agent can
   reason well and communicate well

This means FinKernel should never force all profile meaning into enums or flat
labels, and it should never leave hard risk boundaries as free-form prose only.

## Four pillars

FinKernel still evaluates the user through four top-level pillars:

1. `financial_objectives`
2. `risk`
3. `constraints`
4. `background`

Each pillar contains multiple discovery dimensions. A profile is not complete
until every required dimension inside these pillars is covered strongly enough
for draft generation.

## Layer 1: Structured boundary data

These fields are the machine-usable part of the profile. They are the agent's
"physical and mathematical boundaries" and should be stored in normalized form.

### Financial objectives

| Field | Type | Purpose |
| --- | --- | --- |
| `target_annual_return_pct` | `Decimal` | Core optimization target |
| `investment_horizon_years` | `int` | Hard horizon constraint |
| `annual_liquidity_need` | `Decimal` | Absolute annual cash requirement |
| `liquidity_frequency` | `enum` | `monthly`, `quarterly`, `annual`, or `none` |

Only absolute numbers or normalized choices belong here. Narrative milestone
stories do not belong in this layer.

### Risk boundaries

| Field | Type | Purpose |
| --- | --- | --- |
| `max_drawdown_limit_pct` | `Decimal` | Hard drawdown boundary |
| `max_annual_volatility_pct` | `Decimal` | Portfolio volatility ceiling |
| `max_leverage_ratio` | `Decimal` | Maximum leverage allowance |
| `single_asset_cap_pct` | `Decimal` | Single-asset concentration cap |

This layer defines the red lines that future trading or portfolio logic must
respect without reinterpretation.

### Investment constraints

| Field | Type | Purpose |
| --- | --- | --- |
| `blocked_sectors` | `list[str]` | Sector-level blocklist |
| `blocked_tickers` | `list[str]` | Ticker-level blocklist |
| `base_currency` | `str` | Valuation and settlement currency |
| `tax_residency` | `str` | Tax jurisdiction anchor |

Only rules that can be executed as filters, blocklists, or deterministic
configuration should be stored here.

### Account background

| Field | Type | Purpose |
| --- | --- | --- |
| `account_entity_type` | `enum` | `individual`, `trust`, or `corporate` |
| `aum_allocated` | `Decimal` | Capital allocated to this mandate |
| `execution_mode` | `enum` | `discretionary` or `advisory` |

This section is about account structure and permission boundaries, not a
general biography.

## Layer 2: Non-structured profile intelligence

These fields are the agent's "soul and memory". They should stay narrative,
high-signal, and evidence-rich rather than being collapsed into shallow enums.

### Persona traits

| Field | Type | Purpose |
| --- | --- | --- |
| `financial_literacy` | `str` | Communication and explanation depth |
| `wealth_origin_dna` | `str` | How the capital story changes trust and risk framing |
| `behavioral_risk_profile` | `str` | How the user actually behaves under stress |

Examples of the kind of content that belongs here:

- "The user understands equities and ETFs well but wants derivatives explained
  in plain English."
- "Founder-earned capital creates a preference for understandable business
  models over opaque stories."
- "The user says they can handle volatility, but fast selloffs create anxiety
  and a need for proactive updates."

### Long-term memory

Long-term memories capture durable drivers such as:

- market traumas or outsized wins
- deep family goals
- durable wealth-origin patterns that should keep shaping recommendations
- stable trust or aversion patterns toward specific narratives or asset classes

Examples:

- "The user was badly hurt in bank stocks during 2008 and should not be nudged
  toward levered financial exposure."
- "A child may need education funding in five years, so a protected capital
  reserve matters."

### Short-term memory

Short-term memories capture time-sensitive context such as:

- upcoming liquidity events
- recent emotional reactions to market news
- temporary operational or travel-related constraints

Examples:

- "A recent home purchase makes current liquidity tighter than usual."
- "Recent geopolitical headlines have increased short-term demand for safety."

### Persona evidence

`persona_evidence` remains the source-of-truth transcript layer. It should keep
the raw discovery excerpts tied to the dimensions that produced them.

### Persona markdown

`persona_markdown` is the concluding human-readable profile. A draft should not
be considered fully confirmed until this artifact exists.

## Middle layer: Contextual rules

`contextual_rules` should remain as the bridge between hard numeric boundaries
and pure narrative memory.

This layer is appropriate for operational guidance such as:

- require human confirmation before execution in advisory mode
- preserve liquidity reserves before increasing risk
- treat blocked assets as non-overridable filters

## What should stay out of the structured layer

The following concepts should not be forced into shallow enums unless the team
can justify a concrete operational need:

- wealth source biographies
- market trauma stories
- stress narratives
- subjective sophistication labels
- soft preference explanations that are not directly machine-enforceable

Those belong in `persona_traits`, memory, evidence, or contextual rules.

## Derived fields

`risk_budget` and `persona_style` may still exist as derived summaries, but
they are no longer the primary truth layer.

The primary truth layer is:

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

## Discovery implications

The discovery flow should:

1. ask a starter question for each required dimension
2. keep asking follow-ups until the answer is specific enough to normalize or
   preserve as a high-signal trait
3. block draft generation if required dimensions are still vague
4. generate a final profile containing:
   - structured boundary fields
   - persona traits
   - contextual rules
   - long-term memories
   - short-term memories
   - persona evidence
   - persona markdown after confirmation

## Relationship to current code

The implementation should align with this document through:

- `src/finkernel/schemas/profile.py`
- `src/finkernel/schemas/discovery.py`
- `src/finkernel/services/question_planner.py`
- `src/finkernel/services/profile_discovery.py`
- `src/finkernel/services/profiles.py`

Use this document as the contract for future profile work.

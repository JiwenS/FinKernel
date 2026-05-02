# Profile Discovery Interpretation Contract

This document defines the packet that an agent submits after a user answers one
profile-discovery question.

For the broader architecture, see `docs/profile-discovery-architecture.md`.

## Boundary

The agent is responsible for semantic interpretation:

- what the answer means
- which dimensions are covered
- what remains unclear
- whether there are contradictions
- which evidence, traits, memories, and contextual rules should be saved

FinKernel is responsible for deterministic handling:

- validate section and dimension scope
- normalize supported structured fields
- persist the turn and accepted interpretation packet
- update the working profile snapshot
- update coverage state
- decide draft readiness from stored state

## Packet shape

The submitted JSON object uses this shape:

```json
{
  "section": "financial_objectives | risk | constraints | background",
  "question_text": "string or null",
  "answer_text": "string",
  "covered_dimensions": ["dimension_name"],
  "structured_field_updates": [
    {
      "dimension": "dimension_name",
      "value": "typed value"
    }
  ],
  "narrative_dimension_updates": [
    {
      "dimension": "financial_literacy | wealth_origin_dna | behavioral_risk_profile",
      "text": "string"
    }
  ],
  "long_term_memory_candidates": [
    {
      "summary": "string",
      "theme": "string",
      "source_dimension": "dimension_name"
    }
  ],
  "short_term_memory_candidates": [
    {
      "summary": "string",
      "theme": "string",
      "source_dimension": "dimension_name or null"
    }
  ],
  "evidence_snippets": [
    {
      "excerpt": "string",
      "dimension": "dimension_name or null",
      "rationale": "string or null"
    }
  ],
  "contextual_rule_candidates": [
    {
      "rule_text": "string",
      "reason": "string",
      "confidence": "low | medium | high"
    }
  ],
  "remaining_gaps": ["legacy generic gap string"],
  "dimension_remaining_gaps": [
    {
      "dimension": "dimension_name or null",
      "note": "string"
    }
  ],
  "conflict_notes": ["legacy generic conflict string"],
  "dimension_conflict_notes": [
    {
      "dimension": "dimension_name or null",
      "note": "string"
    }
  ],
  "confidence_label": "low | medium | high",
  "section_complete": false
}
```

The legacy `remaining_gaps` and `conflict_notes` fields remain accepted for
compatibility. New agents should prefer the dimension-level fields when the
issue belongs to a specific dimension.

## Section dimensions

### `financial_objectives`

- `target_annual_return`
- `investment_horizon`
- `annual_liquidity_need`
- `liquidity_frequency`

### `risk`

- `max_drawdown_limit`
- `max_annual_volatility`
- `max_leverage_ratio`
- `single_asset_cap`

### `constraints`

- `blocked_sectors`
- `blocked_tickers`
- `base_currency`
- `tax_residency`

### `background`

- `account_entity_type`
- `aum_allocated`
- `execution_mode`
- `financial_literacy`
- `wealth_origin_dna`
- `behavioral_risk_profile`

## Structured field values

Structured updates must use deterministic values:

| Dimension | Value shape |
| --- | --- |
| `target_annual_return` | decimal-like string, for example `"8.5"` |
| `investment_horizon` | integer years, for example `10` |
| `annual_liquidity_need` | decimal-like string, for example `"25000"` |
| `liquidity_frequency` | `monthly`, `quarterly`, `annual`, or `none` |
| `max_drawdown_limit` | decimal-like string |
| `max_annual_volatility` | decimal-like string |
| `max_leverage_ratio` | decimal-like string |
| `single_asset_cap` | decimal-like string |
| `blocked_sectors` | list of strings |
| `blocked_tickers` | list of strings |
| `base_currency` | uppercase currency string, for example `"USD"` |
| `tax_residency` | short jurisdiction string, for example `"US"` |
| `account_entity_type` | `individual`, `trust`, or `corporate` |
| `aum_allocated` | decimal-like string |
| `execution_mode` | `discretionary` or `advisory` |

Narrative dimensions must use `narrative_dimension_updates`, not
`structured_field_updates`.

## Coverage rules

- Use `covered_dimensions` only when the answer is sufficient for downstream
  profile use.
- A dimension can be covered even when the value is intentionally unknown or not
  applicable, but the evidence should make that clear.
- Set `section_complete` to `true` only when every target dimension in that
  section is covered, no material gaps remain, and no unresolved conflict blocks
  draft generation.
- If `section_complete` is `true`, both generic and dimension-level remaining
  gap fields must be empty.

## Gap and conflict rules

Use `dimension_remaining_gaps` when the next follow-up should target a specific
dimension.

Use `dimension_conflict_notes` when the new answer materially conflicts with
accepted state for a specific dimension.

Use a `null` dimension only for truly section-level issues that cannot be tied
to one dimension.

The runtime validates that dimension-scoped issues belong to the submitted
section.

## Compatibility

Current API names still include legacy persona terminology. This contract uses
profile-first product language while preserving compatible packet field names
where they already exist.

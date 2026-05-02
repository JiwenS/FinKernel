# Profile Discovery Confidence And Coverage

This document defines the first engineering contract for profile-discovery
coverage, confidence, evidence quality, and conflict state.

It is intentionally conservative. The goal is to expose clearer state for host
agents without changing the core rule that semantic judgment starts in the
agent layer and deterministic validation stays in FinKernel.

## Principles

- Coverage means a dimension is sufficiently understood for downstream profile
  use, not merely that a question was asked.
- Confidence starts as agent-produced analysis and is stored by FinKernel.
- Evidence quality measures whether accepted interpretation packets include
  usable supporting excerpts for the covered dimensions.
- Conflicts should block draft readiness until resolved.
- Host agents should use gaps, low confidence, weak evidence, and conflicts to
  choose the next follow-up question.

## Dimension state

Each dimension has deterministic runtime state:

- `coverage_score`: `0` to `3`
  - `0`: untouched
  - `1`: touched but incomplete
  - `2`: minimally covered
  - `3`: strongly covered
- `confidence_score`: `0` to `3`
  - derived from the agent's submitted `confidence_label`
- `evidence_score`: `0` to `3`
  - `0`: no accepted evidence
  - `1`: weak or generic evidence
  - `2`: usable evidence
  - `3`: strong direct evidence
- `depth_score`: `0` to `3`
  - how much the dimension has been probed
- `pending_gaps`: unresolved follow-up needs
- `conflict_flag`: whether the dimension has unresolved conflicting signals

## Section snapshot

Section coverage should expose:

- target dimensions for the current pass
- covered dimensions
- outstanding dimensions
- progress percent
- remaining gaps
- conflict notes
- confidence label
- `evidence_quality_label`
- `blocked_by_conflicts`

## Draft readiness

Draft readiness is blocked when a target dimension has:

- coverage below the minimum threshold
- pending gaps
- unresolved conflicts

Evidence quality does not yet block draft readiness in v1. Low evidence quality
should guide follow-up questions and review UI, but it should not silently
override agent-submitted coverage until the team has evaluated real discovery
data.

## Host behavior

Hosts should prefer follow-up questions in this order:

1. unresolved conflicts
2. required dimensions with pending gaps
3. covered dimensions with low confidence
4. covered dimensions with weak evidence quality
5. optional narrative depth

The host should not narrate these mechanics to the user unless the user asks to
inspect progress or evidence.

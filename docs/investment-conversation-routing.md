# Investment Conversation Routing

This document defines how an upper-layer agent should route natural-language
investment and funds-management conversations into FinKernel.

It exists because having the MCP tools available is **not** enough by itself.
The host agent must explicitly choose to enter the FinKernel flow instead of
answering as a generic finance chatbot.

## Core rule

When the user is implicitly asking FinKernel to help manage money, deploy capital,
rebalance, review risk, or assist with a portfolio decision:

1. do **not** start with generic investment advice
2. do **not** start with web search
3. first resolve onboarding and active-profile state

## Intents that should trigger FinKernel routing

Examples:

- "我想做一笔 20000 美金的投资"
- "帮我管理一下这笔钱"
- "我应该怎么配置这部分仓位"
- "review my risk"
- "should I rebalance"
- "what would you do with this portfolio"

These should be treated as **profile-aware decision-support requests**, not as
generic market Q&A.

## Required first call

For the intents above, the first MCP read should be:

- `get_profile_onboarding_status`

This determines whether the system has an active profile that can govern the
recommendation.

## If no active profile exists

If `get_profile_onboarding_status` returns `onboarding_required = true`:

1. explain that profile-scoped advice requires first capturing the user's objectives,
   risk posture, constraints, and collaboration preferences
2. if the host app already knows the stable user identity, call:
   - `start_profile_discovery`
3. if the host app does **not** provide a stable identity binding, ask for the
   minimum owner label once, then call:
   - `start_profile_discovery`
4. continue discovery with:
   - `get_next_profile_question`
   - `submit_profile_discovery_answer`
5. when ready, call:
   - `generate_profile_draft`
6. author the human/agent-readable profile artifact when needed
7. finalize with:
   - `confirm_profile_draft`

The important boundary is:

- **profile creation happens before allocation advice**

## If an active profile exists

If `get_profile_onboarding_status` shows active profiles:

1. if exactly one active profile exists, use it automatically
2. if multiple active profiles exist:
   - prefer an explicitly named profile from the user
   - otherwise ask which profile should govern the recommendation before giving
     specific allocations or trade guidance

Once the profile is resolved, read profile-aware context before recommending actions:

- `get_profile`
- `get_profile_persona_markdown`
- `get_risk_summary`
- `get_portfolio_snapshot` when current cash / holdings / exposure matter

## Preferred decision-support flow

For broad "what should I do with this money" requests:

1. `create_strategy_from_text`
2. `run_advisor_once`
3. `list_suggestions`
4. narrate the suggestion in user-facing language
5. use approval / workflow tools only if the conversation moves into execution

For what-if sizing and projected impact:

- use `simulate_trade`

## Web research boundary

External web research is allowed only **after** FinKernel context is loaded and only
when fresh market facts materially change the answer.

Examples where web research can be helpful after profile resolution:

- current Treasury yields
- current macro events
- current earnings / market-moving news

Examples where web research should **not** replace FinKernel routing:

- first-use onboarding
- resolving which profile applies
- reading stored risk posture
- reading profile-aware portfolio or risk state
- generating FinKernel-native advisor suggestions

## Where these rules should live

- `SKILL.md` is the agent-facing execution contract
- this document is the maintainer-facing explanation of the routing policy
- host-agent prompts / orchestrators should mirror the same onboarding-first behavior

## Minimal regression checklist

If this routing contract changes, verify at minimum:

1. `SKILL.md` still says to call `get_profile_onboarding_status` before specific allocation advice
2. the MCP surface still exposes:
   - `get_profile_onboarding_status`
   - `start_profile_discovery`
   - `get_risk_summary`
   - `create_strategy_from_text`
   - `run_advisor_once`
3. the onboarding path still returns:
   - `PROFILE_ONBOARDING_REQUIRED`
   - `next_step = start_profile_discovery`

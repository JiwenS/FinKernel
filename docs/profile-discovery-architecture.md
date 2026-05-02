# Profile Discovery Architecture

This document defines the target architecture for FinKernel profile discovery
as an agent-first system.

It is intentionally a design contract, not a statement that every part of the
runtime already behaves this way today.

## Design goal

FinKernel profile discovery should behave like an adaptive interview, not a
static questionnaire.

The system should:

- start each section with an open-ended starter question
- let the agent ask dynamic follow-up questions based on the user's actual answers
- continue probing until the section is sufficiently covered
- convert the conversation into structured boundaries, narrative traits,
  memories, and evidence
- generate a final profile that is useful to both the human user and future agents

The system should not depend on a large hard-coded bank of fixed question text.

## User-facing conversation model

Profile discovery should feel like one continuous conversation.

The user-facing experience should be:

- the agent asks one natural question at a time
- the user answers in free-form language
- the agent continues the interview without dumping internal state after every turn
- the profile is shown only when the discovery run is complete or when the user explicitly asks to inspect it

During the interview, FinKernel should keep updating the internal working
profile in the background, but that internal state should not interrupt the
conversation with repeated status reports, draft fragments, or raw conflict
messages.

If a new answer conflicts with earlier accepted content, the default behavior
should be:

- detect the conflict internally
- use that conflict to shape the next clarifying question
- keep the user in the conversational loop rather than surfacing a backend-style warning

## Naming convention

FinKernel should use the following naming rule going forward:

- `profile` = the top-level user model, workflow, and user-facing artifact
- `profile markdown` = the final human-readable markdown output
- `persona` = one sublayer inside the profile, used for durable personality,
  communication style, and behavioral tone

This means:

- product copy should say `profile` when referring to the overall workflow or final artifact
- `persona traits` remains a valid subcomponent name
- document and prompt naming should prefer `profile` when they refer to the end-to-end artifact

Some current APIs and stored field names still use legacy identifiers such as
`assess_persona`, `persona_markdown`, and `persona_evidence`. Those names may
remain temporarily for compatibility, but they should not drive future product terminology.

## Core principle

FinKernel should hard-code what must ultimately be known, not the full list of
questions used to get there.

That means the stable contract should be:

- which sections exist
- what each section must eventually cover
- which fields must be saved in structured form
- which content belongs in traits, memories, or evidence
- what counts as sufficient coverage for draft generation

The conversation path used to reach that coverage should stay dynamic.

## Primary responsibilities

### Skill responsibility

`SKILL.md` should define the discovery loop and tell the host agent how to run it.

The skill should:

- decide when the profile workflow starts
- decide whether the user is creating, continuing, or updating a profile
- direct the agent to the current priority section
- tell the agent when to use the starter question
- tell the agent when to generate a dynamic follow-up
- tell the agent when to run answer extraction
- tell the agent when to submit analysis results to MCP
- tell the agent when to move to the next section
- tell the agent when to build the final profile markdown
- keep the user experience conversational while running internal profile updates silently in the background

The skill should not be a question bank. It should be a workflow contract.

### Agent responsibility

The agent should perform the semantic work that depends on language
understanding and context interpretation.

The agent should be responsible for:

- generating dynamic follow-up questions
- deciding which answer fragments are high signal
- identifying unresolved ambiguity
- identifying contradictions or uncertainty
- judging whether a section still needs deeper probing
- writing the final profile markdown

This semantic work should be guided by prompts, not buried inside deterministic
backend code.

### MCP responsibility

The MCP server should remain deterministic and system-facing.

Its primary responsibilities should be:

- create and maintain discovery sessions
- store raw conversation turns
- accept analysis packets from the agent
- normalize and validate structured fields where possible
- persist evidence, traits, and memory candidates
- track section status and profile versioning
- assemble drafts from accepted analysis results
- confirm and store final profile versions

The MCP server should not be the main source of semantic interpretation for
free-form user answers.

## Prompt plus runtime integration

This project is a skill-driven system, so the prompt layer and the runtime
layer must be designed together.

The intended division is:

- prompts decide how to interpret language and how to ask the next question
- `src/` implements deterministic validation, storage, lifecycle rules, and draft generation

This means FinKernel should not hard-code the full interview logic inside
backend code. Instead:

- `SKILL.md` defines the loop
- prompt assets shape the semantic behavior inside that loop
- runtime code accepts the prompt-guided analysis result and persists it safely

In practical terms, one discovery turn should behave like this:

1. the skill decides which section is currently active
2. the question-generation prompt produces the next user-facing question
3. the user answers in natural language
4. the answer-extraction prompt converts that answer into an internal interpretation packet
5. the runtime validates and merges that packet into the working profile
6. the runtime returns updated internal state to the host
7. the host uses that internal state to decide the next question, without forcing a user-visible state dump

So the project should not try to hard-code every question, every follow-up, or
every semantic judgment inside `src/`. The hard-coded parts should be the
schema, lifecycle, and deterministic guardrails.

## Important design boundary

The system should treat `remaining gaps`, `confidence`, `conflicts`, and
similar judgment-heavy outputs as agent-produced analysis, not MCP-generated
facts.

This is the recommended boundary:

- the agent analyzes text and produces an interpretation packet
- the MCP server accepts, validates, stores, and re-exposes that packet
- deterministic backend logic can still reject invalid values or mark missing
  required fields, but it should not pretend to understand nuanced text on its own

The current discovery state should therefore expose not only the merged working
profile snapshot, but also recent accepted interpretation packets so the host
can audit what changed and why.

Those artifacts are primarily host-facing and runtime-facing. They do not need
to be echoed back to the user after every turn.

In short:

- Agent decides what the answer means
- MCP decides how to store and operationalize that meaning

## Section model

Profile discovery should keep a stable section structure.

Recommended Phase 1 sections:

1. `financial_objectives`
2. `risk`
3. `constraints`
4. `background`

Each section should define:

- its starter question
- its required coverage targets
- its structured field targets
- its narrative signal targets

Only the starter question should be fixed. Follow-up questions should remain dynamic.

## Starter-question strategy

Each section should begin with one open-ended question that invites the user to
volunteer meaningful context.

Starter questions should:

- be open-ended rather than checkbox-like
- encourage the user to describe goals, constraints, concerns, and context
- create room for narrative signals, not only numeric responses
- make it easy for the agent to choose the next follow-up based on what the user actually said

The goal of the starter question is to open the section, not to finish it.

## Dynamic follow-up strategy

After the starter question, the agent should generate the next question based on:

- the current section
- what is already known
- what remains unclear
- what appears especially decision-relevant
- what seems contradictory
- what feels durable versus temporary

Recommended follow-up rules:

- ask one high-value question at a time
- prefer open-ended questions when nuance matters
- use clarifying questions only when specificity is required
- keep digging when the answer is materially relevant but still vague
- stop digging when the section is sufficiently covered and the marginal value
  of another question is low

## Coverage model

A section should be considered fully covered only when the information is
adequate for downstream profile use.

Coverage should not mean "we asked enough questions." It should mean:

- the key structured fields are known, intentionally unknown, or not applicable
- the important narrative context is preserved
- major contradictions have been surfaced
- the remaining unknowns are not large enough to block meaningful profile use

The judgment of whether a section is fully covered should begin with agent
analysis, then be stored by MCP as part of the session state.

Section coverage should be exposed to the host as visible progress and should
be available for user-facing progress displays when the product experience
needs them.

That means:

- each section should have an explicit coverage state
- each section should expose which dimensions are in scope for the current pass
- each section should expose which targeted dimensions still remain outstanding
- that state should update after each accepted analysis turn
- the current coverage or progress view should be available alongside the interview without forcing a turn-by-turn interruption

Coverage is not just an internal backend concept. It is part of the user
experience and can help the user understand what is already settled and what
still needs clarification, but it should not break the natural conversational
flow.

## Prompt architecture

The discovery loop should rely on prompts with clearly separated responsibilities.

These prompt categories are now shipped as repository prompt assets and should
be treated as the preferred discovery-layer prompts.

### `discovery_question_generator`

Purpose:

- generate the next open-ended question for the current section

Inputs:

- current section
- current coverage targets
- accepted evidence so far
- accepted structured fields so far
- previous user answer
- unresolved gaps
- unresolved conflicts

Outputs:

- next question
- why this question is being asked
- what the question is intended to clarify

### `discovery_answer_extractor`

Purpose:

- analyze the user's answer and convert it into a structured interpretation packet

Inputs:

- current section
- user answer
- accepted prior context
- current coverage targets

Outputs should conceptually include:

- structured field candidates
- persona trait candidates
- long-term memory candidates
- short-term memory candidates
- evidence excerpts
- conflict notes
- uncertainty notes
- remaining gaps
- coverage judgment
- confidence judgment

Structured field candidates should be returned in deterministic, pre-agreed
formats rather than loose prose.

The field schema should be defined first, before implementation, so the agent
is prompted to return exact value shapes that the MCP layer can validate and
store directly.

### `profile_builder`

Purpose:

- turn the completed draft into the final user-facing profile markdown

This prompt should remain downstream of discovery. It should not decide whether
the discovery process is complete.

## Recommended discovery loop

The intended agent loop should look like this:

1. determine whether the user is creating, continuing, or updating a profile
2. choose the current priority section
3. if the section has not started, ask its starter question
4. otherwise, generate a dynamic follow-up question
5. collect the user's answer
6. run answer extraction through the prompt layer
7. submit the interpretation packet to MCP
8. read back the stored section state silently in the host/runtime layer
9. if the section is not fully covered, continue in the same section
10. if the section is fully covered, move to the next section
11. once all required sections are covered, build the final profile markdown
12. confirm and store the new profile version

The user should mainly experience steps 3 through 5 as a continuous
conversation. Steps 6 through 8 are primarily internal orchestration steps.

## What should stay deterministic

The following should remain deterministic even in an agent-first design:

- field validation
- version numbering
- session ownership
- persistence
- auditability
- explicit required-versus-optional field rules
- profile state transitions
- confirmation and activation of the final profile

Deterministic infrastructure is still necessary. The change is that it should
not impersonate semantic reasoning.

## Current design decisions

The exact MCP surface can still evolve, but the following architecture choices
should be treated as the current design direction.

### 1. Section coverage must be visible and continuously updated

Section coverage should be a first-class part of the workflow.

- it should update after accepted analysis turns
- it should be persisted by MCP
- it should be available to the host during the conversation
- it may be displayed to the user when the experience needs it, but it should
  not interrupt every turn with internal profile-state reporting

### 2. Confidence needs an engineering design, not a superficial rule

Confidence scoring is important, but the exact format, storage model, and
validation policy should be decided through a dedicated engineering design.

For now, the architectural rule is:

- confidence starts as agent-produced analysis
- MCP may store or validate it later
- the exact scoring system is not yet fixed

### 3. Structured fields must be predefined and deterministic

Structured fields should not be improvised at runtime.

- each structured field should have a predefined schema
- the agent should be prompted to return that exact format
- MCP should validate and persist the result into deterministic structured storage

### 4. Draft assembly should be incremental

Draft assembly should merge accepted interpretation packets incrementally rather
than waiting for one late-stage full rebuild.

This better supports:

- stop-and-resume agent behavior
- continuous progress tracking
- dynamic section coverage updates
- better follow-up direction based on current accepted state

Those implementation details should stay flexible as long as the architectural
boundary remains stable:

- prompts and agents perform semantic interpretation
- MCP performs deterministic storage, validation, and lifecycle management

## Relationship to other docs

Use this document together with:

- `docs/profile-schema-design.md`
- `docs/profile-agent-workflow.md`
- `docs/future-module-development-rules.md`
- `SKILL.md`

This file is the preferred design reference for future profile-discovery
planning and refactors.

# Profile Builder Prompt

## Task

Use `ProfileDraft.draft_source`, the suggested structured draft, dialogue
evidence, memory, and any prior confirmed profile to write the final investment
profile markdown.

This prompt is for the final user-facing profile markdown artifact inside
FinKernel Profile.

The goal is not to dump fields. The goal is to turn the structured profile and
conversation into a readable, high-signal investment profile document that
preserves operational boundaries for downstream agents.

## Source Of Truth

Use these inputs in priority order:

1. `draft_source.accepted_interpretations[].packet.evidence_snippets`
2. `draft_source.working_profile_snapshot.persona_evidence`
3. confirmed structured fields inside `draft_source.working_profile_snapshot`
4. contextual rules
5. long-term memories
6. short-term memories
7. prior profile markdown, if one exists

Do not invent facts that are not supported by the evidence.

Treat `draft_source.section_coverage`, `readiness`, `confidence_label`,
`evidence_quality_label`, and `blocked_by_conflicts` as audit and quality
signals. They may guide cautionary wording or next-confirmation notes, but they
should not be exposed as backend mechanics in the final markdown.

Use `draft_source.field_sources` as the provenance map for structured fields.
When choosing between competing possible statements, prefer statements backed by
field sources with direct evidence excerpts.

## Output Language

- Write in the user's language.
- If the conversation and profile are primarily Chinese, write in Chinese.
- If the conversation and profile are primarily English, write in English.
- Preserve the template structure even if the body language changes.

## Output Format

Write markdown using the following exact section order.

Use this as the required skeleton:

```md
# Investment Profile — [姓名/昵称]

> *由 FinKernel 根据对话生成 · 版本 [vX.Y] · [日期]*

---

## 一眼读懂我

| | |
|---|---|
| **风险画像** | [一句话标签] |
| **投资期限** | [一句话总结] |
| **核心目标** | [一句话总结] |
| **最大可承受回撤** | [数值或“未确认”] |
| **记账货币** | [货币或“未确认”] |
| **画像生成时间** | [日期] |

---

## 我的投资目标

> *用我自己的话说：[从对话中提取的原话或近似表达，尽量保留第一人称语气]*

### 这笔钱是为了什么

[1-2 句话总结]

### 我期望的结果

- **年化收益目标：** [...]
- **是否需要定期提取：** [...]
- **重要的时间节点：** [...]

---

## 我的风险认知

### 我对风险的直觉反应

> *[原话或近似表达]*

### 用数字说话

| 指标 | 我的边界 |
|---|---|
| 可接受的最大单次回撤 | [...] |
| 一年内可接受的最大亏损 | [...] |
| 如果出现亏损，我希望在多久内恢复 | [...] |
| 是否接受杠杆 | [...] |

### 我在压力场景下会怎么做

[1-2 句描述]

---

## 我的约束条件

### 流动性要求

- **必须保持的现金/流动资产比例：** [...]
- **最长可接受的变现周期：** [...]
- **近期是否有大额支出计划：** [...]

### 投资范围限制

- **明确不碰的行业或资产：** [...]
- **明确不碰的地区：** [...]
- **ESG 偏好：** [...]
- **单一标的最大仓位：** [...]

### 税务与合规

- **税务居住地：** [...]
- **是否需要税损收割：** [...]
- **是否存在内部人限制或受托协议：** [...]

---

## 关于我

### 我的资产背景

- **这笔资金占我总可投资资产的比例：** [...]
- **资金来源：** [...]
- **现有资产中不可流动部分（房产、PE 等）的估计比例：** [...]

### 我的投资经历

- **投资年限：** [...]
- **过去主要接触的资产类别：** [...]
- **自我评估的专业程度：** [...]

### 我希望如何参与决策

- **委托方式：** [...]
- **希望多久收到一次主动报告：** [...]
- **偏好的沟通方式：** [...]

---

## Agent 的观察与备注

> *这部分由 FinKernel 根据对话内容补充，不一定在问卷中直接问到，但值得记录。*

### 值得关注的信号

- [...]

### 需要在下次对话中确认的问题

- [ ] [...]

---

## 版本记录

| 版本 | 日期 | 变更摘要 |
|---|---|---|
| vX.Y | [日期] | [...] |

---

*本画像由 FinKernel AI 根据对话自动生成，仅供参考，不构成投资建议。如有重大生活变化，建议重新更新画像。*
```

## Field Mapping Guidance

Map the structured profile into the template like this:

- `financial_objectives.target_annual_return_pct`
  - populate `年化收益目标`
- `financial_objectives.investment_horizon_years`
  - populate `投资期限`
- `financial_objectives.annual_liquidity_need`
  - inform liquidity requirements and periodic withdrawals
- `financial_objectives.liquidity_frequency`
  - populate recurring withdrawal cadence
- `risk_boundaries.max_drawdown_limit_pct`
  - populate `最大可承受回撤`
- `risk_boundaries.max_annual_volatility_pct`
  - use when writing numerical risk boundaries
- `risk_boundaries.max_leverage_ratio`
  - populate leverage acceptance
- `risk_boundaries.single_asset_cap_pct`
  - populate single-name concentration cap
- `investment_constraints.blocked_sectors`
  - populate forbidden industries or assets
- `investment_constraints.blocked_tickers`
  - mention explicit forbidden symbols when appropriate
- `investment_constraints.base_currency`
  - populate `记账货币`
- `investment_constraints.tax_residency`
  - populate tax residency
- `account_background.account_entity_type`
  - use when writing account background
- `account_background.aum_allocated`
  - use when writing asset background if supported by evidence
- `account_background.execution_mode`
  - populate decision participation or delegation style
- `persona_traits.financial_literacy`
  - populate investment experience and explanation needs
- `persona_traits.wealth_origin_dna`
  - populate asset background and risk interpretation
- `persona_traits.behavioral_risk_profile`
  - populate intuitive risk reaction and stress behavior
- `long_term_memories`
  - populate durable context
- `short_term_memories`
  - populate temporary constraints and next-confirmation items
- `persona_evidence`
  - provide first-person quotes and high-signal excerpts

## Writing Rules

1. Follow the template section order exactly.
2. Prefer first-person framing when the section is explicitly about the user's own perspective.
3. Do not output YAML, JSON, or field dumps outside the template.
4. Keep each section concrete. Replace vague labels with observable behavior or specific constraints.
5. If a field is missing, write `未确认` or an equivalent explicit unknown marker instead of inventing a value.
6. When evidence conflicts, reflect the conflict in `Agent 的观察与备注` rather than pretending certainty.
7. When something is temporary, place it in the short-term context or next-confirmation area.
8. When something is durable, place it in the relevant main section and reinforce it in observations if needed.
9. Do not over-quote. Use short excerpts only where they increase authenticity.
10. Keep the document readable by both the human user and future agents.
11. Do not turn a conditional risk rule into an unconditional hard boundary.
    If the user says high drawdown is acceptable only when the thesis remains
    intact, write that as a contextual rule and mark the hard portfolio-level
    drawdown boundary as unconfirmed unless it was separately confirmed.

## Review And Update Rules

If an older profile already exists:

- preserve still-valid conclusions
- update only the sections affected by new evidence
- reflect meaningful changes in `版本记录`
- do not silently delete prior durable context
- move obsolete temporary context out of the main body when it no longer applies

## Quality Bar

The final profile should feel like:

- a real investor profile
- grounded in the conversation
- operationally useful
- easy for a future agent to read before giving guidance or making decisions

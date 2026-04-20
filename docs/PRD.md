# Trading Agent Infrastructure — 项目需求与架构文档

> 模拟盘 · 仅供学习研究使用 · 不涉及真实资金

---

## 1. 项目概述

本项目旨在搭建一套完整的 AI 交易 Agent 基础设施，让用户可以通过自然语言指令，委托 Agent 在**模拟盘**中管理虚拟股票账户。

Agent 可以根据用户设定的风险偏好，自主收集市场信息、推荐投资组合、择机执行订单，并持续管理仓位——整个过程支持对接多个 paper trading API，不涉及任何真实资金。

### 核心价值

- 用户用自然语言表达投资意图，无需懂交易技术细节
- Agent 持续运行，不错过市场机会，代替人工盯盘
- 所有操作留有完整 audit trail，用户随时可查、可干预
- 基础设施层与投资逻辑层解耦，用户可以接入自己的策略

---

## 2. 典型使用场景

用户对 Agent 说：

> "我有 20k 的模拟资金，希望你帮我做稳健性投资"

Agent 的完整响应流程：

1. 查询账户：确认总资产 50k，可用资金 20k
2. 收集数据：拉取当前股价、债券收益率、黄金价格、近期财经新闻、技术指标等
3. 推荐组合：基于"稳健"风险偏好，建议 40% 股票 + 40% 债券 + 20% 黄金，附理由
4. 等待确认：将建议呈现给用户，等待明确授权
5. 执行建仓：用户确认后，分批下达限价单完成建仓
6. 持续管理：此后每隔设定时间自动检查仓位，必要时 rebalance 或止损

---

## 3. 系统分层架构

```
┌─────────────────────────────────────────────────────┐
│                  Scheduler Layer                     │
│         Cron / Event trigger / Webhook / 手动触发    │
└────────────────────┬────────────────────────────────┘
                     │ 唤醒 Agent
┌────────────────────▼────────────────────────────────┐
│                 Agent Loop Core                      │
│   读状态 → 调工具 → 推理决策 → 写状态 → 睡眠        │
│   (stateless LLM call, 每次从 state store 读上下文)  │
└──────┬─────────────┬──────────────┬─────────────────┘
       │             │              │
       ▼             ▼              ▼
  只读工具       推荐工具        写操作工具
  (自动执行)    (自动执行)      (需用户确认)
┌────────────────────────────────────────────────────┐
│                  Persistent State Store             │
│         策略配置 · 持仓状态 · 待审批队列 · Audit log │
└────────────────────┬───────────────────────────────┘
                     │
┌────────────────────▼───────────────────────────────┐
│             Async Human-in-the-loop                 │
│         Push 通知 → 用户审批 UI → 确认/拒绝/修改    │
└────────────────────┬───────────────────────────────┘
                     │ 用户确认
┌────────────────────▼───────────────────────────────┐
│                 Execution Layer                     │
│      风控前置检查 → Order Manager → Broker API      │
│              (Alpaca Paper Trading)                 │
└─────────────────────────────────────────────────────┘
```

---

## 4. MCP 工具集设计

Agent 通过 MCP Server 调用以下工具。工具分三类：**只读**（自动执行）、**推荐**（自动执行，结果需用户确认）、**写操作**（用户确认后执行）。

### 4.1 账户工具（只读）

| 工具 | 入参 | 返回 | 说明 |
|---|---|---|---|
| `get_account_info()` | user_id | 余额、持仓、可用资金、总资产 | 每次 loop 开始时调用 |
| `get_positions()` | user_id | 持仓列表、当前市值、盈亏 | 用于 rebalance 判断 |
| `get_order_history()` | user_id, limit | 历史订单列表 | 用于 audit |

### 4.2 市场数据工具（只读）

| 工具 | 入参 | 返回 | 说明 |
|---|---|---|---|
| `get_price()` | symbols[] | 实时价格、涨跌幅 | 基础行情 |
| `get_technical_indicators()` | symbol, indicators[] | RSI、MACD、布林带等 | 择时依据 |
| `get_news()` | symbols[], limit | 相关财经新闻摘要 | 情绪判断 |
| `get_market_overview()` | — | 大盘指数、VIX、宏观指标 | 市场环境判断 |

### 4.3 推荐工具（结果需用户确认）

| 工具 | 入参 | 返回 | 说明 |
|---|---|---|---|
| `suggest_portfolio()` | risk_profile, budget, current_positions | 推荐配置比例、品种、理由 | 核心推荐工具 |
| `suggest_rebalance()` | target_allocation, current_positions | 需要执行的调仓操作列表 | 定期再平衡 |
| `suggest_exit()` | position, reason | 是否建议减仓/平仓，理由 | 风险管理 |

### 4.4 执行工具（需用户确认后才调用）

| 工具 | 入参 | 返回 | 说明 |
|---|---|---|---|
| `place_order()` | symbol, side, qty, order_type, order_params | order_id, 状态 | 下单（含止损止盈参数） |
| `cancel_order()` | order_id | 状态 | 撤单 |

`order_type` 支持以下类型，由 Agent 根据策略性质自主选择：

| 订单类型 | 参数 | Agent 使用场景 |
|---|---|---|
| `market` | — | 快速成交，不在乎滑点 |
| `limit` | limit_price | 指定价格，控制成本 |
| `stop` | stop_price | 触发价格后市价卖出 |
| `stop_limit` | stop_price, limit_price | 触发后限价卖出，控制执行价 |
| `bracket` | limit_price, take_profit, stop_loss | 一次性设定入场 + 止盈 + 止损 |
| `trailing_stop` | trail_percent / trail_price | 动态跟踪止损，保留上涨收益 |

**Agent 的决策逻辑（由 system prompt 引导）：**

- 短线交易（持有预期 < 数周）→ 优先使用 `bracket` 或 `trailing_stop`，建仓同时锁定风险边界
- 长期持有（buy and hold，持有预期 > 数月）→ 使用 `limit` 或 `market`，不附加止损，依靠 rebalance 管理仓位
- Agent 在生成建议时，需在 reasoning 中说明参考的信息源以及为何选择该订单类型

---

## 5. 调度层设计

Agent 不依赖用户主动发消息，由调度系统定时唤醒。

### 触发类型

| 类型 | 触发条件 | 适用场景 |
|---|---|---|
| Cron 定时 | 每 15 分钟 / 每小时 / 盘前盘后 | 常规仓位监控 |
| 价格事件 | 某标的涨跌超过阈值 | 止损、加仓 |
| 新闻事件 | 重大财经新闻出现 | 市场突发情况响应 |
| Webhook | Broker 回调（成交、拒单） | 订单状态同步 |
| 手动触发 | 用户主动发消息 | 随时查询、修改策略 |

### 推荐技术实现

- **Node.js**：BullMQ + Redis（支持延迟任务、优先级队列）
- **Python**：Celery + Redis / APScheduler

---

## 6. 状态管理设计

Agent 本身是无状态的（每次 LLM call 独立），所有"记忆"持久化在数据库中。

### 核心数据结构

```json
{
  "user_id": "u_123",
  "strategies": [
    {
      "id": "s_001",
      "name": "稳健组合",
      "risk_profile": "conservative",
      "budget": 20000,
      "target_allocation": {
        "SPY": 0.40,
        "BND": 0.40,
        "GLD": 0.20
      },
      "approved_at": "2025-01-01T10:00:00Z",
      "active": true
    }
  ],
  "positions": [
    {
      "symbol": "SPY",
      "qty": 35.2,
      "avg_cost": 455.00,
      "current_value": 16320.00
    }
  ],
  "pending_approvals": [
    {
      "id": "ap_007",
      "type": "rebalance",
      "suggestion": "建议减持 SPY 5%，增持 GLD 5%，原因：...",
      "actions": [
        { "symbol": "SPY", "side": "sell", "qty": 5 },
        { "symbol": "GLD", "side": "buy", "qty": 3 }
      ],
      "created_at": "2025-01-10T09:30:00Z",
      "expires_at": "2025-01-10T21:00:00Z",
      "status": "pending"
    }
  ],
  "audit_log": [
    {
      "timestamp": "2025-01-10T09:30:00Z",
      "event": "suggestion_created",
      "actor": "agent",
      "detail": "基于 RSI 超买信号，建议减持 SPY"
    }
  ]
}
```

### 存储方案

| 层 | 技术 | 用途 |
|---|---|---|
| 热数据 | Redis | 当前持仓、活跃策略、loop 状态（低延迟读写）|
| 冷数据 | PostgreSQL | Audit log、历史订单、完整用户记录（持久化）|

---

## 7. Human-in-the-loop 设计

Agent 采用**异步非阻塞**的审批模式：Agent 不等待用户回复，将建议写入 pending 队列后立即结束本次 loop。

### 审批流程

```
Agent 生成建议
    → 写入 pending_approvals（status: pending）
    → 推送通知给用户（Push / Email / SMS）
    → 本次 loop 结束，Agent 睡眠

用户收到通知
    → 打开审批 UI
    → 查看建议详情 + 理由 + 风险提示
    → 选择：确认 / 拒绝 / 修改参数

下次 Agent loop
    → 检测到 approved → 调用执行工具下单
    → 检测到 rejected → 记录原因，重新评估
    → 检测到 expired  → 标记过期，重新判断是否仍有价值
```

### 审批 UI 最小信息集

- 建议操作（买/卖什么，多少）
- Agent 的推理依据（数据 + 逻辑）
- 当前账户状态（执行后持仓变化预览）
- 风险提示（波动率、集中度等）
- 操作按钮：确认 / 拒绝 / 修改

---

## 8. 风控护栏（硬约束）

以下规则在执行层强制执行，Agent 无法绕过：

| 规则 | 默认值 | 说明 |
|---|---|---|
| 单笔最大金额 | 总资产的 20% | 防止单笔过大 |
| 单标的最大仓位 | 总资产的 50% | 防止过度集中 |
| 日内最大交易次数 | 10 次 | 防止频繁交易 |
| 最大回撤保护 | 账户总亏损 > 20% | 暂停所有操作，通知用户 |

> 止损不再作为独立的平台逻辑存在，而是通过订单类型（`bracket`、`stop_limit`、`trailing_stop`）在下单时由 Agent 决策是否附加。平台风控层只保留账户级别的熔断保护。

---

## 9. Broker 适配层设计

本项目不绑定任何特定 Broker，采用**统一 Broker 接口 + 适配器模式**，用户可以接入任意 Broker 或自定义实现。

### 统一接口定义

所有 Broker 适配器必须实现以下标准接口：

```typescript
interface BrokerAdapter {
  // 账户
  getAccount(): Promise<AccountInfo>
  getPositions(): Promise<Position[]>
  getOrderHistory(limit: number): Promise<Order[]>

  // 下单
  placeOrder(order: OrderRequest): Promise<OrderResult>
  cancelOrder(orderId: string): Promise<void>

  // 行情（可选，部分 Broker 自带）
  getQuote?(symbols: string[]): Promise<Quote[]>
}

interface OrderRequest {
  symbol: string
  side: 'buy' | 'sell'
  qty: number
  order_type: 'market' | 'limit' | 'stop' | 'stop_limit' | 'bracket' | 'trailing_stop'
  limit_price?: number
  stop_price?: number
  take_profit?: number
  stop_loss?: number
  trail_percent?: number
}
```

### 内置适配器

| 适配器 | 说明 | 适用场景 |
|---|---|---|
| `AlpacaAdapter` | 对接 Alpaca Paper Trading | 默认推荐，免费，接口完整 |

### 用户自定义 Broker

用户只需实现 `BrokerAdapter` 接口并注册，即可接入任意平台（Interactive Brokers、TD Ameritrade、国内券商 API 等）：

```typescript
// 用户自定义示例
class MyBrokerAdapter implements BrokerAdapter {
  async getAccount() { /* 调用自己的 API */ }
  async placeOrder(order) { /* 调用自己的 API */ }
  // ...
}

// 注册
registry.register('my-broker', new MyBrokerAdapter())
```

### Alpaca Paper Trading 快速开始

对于使用默认适配器的用户：

```
Paper Trading Base URL: https://paper-api.alpaca.markets
所需 API 功能：Account / Orders / Market Data / WebSocket Streaming
申请地址：https://alpaca.markets（免费注册，无需真实资金）
```

---

## 10. 技术栈选型建议

| 层级 | 推荐方案 | 备选 |
|---|---|---|
| Agent 推理 | Claude API (claude-sonnet-4-5) | GPT-4o |
| MCP Server | Node.js + @modelcontextprotocol/sdk | Python MCP SDK |
| 调度 | BullMQ + Redis | Celery / APScheduler |
| 状态存储 | PostgreSQL + Redis | Supabase（托管）|
| Broker 适配层 | 自定义 BrokerAdapter 接口 | 内置 Alpaca / Mock 适配器 |
| 市场数据 | Alpaca Data API + Yahoo Finance | Polygon.io |
| 通知推送 | 前期：WebSocket 实时推送到 Web UI | 后期可加 Email |
| 后端框架 | Node.js (Express / Fastify) | Python (FastAPI) |

---

## 11. 项目分阶段实施计划

### Phase 1 — 工具层验证（2 周）
- [ ] 搭建 MCP Server 骨架
- [ ] 实现账户工具（对接 Alpaca paper trading）
- [ ] 实现市场数据工具（行情 + 技术指标）
- [ ] 在 Claude Desktop 中手动测试工具调用

### Phase 2 — Agent 推理层（2 周）
- [ ] 实现 `suggest_portfolio()` 工具
- [ ] 设计 Agent system prompt（角色、约束、输出格式）
- [ ] 实现完整的单次 loop（从收集数据到生成建议）
- [ ] 实现执行工具（place_order、set_stop_loss）

### Phase 3 — 基础设施层（3 周）
- [ ] 搭建状态数据库（PostgreSQL + Redis）
- [ ] 实现调度系统（定时触发 + 事件触发）
- [ ] 实现 pending_approvals 队列
- [ ] 实现 audit log 写入

### Phase 4 — 交互层（2 周）
- [ ] 搭建最小审批 UI（Web）
- [ ] 实现 WebSocket 实时通知
- [ ] 实现用户策略配置界面
- [ ] 端到端联调测试

---

## 12. 项目说明

- 本项目为开源学习项目，仅对接模拟盘（Alpaca Paper Trading），不涉及任何真实资金
- 不构成投资建议，所有模拟交易结果仅供技术研究参考
- 如需对接真实账户，需自行评估当地法律法规要求
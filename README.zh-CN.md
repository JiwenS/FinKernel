# FinKernel

[![Docs: English](https://img.shields.io/badge/Docs-English-2563EB?style=flat-square)](README.md)
[![Docs: Simplified Chinese](https://img.shields.io/badge/Docs-%E7%AE%80%E4%BD%93%E4%B8%AD%E6%96%87-E67E22?style=flat-square)](README.zh-CN.md)

![Python 3.12](https://img.shields.io/badge/Python-3.12-3776AB?style=flat-square&logo=python&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-Profile_API-009688?style=flat-square&logo=fastapi&logoColor=white)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL-pgsql-4169E1?style=flat-square&logo=postgresql&logoColor=white)
![pgvector](https://img.shields.io/badge/pgvector-enabled-0F766E?style=flat-square)
![MCP](https://img.shields.io/badge/MCP-host_agent_ready-111827?style=flat-square)
![Focus](https://img.shields.io/badge/Focus-persona_%26_risk_profile-7C3AED?style=flat-square)

FinKernel 是一个基于 Python / FastAPI 的服务，当前只专注做一件事：构建并维护**个人风险画像**，让下游 agent 和应用在给出投资相关建议前，能够先获得可信的 persona 上下文。

当前产品面刻意保持收敛：

- profile onboarding
- guided risk-profile discovery
- profile review and versioning
- persona markdown authoring
- long-term and short-term memory capture
- MCP + HTTP access for host agents

当前阶段之外的能力，都已经从主路径中移除。

## 当前阶段

Phase 1 的目标是先把个人风险画像基础打稳。

在这个阶段里，FinKernel 只负责 onboarding、discovery、review/versioning、
persona artifacts，以及为 profile-aware investment guidance 提供所需的
profile memory。更广义的投资规划、推荐生成、市场研究编排和执行流程，
都不在当前范围内。

## 建议先读

- 语言切换：
  - English: `README.md`
  - 简体中文：`README.zh-CN.md`
- 文档入口：
  - English: `docs/README.en.md`
  - 简体中文：`docs/README.zh-CN.md`
- `docs/README.md`
- `docs/setup-and-run.md`
- `docs/persona-profiles.md`
- `docs/persona-agent-workflow.md`
- `docs/investment-conversation-routing.md`
- `docs/upper-layer-agent-integration.md`
- `docs/host-agent-runtime-integration.md`
- `docs/troubleshooting.md`
- `prompts/finkernel_system_routing.md`
- `SKILL.md`

## 核心接口

HTTP：

- `GET /api/health`
- `GET /api/profiles/onboarding-status`
- `POST /api/profiles/assess-persona`
- `GET /api/profiles/{profile_id}`
- `GET /api/profiles/{profile_id}/risk-summary`
- `GET /api/profiles/{profile_id}/persona.md`
- `GET /api/profiles/{profile_id}/persona-sources`
- `PUT /api/profiles/{profile_id}/persona`
- `GET /api/profiles/{profile_id}/versions`
- `POST /api/profiles/discovery/sessions`
- `GET /api/profiles/discovery/sessions/{session_id}/next-question`
- `POST /api/profiles/discovery/sessions/{session_id}/answers`
- `POST /api/profiles/discovery/sessions/{session_id}/draft`
- `POST /api/profiles/discovery/drafts/{draft_id}/confirm`
- `POST /api/profiles/{profile_id}/review`
- `POST /api/profiles/{profile_id}/memories`
- `GET /api/profiles/{profile_id}/memories/search`
- `POST /api/profiles/{profile_id}/memories/distill`

MCP：

- `http://localhost:8000/api/mcp/`

## 快速开始

1. 初始化本地环境：
   - `powershell -ExecutionPolicy Bypass -File .\scripts\bootstrap-local.ps1`
2. 启动服务：
   - `powershell -ExecutionPolicy Bypass -File .\scripts\run-local.ps1`
3. 检查健康状态：
   - `http://localhost:8000/api/health`
4. 如果跳过了自动 agent 注册，就手动注册 `config/host-agent-mcp-http.local.json` 或 `config/host-agent-mcp-stdio.local.json`，并注入 `prompts/finkernel_system_routing.md`
5. 开始 persona discovery，或直接使用单入口编排：
   - `POST /api/profiles/assess-persona`
   - `POST /api/profiles/discovery/sessions`

## 配置

- `config/persona-profiles.json` 用于存储 seed risk profiles
- `config/persona-profiles.example.json` 是模板
- `config/host-agent-mcp-http.example.json` 和 `config/host-agent-mcp-stdio.example.json` 展示了如何把 FinKernel 注册成 MCP server
- `scripts/bootstrap-local.ps1` 会创建 `.venv`、安装依赖、逐步引导 `.env` 配置、初始化 PostgreSQL + `vector`、写入本地 HTTP/stdio MCP config，并为 Codex/OpenClaw/custom client 生成 agent bundle
- `scripts/run-local.ps1` 会在 `http://localhost:8000` 启动本地 FastAPI 服务

## 文档契约

只有当实现、prompt 和文档都在描述同一个产品时，FinKernel 才算完成。

至少需要保证下面这些面始终一致：

- API behavior
- MCP tool behavior
- routing prompt
- onboarding and review workflow docs
- seeded profile examples

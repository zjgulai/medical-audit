---
title: AI 审计一体化协作平台仓库说明
doc_type: knowledge
module: repository
topic: project-overview
status: stable
created: 2026-05-31
updated: 2026-08-13
owner: self
source: human+ai
---

# AI 审计一体化协作平台

## 当前定位

本仓库是面向医院场景的私有化医疗审计产品，不是通用 SaaS 或纯研究仓库。核心目标是在可信身份和数据治理边界内完成「知识依据 → 合规判断与疑点 → 底稿与报告 → 整改跟踪」。

核心闭环为：

`法规与知识支撑 -> 合规判断与风险识别 -> 审计底稿与报告 -> 整改跟踪`

## 当前候选状态

- 本地基线：`main == origin/main == ccc73e95820e39559430e96c01d52c8dfb77a246`；候选分支为 `codex/medical-audit-reanalysis-playbook-20260813`。
- 生产历史证据：2026 年 8 月 12 日 L3 只读观测为 `25e1654e0c44ca5cbb2bb42e82debdb40fa6f224`。
- 本地验收：临时 SQLite、确定性 Fake Provider、17 项 Playwright E2E 通过；机器收据覆盖 20 个独立页面、3 个兼容别名和 4 条真实 HTTP/SQLite 业务工作流，共 27 条功能记录。
- 生产边界：候选默认 `public-shell-readonly`，只开放产品导览、健康和部署元数据；业务读取、写入和 Provider 调用关闭。
- 交付边界：候选尚未合并、推送或部署。本地结果不能作为生产完成证明。

权威文档从 [docs/README.md](docs/README.md) 开始阅读。用户操作见 [用户 Playbook](docs/playbooks/user-playbook-medical-audit-v1-stable.md)，运维与安全边界见 [管理员运维 Playbook](docs/playbooks/admin-operations-playbook-stable.md)。

## 当前材料的权威层级

1. `docs/product/product-meeting-consensus-20260315-stable.md`
   当前 MVP 范围的最高优先级业务共识。
2. `docs/product/product-prd-medical-audit-v1-stable.md`
   当前 V1.0 产品执行基线，承接业务共识、架构边界和验收要求。
3. `docs/product/product-development-plan-medical-audit-stable.md`
   当前开发排期、交付物和里程碑基线。
4. `docs/product/product-scope-baseline-stable.md`
   基于现有材料整理出的统一产品范围基线。
5. `docs/knowledge/knowledge-query-evidence-register-stable.md`
   知识库查询引擎草稿证据登记表，说明哪些评测、迁移和 UI 复盘草稿可以作为历史证据保留。
6. `docs/knowledge/audit-agent-platform-reference-stable.pptx`
   上游平台能力参考材料，不直接作为当前医疗项目需求基线。
7. `data/医保审核前期资料/`
   当前项目的正式输入资料库。

## 目录说明

- `docs/product/`: 产品范围、会议共识、计划基线
- `docs/knowledge/`: 项目资料审计、参考材料、长期知识沉淀
- `docs/architecture/`: 后续系统架构、模块边界、数据流设计
- `docs/api/`: 后续接口设计
- `docs/workflows/`: 协作流程、操作规范
- `assets/images/`: 需要在文档中引用的正式图片资产
- `archive/docs/`: 原始源文件、历史版本和不再直接参与协作的材料
- `drafts/`: 未定稿分析、需求草稿、方案探索
- `tmp/`: 临时输出、截图、调试产物
- `data/`: 正式输入资料和知识源文件

## 开发与验证

```bash
uv run pytest
uv run ruff check .
uv run mypy src
pnpm web:test
pnpm web:typecheck
pnpm web:lint
pnpm web:build
pnpm local:fullstack:e2e
pnpm docs:lint
```

`pnpm local:fullstack:e2e` 不使用生产数据或真实 Provider。未经单独授权，不执行生产部署、业务写入、Provider 调用或备份删除。

## 已实现能力概览

- Next.js 前端提供 20 个独立页面和 3 个兼容别名。
- FastAPI 提供知识问答、文档、OCR、合同审计、智能体、项目、疑点、报告、整改、索引和日志 API。
- PostgreSQL/pgvector 支持知识检索和持久化业务 Store；本地 E2E 使用临时 SQLite。
- 整改状态迁移和报告签发由服务端返回能力字段并执行权限门禁。
- 生产构建通过 release manifest 绑定 Git SHA、lockfile、公开构建变量和静态文件哈希。

## 明确保留的后续任务

- 可信 SSO/OIDC 和身份代理。
- 生产业务读取、写入和 Provider UAT。
- 真实 HIS、DLP、OCR/LLM Provider 和医院现场验收。
- rules、archive 和部分智能体配置从 Sample/Preview 升级为持久化功能。
- 隔离恢复演练、性能基线、告警/Webhook 和灾备演练。

---
title: AI 审计一体化协作平台仓库说明
doc_type: knowledge
module: repository
topic: project-overview
status: stable
created: 2026-05-31
updated: 2026-08-22
owner: self
source: human+ai
---

# AI 审计一体化协作平台

## 当前定位

本仓库是面向医院场景的私有化医疗审计产品，不是通用 SaaS 或纯研究仓库。核心目标是在可信身份和数据治理边界内完成「知识依据 → 合规判断与疑点 → 底稿与报告 → 整改跟踪」。

核心闭环为：

`法规与知识支撑 -> 合规判断与风险识别 -> 审计底稿与报告 -> 整改跟踪`

## 当前候选状态

- 外部观察：截至 2026-08-22 00:59（Asia/Shanghai），Draft PR [#275](https://github.com/zjgulai/medical-audit/pull/275) 的 base 为 `ccc73e95820e39559430e96c01d52c8dfb77a246`，观测 head 为 `d1973206d4f9b01ad0b287fb252fccf760fdab5c`；PR 为 `OPEN/DRAFT`、`MERGEABLE/CLEAN`，review、review request 和 review thread 均为 0。
- exact-head CI：[run 32499803192](https://github.com/zjgulai/medical-audit/actions/runs/32499803192) 在上述观测 head 通过 Python `1018` 项和 Web `419` 项测试，以及 Ruff、Mypy、typecheck、lint、普通构建、公开壳层构建和文档检查；Web 原始日志中的 React `act()` warning 为 0。CodeRabbit status 明确写明因 Draft 跳过 review，不能视为代码评审通过。
- 候选范围：相对 base 为 13 个提交、103 个文件，包含生产公开壳层访问门禁、部署合同、疑点深链、整改与报告权限、知识统计、本地全栈验收和完整文档体系。路由合同为 21 个独立页面、2 个兼容跳转、4 条业务工作流和 27 条功能记录。
- 身份合同：tracked 文档只保存带时间的外部观察，不声明自身 commit SHA 或瞬时 push 状态。最新候选身份必须从 GitHub PR、Actions run 和仓库外收据共同解析。
- 生产历史证据：2026 年 8 月 12 日 L3 只读观测为 `25e1654e0c44ca5cbb2bb42e82debdb40fa6f224`。
- 本地验收：临时 SQLite、确定性 Fake Provider、17 项 Playwright E2E 通过，`provider_call=false`。该证据属于 L2 本地活体验证，不能替代生产验收。
- 生产边界：候选默认 `public-shell-readonly`，只开放产品导览、健康和部署元数据；业务读取、写入和 Provider 调用关闭。
- 交付边界：上述观察只证明 `d1973206…` 的 exact-head CI 和 PR 元数据。它不证明 review、Ready、merge、部署或生产业务验收；当前 tracked 文档同步提交及其后续 CI 由 GitHub 与仓库外收据另行绑定。

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

- Next.js 前端提供 21 个独立页面和 2 个兼容跳转；`/workspace` 是独立工作台，不是别名。
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

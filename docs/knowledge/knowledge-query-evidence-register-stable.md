---
title: 知识库查询引擎草稿证据登记表
doc_type: knowledge
module: knowledge-query-engine
topic: evidence-register
status: stable
created: 2026-06-02
updated: 2026-06-02
owner: self
source: human+ai
---

# 知识库查询引擎草稿证据登记表

## 1. 定位

本文只登记 `drafts/` 中与知识库查询引擎相关的草稿证据，解决三个问题：

- 哪些草稿可以作为历史评测和迁移证据保留。
- 哪些草稿已经被正式文档吸收，不应再作为当前状态来源。
- 哪些草稿仍需重新运行或人工确认后才能晋升为正式验收材料。

当前正式事实源仍是：

- `docs/architecture/architecture-knowledge-query-engine-stable.md`
- `docs/api/api-knowledge-query-engine-stable.md`
- `docs/workflows/workflow-knowledge-query-engine-operations-stable.md`
- `docs/product/product-prd-medical-audit-v1-stable.md`

## 2. 使用规则

- `drafts/analysis/` 和 `drafts/docs/` 是证据与过程记录，不是当前状态的最高优先级来源。
- 草稿中的历史指标只能说明当次运行结果；发布、回滚、上线验收前必须重新运行当前门禁。
- 涉及外部 provider 的失败或成功结论只对当次 key、模型、base URL 和日期有效。
- `tmp/outputs/` 中的 JSON 是机器证据，默认不入正式文档；正式文档只引用汇总指标和路径。
- 未在本文登记的草稿不得作为 PRD、架构或验收结论的直接依据。

## 3. 草稿处理结论

| 草稿文件 | 证据类型 | 当前处理 | 理由 |
| --- | --- | --- | --- |
| `drafts/analysis/git-diff-atomic-commit-plan-draft-20260602.md` | 提交拆分过程 | 保留草稿，不晋升 | 已完成原子提交，后续只作为提交治理过程记录。 |
| `drafts/analysis/knowledge-extraction-chat-ui-20-loop-report-draft-20260601.md` | 萃取与 UI 复盘 | 保留草稿，不晋升 | 已提炼进 PRD、架构和运行手册；细节仍可作为 UI/抽取债务证据。 |
| `drafts/analysis/knowledge-extraction-to-chat-workflow-review-draft-20260602.md` | 全链路复盘 | 保留草稿，后续可拆分晋升 | 内容覆盖未完成任务和完整工作流，但部分实现已变化，需按当前代码再校准后才能转正。 |
| `drafts/analysis/knowledge-query-answer-evaluation-kimi-v1-draft-20260601.md` | fallback 答案评测 | 保留草稿，不单独晋升 | 核心指标已进入架构文档；草稿保留为 8 case 评测证据。 |
| `drafts/analysis/knowledge-query-answer-generation-kimi-v1-draft-20260601.md` | 真实生成评测 | 保留草稿，不单独晋升 | 证明 Kimi Code chat completion 当次不可用；换 key 或模型后必须重跑。 |
| `drafts/analysis/knowledge-query-answer-provider-smoke-anthropic-draft-20260601.md` | Provider 预检 | 保留草稿，不单独晋升 | 当次 Anthropic key 无效，不能外推为 provider 永久不可用。 |
| `drafts/analysis/knowledge-query-answer-provider-smoke-kimi-draft-20260601.md` | Provider 预检 | 保留草稿，不单独晋升 | 当次 Kimi chat endpoint 返回受限错误；当前只确认 embedding 可用。 |
| `drafts/analysis/knowledge-query-e2e-20-loop-report-draft-20260601.md` | UI E2E 记录 | 保留草稿，不晋升 | 属于历史 UI smoke 和迭代记录；正式验收以当前测试和发布门禁为准。 |
| `drafts/analysis/knowledge-query-human-evaluation-kimi-v1-draft-20260601.md` | 固定 52 case 检索评测 | 保留草稿，不单独晋升 | 指标已进入架构文档；草稿保留为评测明细证据。 |
| `drafts/analysis/knowledge-query-incremental-plan-current-draft-20260602.md` | 增量计划报告 | 保留草稿，新增资料后重跑 | 当次结论为无新增、无修改、无删除；新资料进入后不能复用该结论。 |
| `drafts/analysis/knowledge-query-pgvector-import-dry-run-kimi-draft-20260601.md` | pgvector dry-run | 保留草稿，不单独晋升 | 数据规模和准备状态已进入架构文档；草稿保留为导入前证据。 |
| `drafts/analysis/knowledge-query-pgvector-import-execute-kimi-draft-20260601.md` | pgvector 执行报告 | 保留草稿，不单独晋升 | 数据库写入结果已进入架构文档；草稿保留为执行明细证据。 |
| `drafts/analysis/knowledge-query-pgvector-import-plan-kimi-draft-20260601.md` | pgvector 导入前校验 | 保留草稿，不单独晋升 | 当前 schema 和结果已正式化；草稿保留为导入前校验明细。 |
| `drafts/analysis/knowledge-query-postgres-bm25-evaluation-v1-draft-20260601.md` | PostgreSQL BM25 评测 | 保留草稿，不单独晋升 | 指标已进入架构文档；发布前应通过 API 验收入口重跑。 |
| `drafts/analysis/knowledge-query-postgres-kimi-evaluation-v1-draft-20260601.md` | PostgreSQL Kimi 评测 | 保留草稿，不单独晋升 | 属于特定 provider 和索引版本的运行证据，不能作为未来版本默认结论。 |
| `drafts/analysis/knowledge-query-real-data-acceptance-report-draft-20260531.md` | 真实资料索引验收 | 保留草稿，不晋升 | 已被后续 Kimi/pgvector 路径覆盖，作为早期验收证据保留。 |
| `drafts/analysis/knowledge-query-real-data-kimi-evaluation-draft-20260531.md` | Kimi 真实资料评测 | 保留草稿，不晋升 | 已被 2026-06-01 固定集评测覆盖，作为历史基线保留。 |
| `drafts/analysis/knowledge-query-real-data-kimi-evaluation-draft-20260601.md` | Kimi 真实资料评测 | 保留草稿，不单独晋升 | 指标已进入架构文档；草稿保留为运行证据。 |
| `drafts/analysis/knowledge-query-real-data-kimi-smoke-evaluation-draft-20260531.md` | Kimi smoke 评测 | 保留草稿，不晋升 | 仅覆盖小样本，不代表全量质量。 |
| `drafts/analysis/knowledge-query-real-data-retrieval-evaluation-draft-20260531.md` | fake embedding 评测 | 保留草稿，不晋升 | 只证明工程闭环，不代表真实语义质量。 |
| `drafts/analysis/session-summary-knowledge-query-engine-kimi-evaluation-draft-20260601.md` | 会话交接 | 保留草稿，不晋升 | 只能作为历史上下文，不能替代代码和正式文档核验。 |
| `drafts/docs/architecture-knowledge-query-engine-kimi-embedding-plan-draft-20260531.md` | Kimi embedding 接入计划 | 保留草稿，不晋升 | 计划已基本被架构和运行手册吸收，保留为设计过程记录。 |
| `drafts/docs/architecture-knowledge-query-engine-pgvector-migration-plan-draft-20260601.md` | pgvector 迁移计划 | 保留草稿，不晋升 | 迁移状态已正式化，草稿保留为迁移步骤和门禁细节。 |
| `drafts/docs/architecture-knowledge-query-engine-real-data-acceptance-plan-draft-20260531.md` | 真实资料验收计划 | 保留草稿，不晋升 | 早期实施计划已被后续运行手册和评测入口覆盖。 |

## 4. 可晋升条件

以下情况发生后，再考虑从草稿晋升为正式文档：

- 增量索引完成 DB 级 candidate 写入、active 切换、旧版本失活和删除文件处理。
- `answer-provider-smoke` 在目标交付模型上通过，并完成真实生成答案评测。
- UI 对话能力从单轮审证升级为服务端持久化会话、问题改写、证据复核和导出。
- OCR、压缩包解包、`.doc/.docx/.csv` 抽取策略进入正式实现并通过验收。
- 发布门禁由人工命令升级为可重复的 `acceptance-run` 或等价流程。

## 5. 当前不归档原因

本批草稿虽然不是正式事实源，但仍满足保留条件：

- 多数草稿包含一次性运行指标、错误码、路径和验收细节。
- 后续排查 Kimi provider、pgvector 导入、PostgreSQL 检索、UI smoke 时仍有参考价值。
- 文件已位于 `drafts/`，不会污染正式目录。

下次正式发布后，如果这些草稿不再参与排查，可整体移动到 `archive/docs/` 或 `archive/experiments/`，并保留本文的登记结论。

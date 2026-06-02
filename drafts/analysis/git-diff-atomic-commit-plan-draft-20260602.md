---
title: Git Diff 原子提交拆分计划
doc_type: analysis
module: repository-governance
topic: git-diff-atomic-commit-plan
status: draft
created: 2026-06-02
updated: 2026-06-02
owner: self
source: ai
---

# Git Diff 原子提交拆分计划

## 1. 当前事实

- 当前没有 staged 文件，不能直接提交。
- 当前 tracked 修改为 38 个文件，untracked 可提交候选为 63 个文件。
- `tmp/`、`__pycache__`、`.DS_Store` 被 `.gitignore` 排除，不进入提交候选。
- 明文密钥扫描未发现常见高风险 API key 前缀、环境变量明文赋值或配置项明文赋值。
- 新增 Markdown 草稿和正式文档均已带 frontmatter。
- `archive/snapshots/` 下两个 SQL 文件为 PostgreSQL dump/schema 快照，体量约 4K 和 20K，未发现业务数据正文。

## 2. 当前验证基线

- `uv run pytest tests/knowledge_query`：141 passed，1 warning。
- `uv run ruff format --check .`：通过，82 files already formatted。
- `uv run ruff check .`：通过。
- `uv run mypy src tests`：通过，82 source files。
- `git diff --check`：通过。
- 本地 `http://127.0.0.1:8010` 已启动，PostgreSQL 后端 ready，`matching_embedding_count=48985`。

## 3. 禁止直接打包提交

当前 diff 中多处文件同时包含功能变更、格式化变更和类型门禁修复。

禁止使用：

- `git add .`
- `git add src tests docs configs drafts archive scripts pyproject.toml uv.lock`
- 单个“大而全”提交

原因：

- `routes_index.py` 同时包含搜索后端、版本激活、验收运行、历史报告等多类行为。
- `routes_pages.py` 和 `index_admin.html` 同时包含 UI、验收状态、历史入口。
- `sql/knowledge-query-schema.sql` 同时包含 1024 维 schema、HNSW 索引、评价历史表。
- `tests/knowledge_query/test_api.py` 同时覆盖多个 API 行为，不适合整文件归入单一提交。
- `ruff format .` 对多个既有改动文件产生格式噪音，应随对应功能 hunk 一起 staging，不能独立整文件提交。

## 4. 建议提交顺序

### Commit 1：建立真实资料抽取与索引基础能力

目标：让 data 目录资料能稳定抽取、切分、形成可验收索引产物。

候选文件：

- `src/medical_audit_kb/acceptance/`
- `src/medical_audit_kb/ingestion/chunkers.py`
- `src/medical_audit_kb/ingestion/extractors.py`
- `src/medical_audit_kb/ingestion/inventory.py`
- `src/medical_audit_kb/ingestion/pipeline.py`
- `src/medical_audit_kb/indexing/bm25_index.py`
- `src/medical_audit_kb/indexing/vector_index.py`
- `src/medical_audit_kb/indexing/persistent_index.py`
- `tests/knowledge_query/test_acceptance_reports.py`
- `tests/knowledge_query/test_chunkers.py`
- `tests/knowledge_query/test_extractors.py`
- `tests/knowledge_query/test_index_backends.py`
- `tests/knowledge_query/test_persistent_index.py`
- `tests/knowledge_query/test_repositories.py`

注意：`pyproject.toml` 中 `numpy` 依赖应随该提交进入，因为 vector index 使用 `numpy`。

### Commit 2：接入 Kimi/OpenAI-compatible 向量与 pgvector 写入链路

目标：把本地索引产物写入 PostgreSQL/pgvector，并固定 Kimi 1024 维 schema。

候选文件：

- `sql/knowledge-query-schema.sql` 中 1024 维、metadata GIN、locator GIN、Kimi HNSW 相关 hunk
- `src/medical_audit_kb/indexing/pgvector_import.py`
- `src/medical_audit_kb/indexing/pgvector_writer.py`
- `src/medical_audit_kb/indexing/embeddings.py` 中 OpenAI-compatible embedding provider 相关 hunk
- `archive/snapshots/postgres-pre-pgvector-import-20260601160814.sql`
- `archive/snapshots/postgres-schema-before-pgvector-import-20260601160829.sql`
- `tests/knowledge_query/test_pgvector_import.py`
- `tests/knowledge_query/test_pgvector_writer.py`
- `tests/knowledge_query/test_sql_assets.py` 中 pgvector schema 相关 hunk

注意：`sql/knowledge-query-schema.sql` 需要 patch staging，不要把 `index_evaluation_runs` 历史表 hunk 混进本提交。

### Commit 3：补齐 PostgreSQL active-version 检索、激活、回滚和增量计划

目标：让 PostgreSQL 检索只读 active indexed 版本，并支持发布/回滚/增量计划。

候选文件：

- `src/medical_audit_kb/retrieval/postgres_search.py`
- `src/medical_audit_kb/api/postgres_status.py`
- `src/medical_audit_kb/indexing/index_activation.py`
- `src/medical_audit_kb/indexing/incremental_plan.py`
- `src/medical_audit_kb/cli.py` 中 pgvector、activate、rollback、incremental-plan 相关 hunk
- `scripts/serve-chat-workbench.sh`
- `tests/knowledge_query/test_postgres_search.py`
- `tests/knowledge_query/test_postgres_status.py`
- `tests/knowledge_query/test_index_activation.py`
- `tests/knowledge_query/test_cli_index_activation.py`
- `tests/knowledge_query/test_incremental_plan.py`
- `tests/knowledge_query/test_cli_incremental_plan.py`
- `tests/knowledge_query/test_scripts.py`

注意：`routes_index.py` 中 search-backend、activate、rollback hunk 可归入本提交；evaluation/history hunk 不归入本提交。

### Commit 4：建立固定检索评测、答案评测和答案 provider 预检

目标：把知识库质量从人工感觉推进到固定 case 集和 answer gate。

候选文件：

- `configs/evaluation/knowledge-query-human-evaluation-cases-v1.yaml`
- `configs/evaluation/knowledge-query-answer-evaluation-cases-v1.yaml`
- `src/medical_audit_kb/evaluation/`
- `src/medical_audit_kb/generation/answer_builder.py`
- `src/medical_audit_kb/generation/answer_preflight.py`
- `src/medical_audit_kb/generation/answer_providers.py`
- `src/medical_audit_kb/generation/citations.py`
- `tests/knowledge_query/test_answer_evaluation.py`
- `tests/knowledge_query/test_answer_providers.py`
- `tests/knowledge_query/test_citations.py`
- `tests/knowledge_query/test_evaluation.py`

注意：`answer_builder.py` 的 Protocol 只读属性修复也可归入质量门禁提交；如果用 patch staging，本提交只收答案行为相关 hunk。

### Commit 5：上线对话审证、原文预览和索引管理 UI

目标：把知识库从 API 能跑推进到可使用的对话工作台。

候选文件：

- `src/medical_audit_kb/api/static/app.css`
- `src/medical_audit_kb/api/templates/chat.html`
- `src/medical_audit_kb/api/templates/query.html`
- `src/medical_audit_kb/api/templates/preview.html`
- `src/medical_audit_kb/api/templates/index_admin.html` 中 UI 基础 hunk
- `src/medical_audit_kb/api/routes_pages.py` 中 chat/query/index-admin 页面 hunk
- `src/medical_audit_kb/api/routes_preview.py`
- `src/medical_audit_kb/api/app.py` 中 search backend 状态字段 hunk
- `docs/product/product-scope-baseline-stable.md`
- `drafts/docs/product-knowledge-query-ui-ux-plan-draft-20260601.md`
- `tests/knowledge_query/test_pages.py`
- `tests/knowledge_query/test_preview_resolver.py`

注意：`index_admin.html` 和 `routes_pages.py` 中验收历史 hunk 不归入本提交。

### Commit 6：接入发布后验收报告持久化和历史列表

目标：让发布后固定验收可下载、可复盘、可查询历史。

候选文件：

- `src/medical_audit_kb/api/evaluation_reports.py`
- `src/medical_audit_kb/db/models.py` 中 `IndexEvaluationRun` hunk
- `sql/knowledge-query-schema.sql` 中 `index_evaluation_runs` 相关 hunk
- `src/medical_audit_kb/api/routes_index.py` 中 `/index/evaluation/run`、`/index/evaluation/latest/export`、`/index/evaluation/history` hunk
- `src/medical_audit_kb/api/routes_pages.py` 中 evaluation status/history context hunk
- `src/medical_audit_kb/api/templates/index_admin.html` 中 Acceptance Panel 和验收历史 hunk
- `docs/api/api-knowledge-query-engine-stable.md`
- `docs/architecture/architecture-knowledge-query-engine-stable.md`
- `docs/workflows/workflow-knowledge-query-engine-operations-stable.md`
- `tests/knowledge_query/test_api.py` 中 evaluation/history hunk
- `tests/knowledge_query/test_pages.py` 中 Acceptance Panel 和验收历史断言 hunk
- `tests/knowledge_query/test_sql_assets.py` 中 evaluation history table 断言 hunk

### Commit 7：收口类型与格式门禁

目标：让仓库形成稳定质量门禁，避免后续每轮都被历史格式和类型噪音阻塞。

候选文件：

- `pyproject.toml` 中 `types-openpyxl` dev 依赖
- `uv.lock`
- Protocol 只读属性相关 hunk
- `openpyxl` `type: ignore` 移除 hunk
- `Workbook.active is not None` 测试断言 hunk
- `RecordingCursor.executemany` 签名 hunk
- `test_cli_incremental_plan.py` fake 参数类型检查 hunk
- 全仓 `ruff format` 产生的纯格式 hunk

注意：此提交最容易和功能提交混杂。更推荐把纯格式 hunk 随对应功能提交进入；如果坚持单独提交，需要用 `git add -p` 只 stage 格式和类型 hunk。

### Commit 8：提交评测、迁移和运行复盘草稿

目标：保留关键执行证据，但不把草稿伪装成正式状态。

候选文件：

- `drafts/analysis/knowledge-*.md`
- `drafts/docs/architecture-knowledge-query-engine-*-draft-*.md`
- `drafts/docs/product-knowledge-query-ui-ux-plan-draft-20260601.md`

注意：这些文件是草稿区资产，适合单独提交。不要和正式代码提交混在一起。

## 5. Patch Staging 高风险文件

以下文件必须使用 `git add -p` 或等效 patch staging：

- `src/medical_audit_kb/api/routes_index.py`
- `src/medical_audit_kb/api/routes_pages.py`
- `src/medical_audit_kb/api/templates/index_admin.html`
- `sql/knowledge-query-schema.sql`
- `tests/knowledge_query/test_api.py`
- `tests/knowledge_query/test_pages.py`
- `tests/knowledge_query/test_sql_assets.py`
- `src/medical_audit_kb/generation/answer_builder.py`
- `src/medical_audit_kb/indexing/embeddings.py`

原因：这些文件跨越多个逻辑提交，整文件 staging 会破坏提交原子性。

## 6. 建议执行命令

每个提交前运行：

```bash
git diff --cached --check
uv run pytest tests/knowledge_query
uv run ruff format --check .
uv run ruff check .
uv run mypy src tests
```

每个提交使用中文提交信息，描述“为什么”：

```bash
git commit -m "建立知识库真实资料索引验收基线"
git commit -m "接入 Kimi 向量写入与 pgvector 检索底座"
git commit -m "收口 PostgreSQL active 版本发布与回滚链路"
git commit -m "建立固定评测和引用答案质量门禁"
git commit -m "上线医保审核知识库对话审证工作台"
git commit -m "沉淀发布后验收报告和历史复盘能力"
git commit -m "收口知识库工程类型和格式门禁"
git commit -m "归档知识库搭建评测和迁移复盘草稿"
```

## 7. 当前不建议提交的内容

- `tmp/` 下运行报告、debug HTML、API 响应：已被 `.gitignore` 排除。
- `__pycache__/`：已被 `.gitignore` 排除。
- `.DS_Store`：已被 `.gitignore` 排除。
- 明文 API key：未发现，且后续必须继续只通过进程环境变量传入。

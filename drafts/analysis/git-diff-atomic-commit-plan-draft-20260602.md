---
title: Git Diff 原子提交拆分计划
doc_type: analysis
module: repository-governance
topic: git-diff-atomic-commit-plan
status: draft
created: 2026-06-02
updated: 2026-06-03
owner: self
source: ai
---

# Git Diff 原子提交拆分计划

## 1. 当前事实

- 当前分支：`codex/index-candidate-release-readiness`。
- 当前没有 staged 文件，不能直接提交。
- 本轮审计时点的 tracked 修改为 21 个文件，untracked 可提交候选为 13 个文件。
- `tmp/`、`.DS_Store`、缓存目录和 `*.pem` 已被 `.gitignore` 排除。
- `ai_video.pem` 当前仍物理位于项目根目录，但已被忽略，不进入提交候选；后续应迁出仓库目录，避免目录治理噪音。
- 密钥扫描未发现真实 `sk-*` API key、私钥正文或生产 `.env` 进入可提交文件；`configs/deploy/tencent-cloud/medical-audit.env.example` 只保留占位符。
- 新增正式 Markdown 文档已带 frontmatter。

## 2. 已完成验证基线

最近一轮完整验证已通过：

- `git diff --check`：通过。
- 正式文档 trailing whitespace 检查：通过。
- `uv run pytest -q`：通过。
- `uv run ruff check .`：通过。
- `uv run ruff format --check .`：通过。

生产验证事实：

- 当前生产地址：`https://audit.lute-tlz-dddd.top/pages/chat`。
- 当前 active index：`full-rebuild-20260603085815`。
- 当前 inactive rollback target：`full-rebuild-20260531142344`。
- PostgreSQL 计数：`source_documents=972`、`document_chunks=97970`、`chunk_embeddings=97970`。
- active 侧匹配索引：`486` documents、`48985` chunks、`48985` embeddings。
- candidate write、activation、rollback rehearsal、return-to-new-active、API evaluation、production readonly E2E 均已完成。

证据等级边界：

- candidate dry-run / readiness report：`L2-fixture-or-dry-run`。
- 生产页面、health、search-backend、readonly E2E：`L3-production-read-only`。
- 已授权并执行的 candidate write、activation、rollback rehearsal：`L4-authorized-live`。
- 以上不等于“无风险生产闭环”；仍需要提交拆分、CI/远端重建复核和后续 secret 管理改造。

## 3. 禁止直接打包提交

禁止使用：

- `git add .`
- `git add src tests docs scripts configs drafts`
- 单个“大而全”提交

原因：

- `routes_pages.py` 同时包含查询页信息架构、对话页审计底稿导出、复核任务台、表单解析和导出逻辑。
- `tests/knowledge_query/test_scripts.py` 同时覆盖部署容器启动、生产 E2E、pending 文件分类、candidate readiness、rollback readiness。
- `docs/api/api-knowledge-query-engine-stable.md` 和 `docs/workflows/workflow-knowledge-query-engine-operations-stable.md` 同时记录 CLI 参数、candidate 发布、activation、rollback 和生产验收。
- 一次性提交会让后续回滚无法判断是 UI、部署、索引生命周期还是文档同步引入问题。

## 4. 建议提交顺序

### Commit 1：隔离腾讯云部署运行环境

目标：把腾讯云部署资产、容器启动脚本和生产 smoke 固化为可复用运维入口，不携带真实密钥。

候选文件：

- `.dockerignore`
- `.gitignore`
- `configs/deploy/tencent-cloud/Dockerfile`
- `configs/deploy/tencent-cloud/docker-compose.prod.yaml`
- `configs/deploy/tencent-cloud/medical-audit.env.example`
- `configs/deploy/tencent-cloud/nginx-audit-server.conf`
- `scripts/serve-chat-workbench-container.py`
- `scripts/run-production-e2e-smoke.py`
- `docs/workflows/workflow-tencent-cloud-audit-deployment-stable.md`

需要 patch staging：

- `tests/knowledge_query/test_scripts.py` 中容器启动脚本和生产 E2E smoke 相关测试。

提交前验证：

```bash
uv run pytest tests/knowledge_query/test_scripts.py -q
uv run ruff check .
uv run ruff format --check .
git diff --cached --check
```

建议提交信息：

```bash
git commit -m "隔离腾讯云部署环境并固化生产 smoke"
```

### Commit 2：收口索引候选发布、激活与回滚门禁

目标：修复跨资料包 chunk_id 冲突风险，并让 candidate、active、inactive 的评测和回滚链路可审计。

候选文件：

- `src/medical_audit_kb/indexing/persistent_index.py`
- `src/medical_audit_kb/retrieval/postgres_search.py`
- `src/medical_audit_kb/cli.py`
- `scripts/audit-index-candidate-release-readiness.py`
- `scripts/audit-index-rollback-readiness.py`
- `tests/knowledge_query/test_persistent_index.py`
- `tests/knowledge_query/test_postgres_search.py`
- `tests/knowledge_query/test_cli.py`

需要 patch staging：

- `tests/knowledge_query/test_scripts.py` 中 candidate readiness 和 rollback readiness 相关测试。
- `docs/api/api-knowledge-query-engine-stable.md` 中 `evaluate-postgres-index --index-version-status/--index-version-key`、candidate 验证、rollback 相关 hunk。
- `docs/workflows/workflow-knowledge-query-engine-operations-stable.md` 中 candidate write、activation、rollback rehearsal、return-to-new-active 相关 hunk。

提交前验证：

```bash
uv run pytest tests/knowledge_query/test_persistent_index.py tests/knowledge_query/test_postgres_search.py tests/knowledge_query/test_cli.py tests/knowledge_query/test_scripts.py -q
uv run ruff check .
uv run ruff format --check .
git diff --cached --check
```

建议提交信息：

```bash
git commit -m "收口索引候选发布与回滚门禁"
```

### Commit 3：完善对话审证 UI、底稿导出与复核任务台

目标：把知识库网站从“查询页面”推进到“审计员可使用的证据工作台”，但明确复核任务仍为进程内能力，不等价生产案件系统。

候选文件：

- `src/medical_audit_kb/api/app.py`
- `src/medical_audit_kb/api/routes_pages.py`
- `src/medical_audit_kb/api/static/app.css`
- `src/medical_audit_kb/api/templates/chat.html`
- `src/medical_audit_kb/api/templates/query.html`
- `src/medical_audit_kb/api/templates/preview.html`
- `src/medical_audit_kb/api/templates/index_admin.html`
- `src/medical_audit_kb/api/templates/review_tasks.html`
- `tests/knowledge_query/test_pages.py`
- `drafts/analysis/knowledge-extraction-chat-ui-20-loop-report-draft-20260601.md`

需要 patch staging：

- `routes_pages.py` 如果后续继续拆分，可把 source collection 卡片、dossier export、review task 三组 hunk 分开；当前文件内逻辑都服务于审证工作台，可作为一个 UI/UX 提交。
- `tests/knowledge_query/test_pages.py` 建议整文件归入本提交，因为新增断言集中覆盖 UI、底稿导出、复核任务和 favicon 噪音修复。

提交前验证：

```bash
uv run pytest tests/knowledge_query/test_pages.py -q
uv run ruff check .
uv run ruff format --check .
git diff --cached --check
```

建议提交信息：

```bash
git commit -m "完善医保审证工作台与复核底稿闭环"
```

### Commit 4：补齐知识库 pending 分类和视觉基线工具

目标：把源文件萃取过程中的 pending 文件分类、视觉基线采集沉淀为可重复脚本。

候选文件：

- `scripts/classify-knowledge-pending-files.py`
- `scripts/capture-chat-workbench-visual-baseline.py`

需要 patch staging：

- `tests/knowledge_query/test_scripts.py` 中 pending 文件分类和视觉基线脚本相关测试。

提交前验证：

```bash
uv run pytest tests/knowledge_query/test_scripts.py -q
uv run ruff check .
uv run ruff format --check .
git diff --cached --check
```

建议提交信息：

```bash
git commit -m "沉淀知识库萃取分类与视觉基线工具"
```

### Commit 5：同步 PRD、开发计划和运行文档

目标：把已完成的生产发布、索引生命周期和下一阶段产品规划同步到正式文档，避免代码事实与文档事实分叉。

候选文件：

- `docs/product/product-development-plan-medical-audit-stable.md`
- `docs/product/product-prd-medical-audit-v1-stable.md`
- `docs/api/api-knowledge-query-engine-stable.md` 中未随 Commit 2 进入的文档 hunk。
- `docs/workflows/workflow-knowledge-query-engine-operations-stable.md` 中未随 Commit 2 进入的文档 hunk。

需要 patch staging：

- `docs/api/api-knowledge-query-engine-stable.md`
- `docs/workflows/workflow-knowledge-query-engine-operations-stable.md`

提交前验证：

```bash
git diff --cached --check
uv run pytest -q
uv run ruff check .
uv run ruff format --check .
```

建议提交信息：

```bash
git commit -m "同步知识库生产发布与下一阶段规划"
```

## 5. 当前不建议提交的内容

- `tmp/` 下所有生产 smoke、评测、截图、中间输出。
- `.mypy_cache/`、`.pytest_cache/`、`.ruff_cache/`。
- `.DS_Store`。
- `ai_video.pem`。
- 任何真实 API key、生产 `.env`、数据库 dump 明文。

## 6. 下一步执行策略

推荐先执行 Commit 1。原因：

- 部署资产和生产 smoke 是当前生产可恢复性的基础。
- 文件边界相对清晰，最少依赖 patch staging。
- 提交后可以独立验证“重新部署/重跑生产 smoke”的能力，不与 UI 和索引逻辑纠缠。

执行规则：

- 只使用显式路径 `git add <path>`。
- 对 `tests/knowledge_query/test_scripts.py` 使用 patch staging。
- 每个提交前必须重新运行对应测试和 `git diff --cached --check`。
- 不使用 `git add .`。
- 不把未验证的 memory-derived 状态写成当前事实；生产状态变更前必须重新查询远端。

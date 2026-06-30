---
title: 医保基金审计系统前后端完整性盘点与分批执行计划
doc_type: workflow
module: fullstack
topic: completeness-audit-and-batch-execution
status: stable
created: 2026-06-21
updated: 2026-06-30
owner: self
source: human+ai
---

# 医保基金审计系统前后端完整性盘点与分批执行计划

## 1. 盘点口径

本文件用于冻结 2026-06-21 本地工作区的前端、后端和联调测试完整性，作为后续分批开发和验收入口。

证据边界：

- `validation_scope=local_repo_and_local_fullstack_smoke`
- `production_side_effect=none`
- `provider_call_status=not_called`
- `default_postgres_status=not_running_on_127.0.0.1:5433`
- `fullstack_smoke_backend=in_memory_fake_provider`
- `production_status_source=existing_state_register_only`

本轮没有生产部署、没有生产写入、没有外部 AI provider 调用。Playwright 联调使用一次性 FastAPI 内存态服务验证 Next rewrites 和核心 API 契约，不代表真实 PostgreSQL、真实医院数据或生产索引验收。

## 2. 新鲜验证证据

本轮已执行：

- `uv run ruff check .`：通过。
- `uv run mypy src`：通过，`88` 个 source files。
- `uv run pytest tests/knowledge_query`：通过，`288 passed`，`1` 个既有 `StarletteDeprecationWarning`。
- `pnpm --filter medical-audit-web lint`：通过。
- `pnpm --filter medical-audit-web typecheck`：通过。
- `pnpm --filter medical-audit-web test`：通过，`11` 个 test files、`91` 个 tests。
- `pnpm --filter medical-audit-web build`：通过，静态页面 `21/21`。
- `pnpm local:fullstack:e2e`：通过，`16 passed`，后端以强制受控 API 鉴权模式启动。
- `uv run python scripts/run-local-fullstack-e2e.py --backend-mode postgres-readonly --allow-unavailable --json-output tmp/outputs/local-postgres-readonly-smoke-20260621.json`：生成只读探测报告，状态为 `blocked`，原因是本机 `localhost:5433` PostgreSQL 未响应。
- `git diff --check`：通过。

2026-06-22 Batch 6.1 增量验证：

- 工作区清理：删除明确可重建的 `.pytest_cache`、`.ruff_cache`、`.mypy_cache`、`web/.next`、`web/test-results` 和 `155` 个 `__pycache__` 目录；未删除 `node_modules`、`.venv`、源码、配置、草稿、参考资料或项目状态文件。
- `uv run ruff check src/medical_audit_kb/api/routes_workbench.py tests/knowledge_query/test_pages.py`：通过。
- `uv run mypy src/medical_audit_kb/api/routes_workbench.py`：通过。
- `uv run pytest tests/knowledge_query/test_pages.py::test_graph_workbench_api_returns_readonly_topology`：通过，`1 passed`。
- `pnpm --dir web typecheck`：通过。
- `pnpm --dir web test -- --run src/lib/api-client.test.ts 'src/app/(workspace)/workspace-pages.test.tsx'`：通过，`2` 个 test files、`44` 个 tests。
- `uv run ruff check .`：通过。
- `uv run mypy src`：通过，`88` 个源码文件。
- `uv run pytest`：通过，`277 passed`，`1` 个既有 `StarletteDeprecationWarning`。
- `pnpm --dir web lint`：通过。
- `pnpm --dir web typecheck`：通过。
- `pnpm --dir web test -- --run`：通过，`11` 个 test files、`76` 个 tests。
- `pnpm --dir web build`：通过，静态页面 `21/21`，包含 `/graph`。
- `pnpm local:fullstack:e2e`：通过，`16 passed`。
- 验证后再次删除重新生成的 `.pytest_cache`、`.ruff_cache`、`.mypy_cache`、`web/.next`、`web/test-results` 和 `144` 个 `__pycache__` 目录，保持工作区不保留可重建缓存。

2026-06-22 Batch 6.2 增量验证：

- `uv run ruff check src/medical_audit_kb/api/routes_workbench.py tests/knowledge_query/test_pages.py`：通过。
- `uv run mypy src/medical_audit_kb/api/routes_workbench.py`：通过。
- `uv run pytest tests/knowledge_query/test_pages.py::test_rules_workbench_api_returns_readonly_rule_status`：通过，`1 passed`。
- `pnpm --dir web typecheck`：通过。
- `pnpm --dir web test -- --run src/lib/api-client.test.ts 'src/app/(workspace)/workspace-pages.test.tsx'`：通过，`2` 个 test files、`46` 个 tests。
- `uv run ruff check .`：通过。
- `uv run mypy src`：通过，`88` 个源码文件。
- `uv run pytest`：通过，`278 passed`，`1` 个既有 `StarletteDeprecationWarning`。
- `pnpm --dir web lint`：通过。
- `pnpm --dir web typecheck`：通过。
- `pnpm --dir web test -- --run`：通过，`11` 个 test files、`78` 个 tests。
- `pnpm --dir web build`：通过，静态页面 `21/21`，包含 `/rules`。
- `pnpm local:fullstack:e2e`：通过，`16 passed`。
- 验证后再次删除重新生成的 `.pytest_cache`、`.ruff_cache`、`.mypy_cache`、`web/.next`、`web/test-results` 和 `144` 个 `__pycache__` 目录，保持工作区不保留可重建缓存。

2026-06-22 Batch 6.3 增量验证：

- `uv run ruff check src/medical_audit_kb/api/routes_workbench.py tests/knowledge_query/test_pages.py`：通过。
- `uv run mypy src/medical_audit_kb/api/routes_workbench.py`：通过。
- `uv run pytest tests/knowledge_query/test_pages.py::test_remediation_workbench_api_returns_readonly_gate_status`：通过，`1 passed`。
- `pnpm --dir web typecheck`：通过。
- `pnpm --dir web test -- --run src/lib/api-client.test.ts 'src/app/(workspace)/workspace-pages.test.tsx'`：通过，`2` 个 test files、`48` 个 tests。
- `uv run ruff check .`：通过。
- `uv run mypy src`：通过，`88` 个源码文件。
- `uv run pytest`：通过，`279 passed`，`1` 个既有 `StarletteDeprecationWarning`。
- `pnpm --dir web lint`：通过。
- `pnpm --dir web typecheck`：通过。
- `pnpm --dir web test -- --run`：通过，`11` 个 test files、`80` 个 tests。
- `pnpm --dir web build`：通过，静态页面 `21/21`，包含 `/remediation`。
- `pnpm local:fullstack:e2e`：通过，`16 passed`。
- 验证后再次删除重新生成的 `.pytest_cache`、`.ruff_cache`、`.mypy_cache`、`web/.next`、`web/test-results` 和 `144` 个 `__pycache__` 目录，保持工作区不保留可重建缓存。

2026-06-22 Batch 6.4 增量验证：

- `uv run ruff check src/medical_audit_kb/api/routes_workbench.py tests/knowledge_query/test_pages.py`：通过。
- `uv run mypy src/medical_audit_kb/api/routes_workbench.py`：通过。
- `uv run pytest tests/knowledge_query/test_pages.py::test_archive_workbench_api_returns_readonly_archive_status`：通过，`1 passed`，`1` 个既有 `StarletteDeprecationWarning`。
- `pnpm --dir web typecheck`：通过。
- `pnpm --dir web test -- --run src/lib/api-client.test.ts 'src/app/(workspace)/workspace-pages.test.tsx'`：通过，`2` 个 test files、`50` 个 tests。
- `uv run ruff check .`：通过。
- `uv run mypy src`：通过，`88` 个源码文件。
- `uv run pytest`：通过，`280 passed`，`1` 个既有 `StarletteDeprecationWarning`。
- `pnpm --dir web lint`：通过。
- `pnpm --dir web typecheck`：通过。
- `pnpm --dir web test -- --run`：通过，`11` 个 test files、`82` 个 tests。
- `pnpm --dir web build`：通过，静态页面 `21/21`，包含 `/archive`。
- `pnpm local:fullstack:e2e`：通过，`16 passed`。
- `git diff --check`：通过。

2026-06-22 Batch 7.1 增量验证：

- `uv run ruff check src/medical_audit_kb/api/agent_store.py src/medical_audit_kb/api/routes_agents.py src/medical_audit_kb/db/models.py tests/knowledge_query/test_api.py tests/knowledge_query/test_sql_assets.py`：通过。
- `uv run mypy src/medical_audit_kb/api/agent_store.py src/medical_audit_kb/api/routes_agents.py src/medical_audit_kb/db/models.py`：通过。
- `uv run pytest tests/knowledge_query/test_api.py -k "agents_api or audit_agent" tests/knowledge_query/test_sql_assets.py::test_pgvector_schema_includes_audit_agent_table`：通过，`5 passed`，`39 deselected`，`1` 个既有 `StarletteDeprecationWarning`。
- `pnpm --dir web typecheck`：通过。
- `pnpm --dir web test -- --run src/lib/api-client.test.ts 'src/app/(workspace)/workspace-pages.test.tsx'`：通过，`2` 个 test files、`53` 个 tests。
- `uv run ruff check .`：通过。
- `uv run mypy src`：通过，`88` 个源码文件。
- `uv run pytest`：通过，`281 passed`，`1` 个既有 `StarletteDeprecationWarning`。
- `pnpm --dir web lint`：通过。
- `pnpm --dir web typecheck`：通过。
- `pnpm --dir web test -- --run`：通过，`11` 个 test files、`85` 个 tests。
- `pnpm --dir web build`：通过，静态页面 `21/21`，包含 `/agents` 和 `/chat`。
- `pnpm local:fullstack:e2e`：通过，`16 passed`。

联调补充证据：

- `pg_isready -h 127.0.0.1 -p 5433 -U medical_audit_kb -d medical_audit_kb`：本机默认 PostgreSQL 未响应。
- 一次性 FastAPI 服务 `http://127.0.0.1:8021/health`：返回 `status=ok`。
- `POST /query`：返回带 citation 的 fallback answer，`query_log_id=in-memory-query-1`。
- `GET /agents`：返回系统默认智能体，`store.backend=InMemoryAgentStore`。

2026-06-22 Batch 7.2 增量验证：

- `uv run ruff check src/medical_audit_kb/api/agent_store.py src/medical_audit_kb/api/routes_agents.py src/medical_audit_kb/db/models.py tests/knowledge_query/test_api.py tests/knowledge_query/test_sql_assets.py`：通过。
- `uv run mypy src/medical_audit_kb/api/agent_store.py src/medical_audit_kb/api/routes_agents.py src/medical_audit_kb/db/models.py`：通过。
- `uv run pytest tests/knowledge_query/test_api.py -k "agents_api or audit_agent" tests/knowledge_query/test_sql_assets.py::test_pgvector_schema_includes_audit_agent_table`：通过，`5 passed`，`39 deselected`，`1` 个既有 `StarletteDeprecationWarning`。
- `pnpm --dir web test -- --run src/lib/api-client.test.ts 'src/app/(workspace)/workspace-pages.test.tsx'`：通过，`2` 个 test files、`57` 个 tests。
- `uv run ruff check .`：通过。
- `uv run mypy src`：通过，`88` 个源码文件。
- `uv run pytest`：通过，`281 passed`，`1` 个既有 `StarletteDeprecationWarning`。
- `pnpm --dir web lint`：通过。
- `pnpm --dir web typecheck`：通过。
- `pnpm --dir web test -- --run`：通过，`11` 个 test files、`89` 个 tests。
- `pnpm --dir web build`：通过，静态页面 `21/21`，包含 `/agents`。
- `pnpm local:fullstack:e2e`：通过，`16 passed`。

2026-06-22 Batch 7.3 增量验证：

- `/query` 已在选择 `agent` 时自动写入智能体调用记录并返回 `agent_invocation_id`。
- `/pages/chat` 已在选择 `agent` 时自动写入 `/pages/chat` 来源调用记录；`/pages/chat/export` 不重复登记新调用。
- `/agents` 已按 URL encoded `X-Project-Name` 执行项目级可见范围过滤和跨项目操作阻断。
- `/agents/{agent_key}/feedback` 已返回反馈统计 `summary`；Next `/agents` 已展示可继续使用、需要复核、暂不建议三类统计。
- `uv run pytest tests/knowledge_query/test_api.py::test_agents_api_tracks_prompt_versions_lifecycle_and_history tests/knowledge_query/test_api.py::test_agents_api_filters_project_scope_and_blocks_cross_project_invocation tests/knowledge_query/test_api.py::test_query_endpoint_returns_citation_answer_and_records_query_log tests/knowledge_query/test_api.py::test_query_endpoint_records_selected_agent_invocation tests/knowledge_query/test_pages.py::test_chat_page_renders_conversation_evidence_and_followups tests/knowledge_query/test_pages.py::test_chat_page_records_selected_agent_invocation_without_export_duplication tests/knowledge_query/test_pages.py::test_chat_dossier_export_returns_json_download_and_records_log`：通过，`7 passed`，`1` 个既有 `StarletteDeprecationWarning`。
- `uv run ruff check src/medical_audit_kb/api/routes_agents.py src/medical_audit_kb/api/routes_query.py src/medical_audit_kb/api/routes_pages.py tests/knowledge_query/test_api.py tests/knowledge_query/test_pages.py`：通过。
- `uv run mypy src/medical_audit_kb/api/agent_store.py src/medical_audit_kb/api/routes_agents.py src/medical_audit_kb/api/routes_query.py src/medical_audit_kb/api/routes_pages.py`：通过。
- `uv run pytest tests/knowledge_query/test_api.py tests/knowledge_query/test_pages.py`：通过，`79 passed`，`1` 个既有 `StarletteDeprecationWarning`。
- `pnpm --filter medical-audit-web test -- src/lib/api-client.test.ts 'src/app/(workspace)/workspace-pages.test.tsx'`：通过，`2` 个 test files、`57` 个 tests。
- `pnpm --filter medical-audit-web typecheck`：通过。
- `pnpm --filter medical-audit-web lint`：通过。
- `pnpm --filter medical-audit-web build`：通过，静态页面 `21/21`。
- `git diff --check`：通过。

2026-06-22 Batch 7.4 增量验证：

- `/agents/{agent_key}/prompt-versions` 已新增 `review_note` 入参；新建提示词版本默认进入 `pending-review` 审核状态。
- `/agents/{agent_key}/prompt-versions/review` 已新增提示词版本审核接口，支持 `pending-review`、`approved` 和 `changes-requested`，并记录 `agent-prompt-version-review` 操作日志。
- `/agents` 响应中的 `prompt_versions` 已返回审核状态、审核意见、申请人、审核人和审核时间等字段。
- Next `/agents` 已展示当前提示词审核状态、版本列表审核标签、审核意见输入、`审批通过` / `要求修改` 按钮，以及上一版与当前版的逐行对照表。
- `uv run ruff check src/medical_audit_kb/api/agent_store.py src/medical_audit_kb/api/routes_agents.py tests/knowledge_query/test_api.py`：通过。
- `uv run mypy src/medical_audit_kb/api/agent_store.py src/medical_audit_kb/api/routes_agents.py`：通过。
- `uv run pytest tests/knowledge_query/test_api.py -k "agents_api"`：通过，`5 passed`，`40 deselected`，`1` 个既有 `StarletteDeprecationWarning`。
- `pnpm --filter medical-audit-web test -- src/lib/api-client.test.ts 'src/app/(workspace)/workspace-pages.test.tsx'`：通过，`2` 个 test files、`58` 个 tests。
- `pnpm --filter medical-audit-web typecheck`：通过。
- `pnpm --filter medical-audit-web lint`：通过。
- `pnpm --filter medical-audit-web build`：通过，静态页面 `21/21`。
- `uv run python scripts/run-local-fullstack-e2e.py`：通过，`16 passed`，使用临时 in-memory FastAPI 后端和 fake provider。
- `git diff --check`：通过。

2026-06-22 Batch 7.5 增量验证：

- 新建提示词版本后只保存为候选版本，`review_status=pending-review`，不再覆盖当前 active prompt 或 `prompt_version_key`。
- `/agents/{agent_key}/prompt-versions/review` 仅在 `approved` 时激活对应版本；`changes-requested` 只记录审核意见，不改变 active version。
- `prompt_versions` 已返回 `is_active`；Next `/agents` 已展示 `待审版本`、`当前激活`、`审核对象：vN`，并将对比对象切换为“当前激活 vs 待审版本”。
- 智能体调用登记继续使用当前 active `prompt_version_key`；审批通过后才切换到新版本 key。
- `/agents` 持久化 store 不可用时的默认智能体 fallback 已补齐 `prompt_versions` 和 `is_active`。
- `uv run ruff check src/medical_audit_kb/api/agent_store.py src/medical_audit_kb/api/routes_agents.py tests/knowledge_query/test_api.py`：通过。
- `uv run pytest tests/knowledge_query/test_api.py -k "agents_api_tracks_prompt_versions_lifecycle_and_history"`：通过，`1 passed`，`44 deselected`，`1` 个既有 `StarletteDeprecationWarning`。
- `uv run pytest tests/knowledge_query`：通过，`285 passed`，`1` 个既有 `StarletteDeprecationWarning`。
- `uv run mypy src`：通过，`88` 个源码文件。
- `pnpm --filter medical-audit-web typecheck`：通过。
- `pnpm --filter medical-audit-web lint`：通过。
- `pnpm --filter medical-audit-web test`：通过，`11` 个 test files、`90` 个 tests。
- `pnpm --filter medical-audit-web build`：通过，静态页面 `21/21`。
- `uv run python scripts/run-local-fullstack-e2e.py`：通过，`16 passed`，使用临时 in-memory FastAPI 后端和 fake provider。

2026-06-22 Batch 7.6 增量验证：

- `/agents/{agent_key}/prompt-versions/review` 和 `/agents/{agent_key}/prompt-versions/rollback` 已收口到 `admin` / `director`；`technician` 可保存候选提示词版本，但不能审批或回滚激活。
- 被拒绝的提示词审核/回滚激活请求会记录 `authorization-denied`，并保留原始 `attempted_action`。
- Next `/agents` 已把候选版本保存和审批/回滚激活控件拆开，技术人员视图不会触发激活 API。
- `uv run ruff check src/medical_audit_kb/api/routes_agents.py tests/knowledge_query/test_api.py`：通过。
- `uv run pytest tests/knowledge_query/test_api.py -k 'agents_api_restricts_prompt_activation_to_admin_and_director or agents_api_tracks_prompt_versions_lifecycle_and_history'`：通过，`2 passed`，`45 deselected`，`1` 个既有 `StarletteDeprecationWarning`。
- `pnpm --filter medical-audit-web test -- workspace-pages.test.tsx -t 'prompt activation controls'`：通过，`1 passed`，`27 skipped`。
- `uv run ruff check .`：通过。
- `uv run mypy src`：通过，`88` 个 source files。
- `uv run pytest tests/knowledge_query`：通过，`286 passed`，`1` 个既有 `StarletteDeprecationWarning`。
- `pnpm --filter medical-audit-web typecheck`：通过。
- `pnpm --filter medical-audit-web lint`：通过。
- `pnpm --filter medical-audit-web test`：通过，`11` 个 test files、`91` 个 tests。
- `pnpm --filter medical-audit-web build`：通过，静态页面 `21/21`。
- `uv run python scripts/run-local-fullstack-e2e.py`：通过，`16 passed`，使用临时 in-memory FastAPI 后端和 fake provider。
- `git diff --check`：通过。

2026-06-22 Batch 7.7 增量验证：

- 持久化用户角色解析已支持 `scope_type=project` + `scope_key=<project_key>`；`/auth/session` 带 `X-Project-Key` 时会返回匹配项目的 `persistent_project_role`。
- `/auth/session` 已返回 `auth_scope_type` / `auth_scope_key`，Next 顶部栏可展示后端 session 生效角色。
- `/projects/{project_key}/members` 新增成员写入口已按路径 `project_key` 执行权限解析；项目 scoped `admin` 只在对应项目获得成员管理权限，跨项目返回 `403` 并记录拒绝日志。
- Next `fetchAuthSession()` 和 `createProjectMember(projectId, ...)` 已携带 `X-Project-Key`。
- `uv run ruff check src/medical_audit_kb/api/auth.py src/medical_audit_kb/api/routes_auth.py src/medical_audit_kb/api/routes_projects.py tests/knowledge_query/test_api.py`：通过。
- `uv run pytest tests/knowledge_query/test_api.py -k 'permission_resolver_uses_project_scoped_role or permission_resolver_prefers_persisted_global_role or auth_api_updates_user_status'`：通过，`3 passed`，`45 deselected`，`1` 个既有 `StarletteDeprecationWarning`。
- `uv run mypy src/medical_audit_kb/api/auth.py src/medical_audit_kb/api/routes_auth.py src/medical_audit_kb/api/routes_projects.py`：通过。
- `pnpm --filter medical-audit-web test -- src/lib/api-client.test.ts src/components/shell/workspace-shell.test.tsx`：通过，`2` 个 test files、`36` 个 tests。
- `pnpm --filter medical-audit-web typecheck`：通过。
- `uv run ruff check .`：通过。
- `uv run mypy src`：通过，`88` 个 source files。
- `uv run pytest tests/knowledge_query`：通过，`287 passed`，`1` 个既有 `StarletteDeprecationWarning`。
- `pnpm --filter medical-audit-web lint`：通过。
- `pnpm --filter medical-audit-web typecheck`：通过。
- `pnpm --filter medical-audit-web test`：通过，`11` 个 test files、`91` 个 tests。
- `pnpm --filter medical-audit-web build`：通过，静态页面 `21/21`。
- `uv run python scripts/run-local-fullstack-e2e.py`：通过，`16 passed`，使用临时 in-memory FastAPI 后端和 fake provider。

2026-06-22 Batch 7.8 增量验证：

- FastAPI 已新增可开关的受控 API 鉴权中间件；`create_app(..., enforce_controlled_api_auth=True)` 或 `MEDICAL_AUDIT_CONTROLLED_API_AUTH=enforce` 可启用本地强制模式。
- 受控 API 裸请求会返回 `401/403` 并写入 `authorization-denied`；停用持久化用户即使带 `admin` header 也会被中间件拒绝。
- 本地 `pnpm local:fullstack:e2e` 的内存态后端已在强制鉴权模式启动，用于验证 Next 工作区 API 是否漏带角色头。
- Next API client 已让查询历史、疑点、报告、图谱、规则、整改、归档、分析历史、项目列表和项目成员读取统一携带审计角色头，项目读取携带 `X-Project-Key`。
- `uv run ruff check src/medical_audit_kb/api/app.py tests/knowledge_query/test_api.py scripts/run-local-fullstack-e2e.py`：通过。
- `uv run pytest tests/knowledge_query/test_api.py -k 'controlled_api_auth_middleware or permission_resolver_uses_project_scoped_role or auth_api_rejects_member_user_management'`：通过，`3 passed`，`46 deselected`，`1` 个既有 `StarletteDeprecationWarning`。
- `pnpm --filter medical-audit-web test -- src/lib/api-client.test.ts`：通过，`31` 个 tests。
- `uv run mypy src/medical_audit_kb/api/app.py src/medical_audit_kb/api/auth.py`：通过。
- `pnpm --filter medical-audit-web typecheck`：通过。
- `pnpm local:fullstack:e2e`：通过，`16 passed`，后端以强制受控 API 鉴权模式启动。
- `uv run ruff check .`：通过。
- `uv run mypy src`：通过，`88` 个 source files。
- `uv run pytest tests/knowledge_query`：通过，`288 passed`，`1` 个既有 `StarletteDeprecationWarning`。
- `pnpm --filter medical-audit-web lint`：通过。
- `pnpm --filter medical-audit-web test`：通过，`11` 个 test files、`91` 个 tests。
- `pnpm --filter medical-audit-web build`：通过，静态页面 `21/21`。

2026-06-22 Batch 7.9 增量验证：

- FastAPI 受控 API 鉴权中间件强制模式已要求 `X-Tenant-Id`；未带租户头的受控 API 会返回 `401`，并记录 `authorization-denied`，payload 保留 `tenant_id=None` 和拒绝原因。
- `/auth/session` 已接受 `X-Tenant-Id` 并在响应中返回 `tenant_id`。
- Next `auditClientHeaders()` 已默认发送 `X-Tenant-Id: hospital-demo`；工作区 API、项目 API 和 `/auth/session` 请求均继承该本地租户头契约。
- `uv run ruff check src/medical_audit_kb/api/app.py src/medical_audit_kb/api/auth.py src/medical_audit_kb/api/routes_auth.py tests/knowledge_query/test_api.py scripts/run-local-fullstack-e2e.py`：通过。
- `uv run pytest tests/knowledge_query/test_api.py -k 'controlled_api_auth_middleware or auth_api_lists_roles_and_manages_users or permission_resolver_uses_project_scoped_role'`：通过，`3 passed`，`46 deselected`，`1` 个既有 `StarletteDeprecationWarning`。
- `pnpm --filter medical-audit-web test -- src/lib/api-client.test.ts`：通过，`31` 个 tests。
- `uv run ruff check .`：通过。
- `uv run mypy src`：通过，`88` 个 source files。
- `uv run pytest tests/knowledge_query`：通过，`288 passed`，`1` 个既有 `StarletteDeprecationWarning`。
- `pnpm --filter medical-audit-web lint`：通过。
- `pnpm --filter medical-audit-web typecheck`：通过。
- `pnpm --filter medical-audit-web test`：通过，`11` 个 test files、`91` 个 tests。
- `pnpm --filter medical-audit-web build`：通过，静态页面 `21/21`。
- `pnpm local:fullstack:e2e`：通过，`16 passed`，后端以强制受控 API 鉴权模式启动。

2026-06-22 Batch 8.1 增量验证：

- 新增 `scripts/run-controlled-api-readonly-permission-smoke.py`，只发 `GET` 请求，用于只读检查受控 API 的匿名请求、缺租户头请求和管理员带齐请求。
- 新增 `pnpm local:permission:readonly`，默认面向本地 `http://127.0.0.1:8021` 严格断言受控 API 权限门禁。
- 新增 `pnpm production:permission-readonly`，默认面向 `https://audit.lute-tlz-dddd.top/api/v1` 做 `observe` 模式只读观测并写报告；该命令不做生产写入、不调用 provider，也不把观测结果自动写成生产验收通过。
- `uv run ruff check scripts/run-controlled-api-readonly-permission-smoke.py tests/knowledge_query/test_scripts.py`：通过。
- `uv run pytest tests/knowledge_query/test_scripts.py -k 'controlled_api_readonly_permission'`：通过，`4 passed`，`23 deselected`。
- `python3 -m py_compile scripts/run-controlled-api-readonly-permission-smoke.py`：通过。
- `uv run pytest tests/knowledge_query/test_scripts.py`：通过，`27 passed`。
- `uv run pytest tests/knowledge_query`：通过，`292 passed`，`1` 个既有 `StarletteDeprecationWarning`。
- `uv run mypy src`：通过，`88` 个 source files。
- `git diff --check`：通过。
- 边界：`production_side_effect=none`，`provider_call_status=not_called`，`production_readonly_status=not_run`。

2026-06-23 Batch 8.2 增量验证：

- 执行 `pnpm production:permission-readonly`，报告写入 `tmp/outputs/production-permission-readonly-smoke-latest.json`。
- 报告 `status=fail`，`probe_count=35`，`issue_count=1`，`observation_count=28`。
- 报告边界为 `production_side_effect=none`、`provider_call_status=not_called`、`http_methods=["GET"]`。
- `/api/v1/health` 返回 `200`；`/api/v1/auth/roles` 返回 `404`，`/api/v1/auth/session` 三类探针均为 `404`。
- 已存在的 `/api/v1/projects`、`/api/v1/agents`、`/api/v1/query/logs?limit=1`、`/api/v1/audit-findings` 和 `/api/v1/analytics/table-uploads` 等读接口未强制拒绝缺 `X-Tenant-Id` 请求。
- `/api/v1/graph/workbench`、`/api/v1/rules/workbench`、`/api/v1/remediation/workbench`、`/api/v1/archive/workbench` 和 `/api/v1/reports/workbench` 返回 `404`。
- 边界：本批没有生产部署、没有生产写入型 E2E、没有 provider 调用；结论是生产权限只读 smoke 未通过。

2026-06-23 Batch 8.3 增量验证：

- 执行生产部署状态只读巡检，首轮旧预期值报告 `tmp/outputs/tencent-cloud-deployment-state-20260623-readonly.json` 返回 `status=fail`，阻断项为 `deploy-sha-mismatch` 和 `search-backend-not-ready`。
- 使用生产实际 SHA `550a445012267ba1211f5881b1d441264f3a3056` 和实际 `matching_embedding_count=49051` 复核后，报告 `tmp/outputs/tencent-cloud-deployment-state-20260623-readonly-current.json` 返回 `status=pass`，`issues=[]`。
- 复核确认 `medical_audit_app` 和 `medical_audit_pg` 均为 running/healthy，`nginx_config_test=True`，`audit_mount_present=True`，生产检索后端 `backend=postgres` 且 `ready=true`。
- 本地当前 `HEAD=b298c6c8b416b4863c948ff5c7d0cbfc5881ebab`，所在分支远端已 `[gone]`，工作树包含大量 tracked 修改和 untracked 文件。
- 结论：生产当前健康，但当前本地工作树不是可直接部署的 release candidate；下一批必须先创建干净 release 分支或 worktree，并用 manifest 精确移植待发布能力。
- 边界：本批没有生产部署、没有生产写入型 E2E、没有 provider 调用；Batch 8.2 的 `production_permission_smoke_status=fail` 仍然有效。

## 3. 当前完整性矩阵

| 模块 | 前端状态 | 后端状态 | 联调状态 | 完整性判断 |
| --- | --- | --- | --- | --- |
| 门户壳层、登录页、导航 | 已完成本地 UI 重构，浅蓝医院内审工作台风格已落地 | 依赖 Next 静态页面和 rewrites | E2E 覆盖 `/login` 外主要工作区路由，当前通过 | 高 |
| AI 对话 | Next 原生入口已完成问题构建、智能体选择、知识来源限定 | `/query`、`/pages/chat`、引用回答、原文预览基础存在；`/query` 已使用持久化用户优先解析 | 本轮用内存态检索验证 `/query`；生产 provider 未验证 | 中高 |
| 智能体广场和我的智能体 | 模板广场、模板预填、智能体新增表单已完成；`/agents` 已支持版本对比、逐行 diff、新版本保存、审核状态、审批通过才激活、审批/回滚激活角色分离、试用登记、效果反馈、反馈统计、下架和软归档；`/chat` 已优先读取角色过滤后的 active 智能体，并能把选中智能体提交到后端深页 | `/agents` GET/POST 已扩展提示词版本、版本审核状态、审核激活门禁、`admin/director` 激活角色门禁、可见范围、生命周期、单体追溯、版本新增、回滚、调用记录、反馈统计和项目范围校验；`/query` 与 `/pages/chat` 已自动写入智能体调用记录 | API 单测、api-client 单测、页面单测、本地 fullstack E2E 已覆盖；生产部署、正式租户 scope 和生产权限验收待补 | 中高 |
| 文档检索 | 检索首页、来源过滤、搜索历史、个人材料入口已完成 | `/query`、`/query/logs`、`/documents/permissions`、`/documents/uploads` 已存在；文档权限和上传列表已使用持久化用户优先解析 | E2E 覆盖实际查询；个人材料入索引、DLP 和对象存储待补 | 中高 |
| AI 数据分析 | 三张医保费用模板入口、上传分析和历史记录 UI 已完成 | `/analytics/table-upload`、`/analytics/table-uploads` 已存在 | E2E 覆盖 CSV 上传解析；正式工作簿治理和安全扫描待补 | 中高 |
| 审计底稿生成 | 报告页和三类提示词模板已完成 API-first 模板 registry 和 Word 下载入口 | `/pages/chat/export`、复核任务记录、报告草稿、已签发报告均支持 JSON/Markdown/Word docx；`/reports/workbench` 已聚合模板、报告记录和下载链接；签发正文仍冻结 Markdown `sha256` | 本地 API 测试已打开 docx 包校验 `word/document.xml`；Next 报告页单测覆盖 API-first 下载入口；生产验收和电子签章待补 | 中高 |
| 疑点工作台 | Next `/findings` 已 API-first 读取疑点列表 | `/audit-findings` 与疑点 store readiness 已存在 | 单元和 E2E 覆盖可达性；规则执行生成到疑点闭环待扩展 | 中 |
| 项目管理和角色 | 医院四类角色矩阵和成员新增入口已完成；顶部栏已展示后端 session 生效角色 | `/projects`、`/projects/{project_key}/members` 已存在；项目 scoped role assignment 已在成员新增写入口本地生效 | E2E 覆盖成员新增；项目 scoped admin 本地 API 测试已覆盖，真实邀请和 SSO 会话待补 | 中高 |
| 知识库 | 个人、系统、公开知识库展示已完成 | 索引管理深页和 index API 已存在 | 以只读展示为主；知识库管理 API 化待补 | 中 |
| 知识图谱 | Next `/graph` 已后端优先读取图谱 workbench，API 不可用时保留静态兜底 | `/graph/workbench` 已返回项目、知识库、文档、规则、疑点、复核、报告、整改关系和指标 | API 单测、api-client 单测和页面单测已覆盖；生产图谱数据源和动态写入未验证 | 中 |
| 专题规则库 | Next `/rules` 已后端优先读取规则 workbench，API 不可用时保留静态兜底 | `/rules/workbench` 已返回规则清单、来源覆盖、运行快照、发布门禁和指标 | API 单测、api-client 单测和页面单测已覆盖；真实规则运行和疑点生成写入未执行 | 中 |
| 补证整改 | Next `/remediation` 已后端优先读取整改 workbench，API 不可用时保留静态兜底 | `/remediation/workbench` 已返回整改台账、补证请求、关闭门禁、整改动态和指标；旧 review-task rectification 写入口仍保留在后端深页 | API 单测、api-client 单测和页面单测已覆盖；真实补证提交、验收意见和关闭写入未接入 Next | 中 |
| 项目档案和审计日志 | Next `/archive` 已后端优先读取归档 workbench，API 不可用时保留静态兜底；归档包、签名链和治理策略展示已完成 | `/archive/workbench` 已返回档案包、归档巡检、签名链、治理策略、入档动态和指标；`/audit/logs`、`/audit/logs/export`、review-task exports 仍保留 | API 单测、api-client 单测、页面单测和本地 E2E 已覆盖；真实归档写入、签名 manifest 生成和恢复演练仍未执行 | 中 |
| 认证和权限 | 顶部角色视图、角色上下文和项目成员角色映射已完成 UI，顶栏已读取 `/auth/session` 并展示后端生效角色和本地 `tenant_id`；智能体审批/回滚激活控件已按 `admin/director` 分支禁用；工作区 API client 已统一携带审计角色头、项目 key 和本地租户头 | 已有医院四类角色权限矩阵、`auth_departments`、`auth_users`、`auth_user_role_assignments` 和 `/auth/*` 过渡层 API；`/query`、`/documents`、`/audit/logs` 核心路由已接入持久化用户优先解析；项目 scoped role assignment 已在 `/auth/session` 和项目成员写入口生效；受控 API 鉴权中间件本地强制模式已通过，并要求 `X-Tenant-Id`；只读权限 smoke 脚本已准备；智能体提示词激活已限制为管理员/主任 | 本地 API、前端单测、强制鉴权 fullstack E2E 和脚本契约测试通过；生产只读权限 smoke 已执行但失败，生产 `/auth/*` 和多项 workbench API 尚未部署，既有读接口未强制租户头；真实登录会话、正式租户身份来源、医院 SSO 和生产权限验收仍未闭合 | 中高 |

## 4. 主要缺口

P0 缺口：

- 本机默认 PostgreSQL 联调环境未就绪，完整本地 E2E 目前依赖一次性内存态 FastAPI 服务。
- 真实医院 SSO、登录会话签发、正式租户身份来源和生产权限验收未闭合；当前账号/角色/租户能力是 header 过渡层和本地权限底座，核心 `/query`、`/documents`、`/audit/logs` 路由已完成本地持久化用户优先解析，项目级角色授权已在 `/auth/session` 和项目成员写入口本地生效，受控 API 鉴权中间件已在本地强制模式通过并要求 `X-Tenant-Id`；生产只读权限 smoke 已执行但失败，生产当前仍是旧权限/路由状态。
- Word/docx 底稿导出、模板 registry 和 Next `/reports` API-first 下载入口已完成本地能力；生产验收、电子签章和证书级正式报告仍未完成。
- 文档上传已完成本地 `local-policy` 策略扫描、DLP 标记和受控下载隔离；文档和表格上传仍缺外部杀毒/DLP 服务、脱敏改写、对象存储和生命周期治理。
- 个人材料已完成本地留存、角色读取隔离、本地策略扫描、治理准入和本地文本入索引；真实异步向量索引、外部 DLP/杀毒和对象存储待补。

P1 缺口：

- 图谱、规则、整改和归档页已完成本地只读 API 化，但仍是本地 seed，不代表生产图谱数据源、真实规则运行、授权整改写入、归档签名生成或生产恢复演练。
- 智能体已完成本地提示词版本、下架/恢复底座、角色过滤、普通成员发布限制、调用记录、效果反馈、反馈统计、版本 diff UI、逐行 diff、审核状态记录、审批通过才激活、管理员/主任激活角色门禁、真实对话挂接、项目范围校验和本地租户头契约首切片；生产部署验收、正式租户 scope 和完整删除/归档治理待补。
- 项目成员缺邀请审批、禁用/移除和真实权限联动。
- 文档检索 `title_only` 已接入后端查询参数和标题/路径元数据过滤；真实生产专项验收仍待执行。
- 生产搜索历史列表/回填专项验收待补。

P2 缺口：

- 生产级 provider answer generation 未完成验收，当前可证明的是 fallback citation answer 和 embedding 检索基础。
- 证书级电子签章、长期留存介质、归档恢复演练和外部告警端点仍需方案化。
- UI 产品原型已覆盖第一阶段核心功能，但医院现场操作手册、角色培训和灰度配置待补。

## 5. 分批执行计划

### Batch 0：当前盘点与本地联调基线

状态：`completed`

已完成：

- 前后端代码面和测试面盘点。
- 本地静态质量闸和单元测试。
- 一次性内存态 FastAPI 联调服务。
- Playwright E2E 断言校准并通过 `16 passed`。

验收闸：

- 前端 lint/typecheck/unit/build 通过。
- 后端 ruff/mypy/pytest 通过。
- Next + FastAPI 本地联调 E2E 通过。
- 明确 `production_side_effect=none` 和 `provider_call_status=not_called`。

### Batch 1：可重复本地全栈联调环境

状态：`completed`

目标：

- 把本轮一次性内存态 FastAPI 服务固化为可重复的本地 smoke harness。
- 支持 `pnpm --dir web e2e` 前自动启动测试态 FastAPI，或提供单独 `scripts/run-local-fullstack-smoke`。
- 给出两套模式：`in_memory_fake_provider` 和 `local_postgres_readonly`。

开发项：

- 新增本地 smoke harness，禁止读取生产凭据。已完成：`scripts/run-local-fullstack-e2e.py`。
- 明确测试态数据、测试态上传目录和清理策略。已完成：默认 `in-memory` 模式使用临时目录，退出后清理。
- 补充文档：如何运行、证据等级、不能代表什么。已完成：本节作为当前运行入口。
- 新增根命令：`pnpm local:fullstack:e2e`。
- 新增本地 PostgreSQL 只读探测入口：`pnpm local:postgres:readonly`。

验收闸：

- 一条命令可完成 Next + FastAPI E2E。
- 默认模式不依赖外部 provider、不依赖生产数据库。
- 可选 PostgreSQL 模式必须先通过只读健康检查。

运行方式：

```bash
pnpm local:fullstack:e2e
```

该命令启动内存态 FastAPI、fake embedding provider 和临时上传目录，然后运行 `web` 的 Playwright E2E。证据等级是 `L1/L2-local-fullstack-smoke`，可证明 Next rewrites 与核心 API 契约可跑通，不能证明真实 PostgreSQL、真实医院数据或生产索引。

```bash
pnpm local:postgres:readonly
```

该命令按 `configs/knowledge-query-engine-dev.yaml` 或 `MEDICAL_AUDIT_KB_CONFIG` 启动配置态 FastAPI，只调用 `/health` 和 `/index/postgres-status`。它不运行 Playwright、不上传文件、不创建成员、不加载外部 embedding provider；本机 PostgreSQL 未运行时应返回 blocked 报告。

最新只读探测报告：

- `tmp/outputs/local-postgres-readonly-smoke-20260621.json`
- `status=blocked`
- `production_side_effect=none`
- `provider_call_status=not_called`
- `playwright_e2e_status=not_run_in_readonly_mode`
- `database_endpoint=localhost:5433`

### Batch 2：真实认证与权限生效

状态：`in_progress`

当前切片：`completed_controlled_api_auth_with_local_tenant_header`

目标：

- 把管理员、技术人员、主任、普通成员从 UI 展示推进到后端权限模型。
- 当前 `X-Role`、`X-User-Id`、`X-Project-Key` 和 `X-Tenant-Id` 只能作为过渡兼容层。

开发项：

- 用户、医院/科室、项目成员、角色授权模型。进度：已完成最小医院角色枚举和动作权限矩阵；已新增 `auth_departments`、`auth_users`、`auth_user_role_assignments`、`/auth/users`、`/auth/users/{user_key}`、`/auth/users/{user_key}/role-assignments` 和 `/auth/users/{user_key}/role-assignments/{assignment_key}` 过渡层 API。
- 登录会话或医院侧 SSO 适配层。进度：未完成，当前 `/auth/session` 仍是 header 过渡层；但已优先读取持久化用户的 `active/global/project` 角色授权，并在响应中返回 `auth_source/profile_status/auth_scope_type/auth_scope_key/tenant_id`。
- 前端根据真实用户权限显示/隐藏写入入口。进度：已完成本地角色上下文、顶栏角色切换、`/auth/session` 状态读取、智能体保存和项目成员新增的权限禁用。
- API 统一鉴权中间件和拒绝审计日志。进度：已完成统一鉴权辅助、持久化角色优先解析、`disabled/pending` 用户拒绝、软禁用/恢复用户、撤销/恢复角色授权和 `authorization-denied` 记录；`/query`、`/documents/permissions`、`/documents/uploads`、`/audit/logs`、`/audit/logs/export`、`/pages/audit-logs` 已接入持久化用户优先解析；受控 API 鉴权中间件本地强制模式已覆盖工作区 API，并要求 `X-Tenant-Id`。真实会话、正式 SSO claims 和生产全站权限验收未完成。
- 智能体保存、项目成员新增、索引维护三类写入口已接入权限检查。

验收闸：

- 未授权路径返回 `401/403`。当前已覆盖智能体保存、项目成员新增、索引维护、文档权限/上传、查询、审计日志 API、持久化角色覆盖 header、disabled 用户拒绝、撤销授权后的降权、受控 API 裸请求拒绝和缺少 `X-Tenant-Id` 拒绝；审计日志后端页面保持 200 但隐藏事件。
- 管理员可开设账号和分配权限。当前已覆盖项目成员新增、`/auth/users` 用户创建、`/auth/users/{user_key}` 软禁用/恢复、`/auth/users/{user_key}/role-assignments` 角色分配和 `/auth/users/{user_key}/role-assignments/{assignment_key}` 授权撤销/恢复；真实登录凭据和医院 SSO 仍未完成。
- 技术人员可维护数据/索引但不能签发底稿。当前已覆盖索引维护；底稿签发权限仍待 Batch 3/后续报告链路接入。
- 主任可复核和签发，普通成员只能审证、补证、草稿。当前已覆盖主任可保存智能体、普通成员不能保存系统智能体或新增成员；正式复核/签发权限仍未全量接入。
- 拒绝访问写入审计日志。当前已通过 `authorization-denied` 写入进程内操作日志，并在配置 `audit_log_store` 时进入持久化审计底座。

本轮验证证据：

- `uv run ruff check src/medical_audit_kb/api/auth.py src/medical_audit_kb/api/routes_agents.py src/medical_audit_kb/api/routes_projects.py src/medical_audit_kb/api/routes_index.py src/medical_audit_kb/api/document_permissions.py src/medical_audit_kb/api/audit_log_policy.py tests/knowledge_query/test_api.py`：通过。
- `uv run pytest tests/knowledge_query/test_api.py`：通过，`32 passed`。
- `uv run mypy src`：通过，`84` 个源码文件。
- `pnpm web:lint`：通过。
- `pnpm web:typecheck`：通过。
- `pnpm --dir web test -- api-client.test.ts workspace-shell.test.tsx workspace-pages.test.tsx`：通过，`44 passed`。
- `uv run pytest tests/knowledge_query/test_api.py tests/knowledge_query/test_sql_assets.py`：通过，`45 passed`，覆盖 `/auth/roles`、`/auth/session`、`/auth/users`、角色分配和 auth schema 资产。
- `uv run ruff check .`：通过。
- `uv run mypy src`：通过，`87` 个源码文件。
- `uv run pytest`：通过，`272 passed`，`1` 个既有 `StarletteDeprecationWarning`。
- `pnpm web:lint`：通过。
- `pnpm web:typecheck`：通过。
- `pnpm web:test`：通过，`73 passed`。
- `pnpm web:build`：通过，静态页面 `21/21`。
- `pnpm local:fullstack:e2e`：通过，`16 passed`。
- `uv run pytest tests/knowledge_query/test_api.py -k "auth_api or permission_resolver or agents_api_enforces or projects_api_enforces"`：通过，`6 passed`，覆盖持久化 `active/global` 角色优先、header 降权覆盖和 `disabled` 用户拒绝。
- `uv run pytest tests/knowledge_query/test_api.py -k "auth_api or permission_resolver"`：通过，`5 passed`，覆盖用户软禁用/恢复、角色授权撤销/恢复和撤销后的降权。
- `uv run ruff check src/medical_audit_kb/api/routes_documents.py src/medical_audit_kb/api/routes_query.py src/medical_audit_kb/api/routes_pages.py tests/knowledge_query/test_api.py tests/knowledge_query/test_pages.py`：通过，覆盖本切片改动文件。
- `uv run pytest tests/knowledge_query/test_api.py -k "documents or query_endpoint"`：通过，`8 passed`，覆盖文档权限持久化角色覆盖、disabled profile 拦截和查询入口状态门禁。
- `uv run pytest tests/knowledge_query/test_pages.py -k "audit_logs"`：通过，`5 passed`，覆盖审计日志 API、导出和页面持久化角色覆盖。

证据边界：

- `validation_scope=local_unit_typecheck_build_and_fullstack_smoke`
- `production_side_effect=none`
- `provider_call_status=not_called`
- `auth_status=header_transition_layer`
- `sso_status=not_implemented`
- `auth_persistence_status=local_schema_and_store_ready`
- `auth_session_status=header_transition_with_persistent_role_resolution_no_token_issued`
- `disabled_user_gate_status=implemented_for_protected_api_helper`
- `auth_user_management_status=soft_disable_and_role_revoke_api_ready`
- `auth_route_coverage_status=controlled_api_auth_with_local_tenant_header_ready`

### Batch 3：审计底稿 Word/docx 生成

状态：`completed_local_docx_export_slice`

当前切片：`completed_chat_review_task_report_docx_exports`

目标：

- 把提示词模板、引用、疑点、复核意见和模板字段组织成正式 Word/docx 草稿。

开发项：

- 底稿模板 registry，覆盖三张医保费用模板。进度：已完成本地 API registry；`/reports/workpaper-templates` 返回三张模板字段、核验重点、证据绑定和提示词入口。
- Word/docx 生成服务和下载接口。进度：已新增标准库 docx 生成器；`/pages/chat/export`、`/review-tasks/{task_id}/export`、`/review-tasks/{task_id}/report-draft`、`/review-tasks/{task_id}/signed-report` 支持 `format=docx`。
- 引用不足、未复核、未确认时阻断正式导出。进度：沿用既有引用查询、报告门禁和签发冻结逻辑；报告草稿未过门禁返回 `409`，未签发正式报告返回 `409`。
- 前端报告页接入 API-first 生成和下载状态。进度：已完成本地切片；Next `/reports` 优先读取 `/reports/workbench`，展示任务 Word、报告 Word 和模板 registry，后端无任务或异常时保留样例兜底。

验收闸：

- 生成文件可打开，包含引用、复核任务、底稿编号、报告草稿和已签发报告正文。当前通过测试打开 `.docx` ZIP 包并校验 `word/document.xml`。
- 无引用或未复核时只能生成草稿，不允许正式签发。当前沿用既有 `404/409` 门禁。
- 单元、API、E2E 覆盖生成、下载和门禁。当前完成 API 级回归和 Next 页面 API-first 下载入口测试；真实浏览器只验证入口可见，不执行二进制下载验签。

本轮验证证据：

- `uv run ruff check src/medical_audit_kb/api/docx_export.py src/medical_audit_kb/api/routes_pages.py tests/knowledge_query/test_pages.py`：通过。
- `uv run mypy src`：通过，`87` 个源码文件。
- `uv run pytest tests/knowledge_query/test_pages.py -k "docx or review_task_create_update_and_export_flow or chat_dossier_export"`：通过，`5 passed`，覆盖对话底稿 docx、复核任务 docx、报告草稿 docx 和已签发报告 docx。
- `uv run pytest`：通过，`272 passed`，`1` 个既有 `StarletteDeprecationWarning`。
- `uv run pytest tests/knowledge_query/test_pages.py -k "report_workpaper_template_registry or review_task_create_update_and_export_flow"`：通过，`2 passed`，覆盖模板 registry、报告 workbench 和 Word 下载链接聚合。
- `pnpm --filter medical-audit-web test -- src/lib/api-client.test.ts src/app/'(workspace)'/workspace-pages.test.tsx`：通过，`41 passed`，覆盖 `/api/v1/reports/workbench` client 和 Next `/reports` API-first 下载入口。

证据边界：

- `validation_scope=local_api_unit_typecheck`
- `production_side_effect=none`
- `provider_call_status=not_called`
- `docx_generation_status=stdlib_docx_package_generated_from_existing_markdown`
- `signed_report_hash_scope=frozen_markdown_content_sha256_not_docx_binary`
- `report_workbench_status=local_api_first_next_ready_with_sample_fallback`

### Batch 4：报告页 API-first 下载与模板 registry

状态：`completed_local_report_workbench_slice`

当前切片：`completed_template_registry_and_next_report_download_links`

目标：

- 把报告页从纯静态展示推进为 API-first 报告工作台，承接后端 docx 导出链路。

开发项：

- `/reports/workpaper-templates` 模板 registry。进度：已完成，覆盖三张医保费用模板的字段、核验重点、证据绑定和提示词入口。
- `/reports/workbench` 报告工作台聚合接口。进度：已完成，返回模板 registry、复核任务报告记录、证据来源、统计和 Word 下载链接。
- Next `/reports` API-first 下载入口。进度：已完成，页面优先读取 `/api/v1/reports/workbench`，展示任务 Word 和报告 Word；无任务或后端异常时保留样例兜底。

验收闸：

- 模板 registry 必须覆盖三张用户提供的医保费用模板。
- 过门禁或已签发任务必须能在报告页看到报告 Word 下载入口。
- 未过门禁任务不得提供报告 Word 下载入口，只能提供任务记录 Word。

本轮验证证据：

- `uv run ruff check src/medical_audit_kb/api/routes_pages.py tests/knowledge_query/test_pages.py`：通过。
- `uv run pytest tests/knowledge_query/test_pages.py -k "report_workpaper_template_registry or review_task_create_update_and_export_flow"`：通过，`2 passed`。
- `pnpm web:typecheck`：通过。
- `pnpm --filter medical-audit-web test -- src/lib/api-client.test.ts src/app/'(workspace)'/workspace-pages.test.tsx`：通过，`41 passed`。
- `pnpm local:fullstack:e2e`：通过，`16 passed`，覆盖 `/reports` 模板源文件和 registry 状态可见。

证据边界：

- `validation_scope=local_api_next_unit`
- `production_side_effect=none`
- `provider_call_status=not_called`
- `report_download_status=api_first_links_ready_no_browser_binary_download_assertion`
- `sample_fallback_status=enabled_when_backend_empty_or_unavailable`

### Batch 5：文档检索和个人材料治理

目标：

- 补齐个人材料入索引、后端 `title_only`、搜索历史专项验收和材料治理。

开发项：

- 后端查询支持 `title_only` 或明确替代筛选参数。进度：已完成本地 `/query` 参数、日志和标题/路径元数据过滤。
- 个人上传材料进入索引的异步任务和状态机。进度：已完成本地治理状态机、`index-ready/blocked/not-indexed` 标记、`personal_index_status` 本地入索引任务和按权限查询补充命中；真实后台队列和向量索引写入待补。
- 病毒扫描、DLP/脱敏标记、下载权限隔离。进度：已完成本地 `local-policy` 策略扫描、DLP 标记、准入索引阻断和本人/读全部权限下载隔离；外部杀毒/DLP 服务、脱敏改写和对象存储待补。
- 搜索历史列表/回填生产专项验收脚本。

验收闸：

- 普通成员只能读自己的个人材料。
- 管理员和授权主任可读项目范围材料。
- 高风险文件被阻断并留痕。
- 个人材料入索引后可按权限检索。进度：已完成本地文本索引检索，`/query` 返回独立 `personal_upload_matches`，不混入法规引用证据链。

### Batch 6：规则、图谱、整改、归档 API 化

状态：`in_progress`

当前切片：`completed_graph_rules_remediation_archive_workbench_readonly_api_first`

目标：

- 把当前静态门户视图逐步替换为后端真实状态。

开发项：

- 图谱 API：项目、知识库、文档、规则、疑点、复核、报告、整改关系。进度：已完成本地只读 `/graph/workbench`，Next `/graph` 优先读取 `/api/v1/graph/workbench`，失败时保留静态兜底并显示“本地样例兜底”。
- 规则运行 API：规则版本、执行任务、疑点生成、运行历史。进度：已完成本地只读 `/rules/workbench`，Next `/rules` 优先读取 `/api/v1/rules/workbench`，失败时保留静态兜底并显示“本地样例兜底”；真实规则执行和疑点写入未启用。
- 整改 API：补证请求、提交材料、验收意见、关闭门禁。进度：已完成本地只读 `/remediation/workbench`，Next `/remediation` 优先读取 `/api/v1/remediation/workbench`，失败时保留静态兜底并显示“本地样例兜底”；真实补证提交、验收意见、关闭写入仍沿用旧后端深页能力，未接入 Next 工作台。
- 归档 API：归档包、签名 manifest、审计日志导出和恢复演练记录。进度：已完成本地只读 `/archive/workbench`，Next `/archive` 优先读取 `/api/v1/archive/workbench`，失败时保留静态兜底并显示“本地样例兜底”；真实归档写入、签名 manifest 生成和恢复演练未执行。

验收闸：

- 页面刷新后状态来自后端。
- 写入动作都有审计日志。
- 规则命中到疑点、疑点到复核、复核到整改、整改到归档链路可追踪。

Batch 6.1 验收结果：

- 已满足：图谱页面刷新后优先来自后端 `/graph/workbench`，同时保留无后端时的静态兜底。
- 已满足：只读 API 会写入本地 `operation_logs` 的 `graph-workbench-view` 记录。
- 未满足：规则运行、整改写入、归档 manifest 和恢复演练仍未 API-first。
- 边界：`production_side_effect=none`，`provider_call_status=not_called`，`graph_workbench_status=local_readonly_seed_api_first`。

Batch 6.2 验收结果：

- 已满足：规则页面刷新后优先来自后端 `/rules/workbench`，同时保留无后端时的静态兜底。
- 已满足：只读 API 会写入本地 `operation_logs` 的 `rules-workbench-view` 记录。
- 已满足：前端页面单测覆盖 rules workbench API 调用、后端连接状态和 API 失败兜底。
- 未满足：真实规则执行、疑点生成写入、规则版本治理和批量运行审计日志仍未闭合。
- 边界：`production_side_effect=none`，`provider_call_status=not_called`，`rules_workbench_status=local_readonly_seed_api_first`。

Batch 6.3 验收结果：

- 已满足：整改页面刷新后优先来自后端 `/remediation/workbench`，同时保留无后端时的静态兜底。
- 已满足：只读 API 会写入本地 `operation_logs` 的 `remediation-workbench-view` 记录。
- 已满足：前端页面单测覆盖 remediation workbench API 调用、后端连接状态和 API 失败兜底。
- 未满足：真实补证提交、整改验收意见、关闭门禁写入和归档联动仍未接入 Next 工作台。
- 边界：`production_side_effect=none`，`provider_call_status=not_called`，`remediation_workbench_status=local_readonly_seed_api_first`。

Batch 6.4 验收结果：

- 已满足：项目档案页面刷新后优先来自后端 `/archive/workbench`，同时保留无后端时的静态兜底。
- 已满足：只读 API 会写入本地 `operation_logs` 的 `archive-workbench-view` 记录。
- 已满足：前端页面单测覆盖 archive workbench API 调用、后端连接状态和 API 失败兜底。
- 已满足：本地全栈 E2E 覆盖 `/archive` 的档案包、归档巡检和签名链可见性。
- 未满足：真实归档写入、签名 manifest 生成、恢复演练和外部告警端点仍未执行。
- 边界：`production_side_effect=none`，`provider_call_status=not_called`，`archive_workbench_status=local_readonly_seed_api_first`。

### Batch 7：智能体治理

状态：`in_progress`

当前切片：`completed_agent_prompt_activation_role_gate`

目标：

- 从“提示词型智能体可新增”升级为可运营、可审计、可回滚。

开发项：

- 提示词版本表和版本 diff。进度：已完成本地 `audit_agent_prompt_versions`、`POST /agents/{agent_key}/prompt-versions`、`POST /agents/{agent_key}/prompt-versions/rollback`、`POST /agents/{agent_key}/prompt-versions/review`、`/agents` 版本对比 UI、逐行 diff、审核状态记录、审核意见操作、审批通过才激活门禁，以及 `admin/director` 审批/回滚激活角色门禁。
- 上下架、停用、删除软归档。进度：已完成本地 `POST /agents/{agent_key}/lifecycle`，`inactive/archived` 不进入 active 列表；`/agents` 已有下架和软归档按钮；物理删除不做。
- 按项目/角色限制智能体可见和可用范围。进度：已完成 `visibility_scope`、`allowed_roles`、`/agents` 角色过滤和 URL encoded `X-Project-Name` 项目范围校验；正式租户 scope 仍待项目身份体系进一步接入。
- 智能体调用记录和效果反馈。进度：已完成本地 `audit_agent_invocations`、`audit_agent_feedback`、对应 API、操作日志、`/agents` 登记/反馈入口、反馈统计，以及 `/query` 和 `/pages/chat` 选中智能体自动登记。

验收闸：

- 旧版本可回滚。
- 下架智能体不可被新对话选择，历史对话仍可追溯。
- 普通成员不能发布系统级智能体。
- 新版本默认待审批，管理员/主任可更新审核状态。
- 待审批或要求修改的版本不能成为当前 active prompt；审批通过后才激活。
- 技术人员可创建候选版本，但不能审批或回滚激活提示词。
- 当前版能显示逐行对照和审核状态。

Batch 7.1 验收结果：

- 已满足：旧版本可通过 `/agents/{agent_key}/prompt-versions/rollback` 回滚，回滚会生成新的当前版本并保留历史版本。
- 已满足：`inactive/archived` 自定义智能体不出现在 `GET /agents`，Next `/chat` 和 `/agents` 只吸收 active 列表；`GET /agents/{agent_key}` 仍可追溯非 active 详情。
- 已满足：普通成员调用 `/agents` 发布系统级智能体仍返回 `403`，并记录 `authorization-denied`。
- 已满足：提示词版本新增、回滚和生命周期变更分别记录 `agent-prompt-version-create`、`agent-prompt-version-rollback` 和 `agent-lifecycle-update` 操作日志。
- 截至 Batch 7.1 未满足：提示词版本 diff UI、调用记录、效果反馈、完整软归档治理和生产部署验收仍未完成；其中本地 diff/调用/反馈/软归档入口已在 Batch 7.2 补齐。
- 边界：`production_side_effect=none`，`provider_call_status=not_called`，`agent_governance_status=local_role_filtered_version_lifecycle_first_slice`。

Batch 7.2 验收结果：

- 已满足：`/agents` 工作台可显示上一版与当前版提示词对比、保存新版本并触发现有版本 API。
- 已满足：`/agents` 工作台可登记智能体试用记录并提交 `effective/needs_review/unsafe` 效果反馈。
- 已满足：调用记录和反馈分别写入 `audit_agent_invocations`、`audit_agent_feedback`，并记录 `agent-invocation-create`、`agent-feedback-create` 操作日志。
- 已满足：自定义智能体可在 UI 触发 `inactive` 下架或 `archived` 软归档；两类状态均不进入 active 新对话选择。
- 截至 Batch 7.2 未满足：真实后端深页 `/pages/chat` 自动记录调用、逐行版本 diff、反馈统计看板、项目级可见范围后端强校验和生产部署验收仍未完成；其中真实对话挂接、逐行 diff、反馈统计和项目范围校验已在 Batch 7.3/7.4 补齐本地首切片。
- 边界：`production_side_effect=none`，`provider_call_status=not_called`，`agent_governance_status=local_operability_first_slice`。

Batch 7.3 验收结果：

- 已满足：`/query` 选择智能体时会自动登记智能体调用记录并返回 `agent_invocation_id`。
- 已满足：`/pages/chat` 选择智能体时会登记 `/pages/chat` 来源调用记录；导出底稿不会重复登记调用。
- 已满足：`/agents` 按 URL encoded `X-Project-Name` 执行项目范围过滤和跨项目操作阻断。
- 已满足：`/agents/{agent_key}/feedback` 返回反馈统计 `summary`，Next `/agents` 展示三类反馈计数。
- 边界：`production_side_effect=none`，`provider_call_status=not_called`，`agent_governance_status=local_agent_invocation_project_scope_first_slice`。

Batch 7.4 验收结果：

- 已满足：新建提示词版本默认 `review_status=pending-review`，并保留 `review_note`。
- 已满足：管理员/主任可通过 `/agents/{agent_key}/prompt-versions/review` 更新 `approved` 或 `changes-requested`，并记录 `agent-prompt-version-review`。
- 已满足：Next `/agents` 展示当前审核状态、版本列表审核标签、审核意见、`审批通过` / `要求修改` 操作和逐行提示词对照。
- 未满足：审核状态尚未作为激活或对话使用的强制门禁；生产部署验收、正式租户 scope 和生产权限验收仍未完成。
- 边界：`production_side_effect=none`，`provider_call_status=not_called`，`agent_governance_status=local_prompt_review_tracking_only`。

Batch 7.5 验收结果：

- 已满足：新建提示词版本只生成待审候选，不覆盖当前 active prompt、`prompt_version` 或 `prompt_version_key`。
- 已满足：`changes-requested` 只记录审核意见，不激活版本；`approved` 才激活对应版本。
- 已满足：`prompt_versions` 返回 `is_active`，Next `/agents` 展示 `待审版本`、`当前激活` 和 `审核对象：vN`。
- 已满足：调用登记继续绑定当前 active 版本；审批通过后才切换到新版本 key。
- 未满足：生产部署验收、正式租户 scope 和生产权限验收仍未完成。
- 边界：`production_side_effect=none`，`provider_call_status=not_called`，`agent_governance_status=local_prompt_review_activation_gate_ready`。

Batch 7.6 验收结果：

- 已满足：技术人员可创建智能体和保存候选提示词版本，但调用 `/agents/{agent_key}/prompt-versions/review` 或 `/agents/{agent_key}/prompt-versions/rollback` 会返回 `403`。
- 已满足：主任可审批通过候选版本并激活 active prompt。
- 已满足：被拒绝的审核/回滚激活请求记录 `authorization-denied`，并保留 `attempted_action`。
- 已满足：Next `/agents` 技术人员视图下 `审批通过`、`要求修改` 和 `回滚到此版` 不触发激活 API。
- 未满足：生产部署验收、正式租户 scope 和生产权限验收仍未完成。
- 边界：`production_side_effect=none`，`provider_call_status=not_called`，`agent_governance_status=local_prompt_activation_role_gate_ready`。

Batch 7.7 验收结果：

- 已满足：`scope_type=project` 的持久化角色授权可在 `/auth/session` 带 `X-Project-Key` 时生效，返回 `persistent_project_role`、`auth_scope_type` 和 `auth_scope_key`。
- 已满足：`/projects/{project_key}/members` 新增成员按路径 project key 执行权限解析，项目 scoped `admin` 可管理本项目成员。
- 已满足：同一用户跨项目访问未授权项目成员写入口会返回 `403`，拒绝日志保留 `auth_scope_type=project` 和实际 `auth_scope_key`。
- 已满足：Next `/auth/session` 和项目成员新增请求均携带 `X-Project-Key`，顶部栏展示后端 session 生效角色。
- 未满足：生产部署验收、正式租户身份来源、真实医院 SSO、真实登录会话签发和生产权限验收仍未完成。
- 边界：`production_side_effect=none`，`provider_call_status=not_called`，`auth_project_scope_status=local_ready`。

Batch 7.8 验收结果：

- 已满足：受控 API 鉴权中间件可在本地强制模式启用，未带角色头的受控 API 返回 `401` 并记录 `authorization-denied`。
- 已满足：持久化停用用户即使带 `admin` header 访问受控 workbench，也会被中间件拒绝并记录拒绝原因。
- 已满足：本地 fullstack E2E 已在强制受控 API 鉴权模式运行并通过 `16 passed`，验证 Next 工作区 API 没有裸请求。
- 已满足：Next API client 的查询历史、疑点、报告、图谱、规则、整改、归档、分析历史、项目列表和项目成员读取已统一携带审计角色头，项目读取携带 `X-Project-Key`。
- 未满足：真实医院 SSO、正式登录会话签发、正式租户身份来源、网关/Nginx 注入策略、生产只读和生产写入型权限验收仍未完成。
- 边界：`production_side_effect=none`，`provider_call_status=not_called`，`controlled_api_auth_gate=local_enforce_ready`。

Batch 7.9 验收结果：

- 已满足：受控 API 鉴权中间件强制模式要求 `X-Tenant-Id`，缺少租户头会返回 `401` 并记录 `authorization-denied`。
- 已满足：拒绝日志保留 `tenant_id=None`、请求路径和拒绝原因，停用用户拒绝日志保留本地租户 ID。
- 已满足：`/auth/session` 接受 `X-Tenant-Id` 并返回 `tenant_id`，前端 API client 默认发送 `X-Tenant-Id: hospital-demo`。
- 已满足：本地 fullstack E2E 在强制受控 API 鉴权模式下通过 `16 passed`，验证工作区 API 未漏带本地租户头。
- 未满足：真实医院 SSO、正式登录会话签发、正式租户身份来源、网关/Nginx claims 注入策略、生产只读和生产写入型权限验收仍未完成。
- 边界：`production_side_effect=none`，`provider_call_status=not_called`，`tenant_header_contract=local_ready`。

### Batch 8：生产验收和灰度发布

状态：`in_progress`

当前切片：`document_governance_ready_profile_verified`

目标：

- 在前面批次通过后，再做生产只读、授权写入和灰度验收。

开发项：

- 生产只读 smoke 更新。进度：已新增只读权限 smoke 脚本和 `production:permission-readonly` 入口；历史生产真实观测曾失败，最新 UI/UX 生产基线后已重新执行并在只读 GET 探测范围内通过观察。
- 授权写入 smoke 分角色执行。
- 生产前 DB 备份和回滚方案。
- 医院角色用户验收清单。

验收闸：

- 每个生产写入动作前有备份、授权和回滚路径。
- 生产 smoke 结果按 `production_readonly`、`authorized_live_side_effect` 分层记录。
- 当前生产 SHA、部署时间、报告路径和截图齐备。

Batch 8.1 验收结果：

- 已满足：只读权限 smoke 脚本只发 `GET`，覆盖公开路径、匿名受控路径、缺 `X-Tenant-Id` 路径和管理员带齐 header 路径。
- 已满足：本地严格模式和生产观测模式已拆开；生产观测模式不会把受控 API 状态差异直接写成生产验收通过。
- 已满足：脚本报告显式记录 `production_side_effect=none`、`provider_call_status=not_called` 和 `http_methods=["GET"]`。
- 未满足：尚未实际执行生产只读权限 smoke，尚无 `tmp/outputs/production-permission-readonly-smoke-latest.json` 的真实验收结论。
- 边界：`production_side_effect=none`，`provider_call_status=not_called`，`production_readonly_status=not_run`。

Batch 8.2 验收结果：

- 已满足：生产只读权限 smoke 已按授权执行，并生成 `tmp/outputs/production-permission-readonly-smoke-latest.json`。
- 已满足：执行全程只发 `GET`，报告记录 `production_side_effect=none` 和 `provider_call_status=not_called`。
- 未满足：生产只读权限 smoke 未通过，`/api/v1/auth/roles` 和 `/api/v1/auth/session` 未部署，多个本地 API-first workbench 生产返回 `404`。
- 未满足：部分已存在读接口对匿名或缺 `X-Tenant-Id` 请求返回 `200`，未执行本地 Batch 7.9 的租户头强制门禁。
- 边界：本批未部署生产、未写生产库、未执行授权写入 smoke。

Batch 8.3 验收结果：

- 已满足：生产部署状态只读巡检复核完成，当前生产实际 SHA 为 `550a445012267ba1211f5881b1d441264f3a3056`。
- 已满足：生产容器、Nginx 挂载、检索后端和最新本地 smoke 引用均通过只读巡检。
- 已满足：确认旧文档 SHA `f864e370abd7309f6222376074b45ef2bc6c0ff4` 已过期，并已同步到当前生产状态文档。
- 未满足：本地当前工作树不是干净发布候选，存在大量 tracked/untracked 变更，且分支远端已 `[gone]`。
- 未满足：尚未形成发布 manifest、干净 release 分支、部署 dry-run preflight 或生产权限复验通过证据。
- 边界：本批未部署生产、未写生产库、未执行授权写入 smoke。

Batch 8.4 验收结果：

- 已满足：最新 UI/UX 生产基线部署状态只读复核完成，`tmp/outputs/tencent-cloud-deployment-state-auth-permission-20260630T041340+0800.json` 返回 `status=pass`，生产实际 SHA 为 `a78bf8e5a1303178df26d03c6a687bd68f4512c2`。
- 已满足：生产 app/postgres/clamav 均 healthy，`virus_scan_provider=clamav-sidecar`，`dlp_review_provider=ruleset-v1`，`audit_frontdoor_healthy=true`，`audit_next_static_healthy=true`，`search_backend_ready=true`，`matching_embedding_count=49051`。
- 已满足：生产只读权限 smoke 已重新执行，`tmp/outputs/production-permission-readonly-smoke-auth-permission-20260630T041340+0800.json` 返回 `status=observed`、`probe_count=35`、`issue_count=0`、`observation_count=0`，全程只发 `GET`。
- 已满足：本批探测的 `/auth/session`、查询历史、疑点、图谱、规则、整改、归档和报告 workbench 只读路径对匿名或缺 `X-Tenant-Id` 返回 `401`，带管理员角色、项目和租户头返回 `200`。
- 未满足：真实医院 SSO、正式登录会话签发、正式租户身份来源、网关/Nginx claims 注入策略和生产写入型权限验收仍未完成。
- 边界：本批未部署生产、未写生产库、未调用 provider、未执行授权写入 smoke；只证明被探测 GET 路径的 L3 生产只读权限行为。

Batch 8.5 验收结果：

- 已满足：新增 `scripts/audit-auth-sso-contract-readiness.py` 与 `pnpm auth:sso-contract-readiness`，把 P0-04 真实 SSO/session 合同转为可执行 readiness 门禁。
- 已满足：脚本默认目标为 `trusted-sso-proxy`，只检查本地 env 名称和 `SET/UNSET` 状态，不访问网络、不写生产 env、不调用 provider、不执行生产写入。
- 已满足：目标测试通过，`uv run pytest tests/knowledge_query/test_scripts.py -k "audit_auth_sso_contract_readiness"` 返回 `3 passed`；`ruff` 和 `py_compile` 通过。
- 已满足：本批 readiness 报告 `tmp/outputs/auth-sso-contract-readiness-p0-04-20260630T042500+0800.json` 返回 `status=blocked`、`evidence_grade=L2-fixture-or-dry-run`，并明确 `secret_values_reported=false`。
- 未满足：可信代理、签名密钥 env、允许来源 CIDR、关闭 legacy header auth 仍未配置；server-session 路径也未选择或配置。
- 边界：本批是合同/门禁固化，不证明真实医院 SSO、正式登录会话、生产配置或写入型权限验收完成。

Batch 8.6 验收结果：

- 已满足：新增 `scripts/audit-document-governance-contract-readiness.py` 与 `pnpm document:governance-contract-readiness`，把 P0-05 文档治理安全闭环转为可执行 readiness 门禁。
- 已满足：脚本复用文档上传治理 provider preflight 和 Tencent COS bootstrap preflight，只读取本地配置/env 名称与 `SET/UNSET` 状态，不访问网络、不写对象存储、不写生产 env、不调用外部治理 provider、不执行生产写入。
- 已满足：目标测试通过，`uv run pytest tests/knowledge_query/test_scripts.py -k "audit_document_governance_contract_readiness"` 返回 `3 passed`；`ruff`、`py_compile` 和 package JSON 解析通过。
- 已满足：本批 readiness 报告 `tmp/outputs/document-governance-contract-readiness-latest.json` 返回 `status=blocked`、`evidence_grade=L2-fixture-or-dry-run`，并明确 `secret_values_reported=false`。
- 未满足：Tencent COS/provider、对象记录、企业级病毒/DLP provider、脱敏改写、策略版本、人工复核和审计事件合同仍未配置；授权写入型治理 E2E、归档签章和恢复演练尚未执行。
- 边界：本批是本地合同/门禁固化，不证明生产对象存储、外部 DLP、脱敏改写、证书级签章或长期留存闭环完成。

Batch 8.7 验收结果：

- 已满足：P0-05 的脱敏改写、策略版本、人工复核和治理审计事件合同已进入 `DocumentUploadGovernanceSettings`，并支持 `MEDICAL_AUDIT_DOCUMENT_REDACTION_*` 与 `MEDICAL_AUDIT_DOCUMENT_GOVERNANCE_AUDIT_EVENT_REQUIRED` env override。
- 已满足：`document:governance-contract-readiness` 改为读取 typed settings，而不是在脚本内裸读脱敏/审计 env 值；报告仍只输出合同状态和 COS secret env 的 `SET/UNSET`。
- 已满足：目标测试通过，`uv run pytest tests/knowledge_query/test_config.py tests/knowledge_query/test_scripts.py -k "document_governance or document_upload_governance or audit_document_governance"` 返回 `6 passed`；`ruff` 与 `py_compile` 通过。
- 已满足：本批 readiness 报告仍按预期 `status=blocked`，阻塞项继续覆盖 COS、对象记录、企业级病毒/DLP provider、脱敏改写和审计事件合同。
- 未满足：生产没有写入新 env；Tencent COS/object recording、企业级治理 provider、真实脱敏改写、生产只读复核和授权写入型治理 E2E 仍未执行。
- 边界：本批只是本地 typed config contract，不证明生产配置、对象存储写入、外部 provider 调用或证书级合规闭环完成。

Batch 8.8 验收结果：

- 已满足：新增非生产配置 `configs/knowledge-query-engine-document-governance-ready-profile.yaml`，覆盖 Tencent COS provider、bucket/region、secret env name、SDK bootstrap、对象记录、签名 URL TTL、retention、ClamAV sidecar、ruleset DLP、脱敏策略、人工复核和审计事件合同。
- 已满足：新增 `pnpm document:governance-ready-profile` 与 `scripts/run-document-governance-ready-profile.py`；wrapper 内部注入非生产 sentinel env value，package 命令回显不暴露 sentinel 值。
- 已满足：目标测试通过，`uv run pytest tests/knowledge_query/test_scripts.py -k "audit_document_governance or run_document_governance_ready_profile"` 返回 `5 passed`；`ruff`、`py_compile` 和 package JSON 解析通过。
- 已满足：`pnpm document:governance-ready-profile` 返回 `status=ready_for_readonly_governance_probe`、`blockers=[]`、`evidence_grade=L2-fixture-or-dry-run`，并记录 `production_side_effect=none`、`object_storage_write=false`、`external_governance_provider_call=not_called`、`secret_values_reported=false`。
- 未满足：本批没有生产只读复核、没有生产 env 写入、没有对象存储写入、没有外部 DLP/virus provider 调用、没有授权写入型治理 E2E。
- 边界：ready-profile 只证明本地合同可达，不证明生产 COS、真实脱敏改写、外部治理 provider 或证书级合规闭环完成。

Batch 8.9 验收结果：

- 已满足：新增 `scripts/prepare-document-governance-production-readonly-plan.py` 与 `pnpm document:governance-production-readonly-plan`，把 P0-05 生产只读准备拆成 `local-ready-profile-dry-run`、`production-readonly-observation` 和 `authorized-write-governance-e2e` 三个证据层。
- 已满足：准备包输出 `tmp/outputs/document-governance-production-readonly-plan-latest.json` 与 `.md`，列明生产只读报告必备字段、生产配置授权输入、rollback 要求和后续证据升级路径。
- 已满足：本批准备包明确 `production-readonly-not-run`、`production-env-write-not-authorized`、`authorized-write-e2e-not-authorized` 和 `provider-smoke-not-authorized` 仍为 blocker。
- 已满足：目标测试通过，`uv run pytest tests/knowledge_query/test_scripts.py -k "prepare_document_governance_production_readonly_plan"` 返回通过；`py_compile`、`ruff`、package JSON 解析和 package 命令输出 JSON 解析通过。
- 未满足：本批没有执行生产只读 probe，没有写生产 env，没有对象存储写入，没有外部治理 provider 调用，也没有授权写入型治理 E2E。
- 边界：本批只是 L2 本地准备包，不证明当前生产文档治理配置已观测；生产只读通过后才可升级到 `L3-production-read-only`，写入型治理 E2E 只有备份、显式授权和回滚点齐备后才可能升级到 `L4-authorized-live`。

## 6. 下一步执行顺序

当前已推进到 Batch 8.9 P0-05 生产只读准备包。原因：

- Batch 1 已完成可重复本地全栈 smoke，后续每批功能都有同一条回归入口。
- Batch 2 已把账号/角色底座、受控写入口、项目级角色 scope、核心查询/文档/审计日志路由、受控 API 鉴权中间件和本地租户头契约推进到本地可验收状态。
- Batch 3/4 已补齐后端 Word/docx 导出、模板 registry 和 Next `/reports` API-first 下载本地能力；Batch 5 已补齐文档上传治理、本地策略扫描、下载隔离、后端 `title_only`、搜索历史和个人材料本地入索引。
- Batch 6 已完成图谱、规则、整改和归档四个只读 workbench 的 API-first 切片。
- Batch 7 已完成智能体版本、生命周期、调用反馈、真实对话挂接、项目范围校验、逐行 diff、审核状态记录、审批通过才激活门禁、`admin/director` 激活角色门禁、项目级角色 scope、受控 API 鉴权中间件和本地租户头契约的本地切片。
- Batch 8.1 已把生产权限只读 smoke 的执行入口准备好。
- Batch 8.2 曾执行生产只读观测，确认当时生产未包含本地 `/auth/*`、受控 API 鉴权中间件、租户头门禁和 API-first workbench 切片。
- Batch 8.3 完成旧生产部署差异只读复核并指出需要干净 release 路径。
- Batch 8.4 在最新 UI/UX 已部署基线后重新执行部署状态审计和生产权限只读 smoke，确认本批探测的受控 GET 路径已按租户头和角色头门禁工作。
- Batch 8.5 已把真实 SSO/session claims、可信代理签名、正式租户身份来源和关闭 legacy header 授权的条件固化为本地 readiness 门禁，当前按预期 fail-closed 为 `blocked`。
- Batch 8.6 已把文档对象存储、外部治理 provider、脱敏改写、留存和审计事件合同固化为本地 readiness 门禁，当前按预期 fail-closed 为 `blocked`。
- Batch 8.7 已把脱敏改写、策略版本、人工复核和治理审计事件合同从脚本裸 env 检查提升到正式 settings/env override 层；本批未验证或变更生产配置，默认 readiness 继续 fail-closed。
- Batch 8.8 已用非生产 ready-profile 证明 P0-05 合同可以进入 `ready_for_readonly_governance_probe`，同时保持无生产副作用和 secret value 不输出。
- Batch 8.9 已把生产只读复核字段、生产配置授权输入、rollback 要求和写入型 E2E 授权边界固化为本地准备包；当前仍未执行生产只读或任何生产写入。

下一批优先执行的收口计划：

1. P0-05 生产配置授权包人工复核：基于 `document:governance-production-readonly-plan` 生成的 env 名称、目标 bucket/region、对象记录开关、脱敏策略版本、ClamAV/DLP 路径和回滚点，形成人工确认清单；未获授权前不执行生产 env 写入。
2. P0-05 生产只读执行前检查：复跑 `pnpm document:governance-ready-profile` 和 `pnpm document:governance-production-readonly-plan`，确认准备包仍无 secret value 输出，再单独申请生产只读 probe 授权。
3. P0-05 生产只读复核：只有获得只读授权后才执行生产 GET-only probe，并把生产当前配置观测、ready-profile dry-run 和授权写入型 E2E 继续分开记录。
4. P0-05 写入型治理 E2E：只有备份、显式授权和回滚路径齐备后才执行对象存储写入、治理结果写入、归档签章或恢复演练。
5. P0-04 路径选择仍未关闭：在 `trusted-sso-proxy` 与 `server-session` 中选定一条生产路径；未选定前不写生产 env。
6. F2 no-fallback 生成：生产仍缺 answer provider key；如需推进，必须先明确授权一次 provider smoke，不能用 UI/权限验收或文档治理 readiness 替代生成模型门禁。

Batch 1 的完成项：

1. 抽取本轮一次性 FastAPI 测试服务为仓库脚本。已完成：`scripts/run-local-fullstack-e2e.py`。
2. 接入 Playwright E2E 前置启动或提供明确命令。已完成：`pnpm local:fullstack:e2e`。
3. 写入本地联调运行文档和证据边界。已完成：本文档 Batch 1。
4. 复跑 `pnpm local:fullstack:e2e`、前端 lint/typecheck/unit/build 和后端 ruff/mypy/pytest。已完成。
5. 增加 PostgreSQL 只读探测模式并输出报告。已完成；当前本机 `localhost:5433` 未响应，所以真实 PostgreSQL 验收仍是 blocked。

Batch 2 已完成任务：

1. 盘点现有认证入口、`X-Role`/`X-User-Id` 过渡层、项目成员 API 和前端角色使用点。
2. 定义最小权限模型：`admin`、`technician`、`director`、`member` 的 API action matrix。
3. 完成后端权限辅助、拒绝审计日志、受控写入口权限、前端入口显隐和 401/403 状态。
4. 完成 `/query`、`/documents`、`/audit/logs` 核心路由持久化用户优先解析专项回归。
5. 完成项目级 `scope_type=project` 角色授权在 `/auth/session` 和 `/projects/{project_key}/members` 写入口的本地生效。
6. 完成受控 API 鉴权中间件本地强制模式、拒绝日志和 Next 工作区 API 角色头覆盖。
7. 完成本地 `X-Tenant-Id` 请求头契约、`/auth/session` 租户回显和强制鉴权 E2E 漏头门禁。

Batch 5 已完成任务：

1. 后端 `/query` 已支持 `title_only` 并记录查询历史。
2. 个人材料已完成上传留存、本人/读全部角色隔离、下载权限隔离、本地策略扫描和 DLP 标记。
3. 个人材料治理已完成 `pending-review/approved-for-index/blocked` 准入状态和高风险文件阻断。
4. 个人材料本地文本入索引已完成 `/documents/uploads/{upload_id}/index`，并在 `/query` 以 `personal_upload_matches` 独立返回按权限命中的个人材料片段。
5. Next `/documents` 已显示个人材料本地索引状态、治理按钮、入索引按钮和检索结果中的个人材料命中区。

Batch 7 已完成任务：

1. 提示词版本新增、回滚、逐行对照、审核状态记录和审批通过才激活。
2. 智能体下架、软归档、active 列表过滤和历史追溯。
3. 智能体调用记录、效果反馈、反馈统计和真实对话入口自动登记。
4. 智能体角色过滤、项目范围校验和普通成员发布限制。
5. Next `/agents` 完成版本治理、审核意见、审批按钮、待审/当前激活标记和反馈统计的本地工作台交互。

Batch 8 已完成任务：

1. 新增只读权限 smoke 脚本：`scripts/run-controlled-api-readonly-permission-smoke.py`。
2. 新增本地严格模式入口：`pnpm local:permission:readonly`。
3. 新增生产只读观测入口：`pnpm production:permission-readonly`。
4. 为脚本增加契约测试，固定只读方法、租户头门禁和 observe 模式边界。
5. 执行一次生产只读权限观测，结论为 `status=fail`，报告路径为 `tmp/outputs/production-permission-readonly-smoke-latest.json`。
6. 执行一次生产部署状态只读复核，确认生产实际 SHA 为 `550a445012267ba1211f5881b1d441264f3a3056` 且生产当前健康；同时确认当前本地工作树不可直接发布。

## 7. 当前状态结论

事实：

- 第一阶段核心功能的前端入口已经成型，且主要工作区页面通过本地 E2E。
- 后端已有知识检索、索引治理、智能体、项目成员、数据分析上传、文档权限/上传、复核任务、审计日志等基础能力。
- 本轮新鲜本地质量闸、强制鉴权内存态全栈 E2E、Batch 1 固化脚本、Batch 7.9 权限/智能体治理专项测试和 Batch 8.1 只读权限 smoke 脚本契约测试均已通过；Batch 8.2 生产只读权限 smoke 已执行但未通过；Batch 8.3 生产部署状态只读复核已通过。
- 本轮 PostgreSQL 只读探测已形成报告，状态为 `blocked`，定位到本机 `localhost:5433` 未响应；该结论不涉及生产数据库。

推断：

- 下一批更适合先做干净 release 分支/worktree 和发布 manifest：把已完成的本地权限/租户/Workbench/脚本能力从脏工作树精确移植到可审计发布候选；在完成部署授权前，不应执行授权写入 smoke。
- 权限、底稿导出、材料治理和智能体治理是产品可交付性的主路径。

不确定项：

- 生产 PostgreSQL 容器和检索后端运行态已通过只读巡检；生产数据库业务数据未做写入或深度一致性核验。
- 生产当前不包含本地 `/auth/*` 和多个 workbench API 切片；生产是否包含全部 UI 重构细节仍需页面级生产验收。
- 医院侧真实 SSO、组织架构、签章和对象存储方案需要业务/运维确认。

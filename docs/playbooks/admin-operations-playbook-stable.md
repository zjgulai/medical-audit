---
title: medical_audit 管理员运维 Playbook
doc_type: operations-playbook
module: operations
status: stable
created: 2026-08-13
updated: 2026-08-15
owner: self
source: human+ai
---

# medical_audit 管理员运维 Playbook

本文说明本地验证、构建、生产只读检查、备份、恢复和故障处理。任何生产写操作都必须绑定 exact SHA、精确目标和独立授权。

## 1. 本地质量门禁

### 前置条件

- 当前分支是候选分支。
- 工作树只包含本轮授权变更。
- 不启动、扫描、清理、重建或修改本地 Docker。
- Provider 测试默认使用 Fake；`provider_call=false`。

### 执行顺序

```bash
uv run ruff check .
uv run mypy src
uv run pytest
pnpm web:lint
pnpm web:typecheck
pnpm web:test
pnpm web:build
pnpm local:fullstack:e2e
pnpm docs:lint
git diff --check
```

每条命令失败时停止完成声明。先执行最小复现和定向回归，再重跑完整门禁。

### 本地 E2E 收据

`pnpm local:fullstack:e2e` 创建临时 SQLite 数据库和确定性 Fake Provider，运行结束后删除临时目录。默认收据位于：

```text
tmp/outputs/local-fullstack-feature-acceptance-latest.json
```

收据必须包含 `provider_call=false`、21 个独立页面、2 个兼容跳转和 4 条持久化业务工作流，共 27 条功能记录。四条工作流分别验证整改状态与附件、报告签发权限、项目/成员/文件持久化，以及确定性 Fake OCR 页映射。

## 2. 生产公开壳层只读检查

候选未部署前，不要对当前生产执行新的 `public-shell-readonly` 合同探针，因为当前生产可能仍接受受保护 GET。部署后仅执行：

```bash
pnpm production:permission-readonly
```

预期检查：

1. `/api/v1/health` 返回 `200`。
2. `/api/v1/deployment/metadata` 返回 `runtime_access.mode=public-shell-readonly`。
3. 一个受保护 GET 返回 `503 trusted_identity_required`。
4. 报告包含 `production_side_effect=none`、`database_write=false` 和 `provider_call_status=not_called`。

不要把 `production:frontend-acceptance` 直接列为只读命令。该 gate 默认 fail-closed，并要求 exact SHA、run ID、S1 guard 和显式副作用授权。

## 3. 浏览器壳层验收

只读导航验收覆盖 21 个独立页面、2 个兼容跳转、桌面和移动视口。执行前确认：

- 目标域名和 expected SHA 精确匹配。
- 使用 `--navigation-only-readonly`。
- 阻断所有 `/api/` 业务请求。
- 截图和报告写入本地证据目录，不写生产数据。

只有在候选已经按 exact SHA 部署、S1 收据通过，并另外取得生产只读授权后，才运行下列唯一命令模板：

```bash
pnpm production:frontend-navigation-readonly -- \
  --expected-deploy-sha <APPROVED_SHA> \
  --acceptance-run-id <ACCEPTANCE_RUN_ID> \
  --release-guard-report <S1_REPORT_PATH> \
  --ssh-key "$SSH_KEY_PATH" \
  --post-release-guard-report <S2_REPORT_PATH> \
  --release-guard-compare-report <S1_S2_COMPARE_PATH> \
  --confirm-production-readonly 101.34.52.232 \
  --output <FRONTEND_REPORT_PATH> \
  --screenshot-dir <SCREENSHOT_DIR>
```

该 gate 在浏览器导航前重新校验 S1，在导航后执行一次 L3 S2 只读捕获并生成 S1→S2 比较。只有 `audit_log_delta=0`、`database_write=false`、同一 SHA/run ID、23 个入口的桌面和移动截图均完整时才通过。任一参数缺失、证据文件复用、受保护 API 尝试或状态漂移都会失败关闭。

发现页面错误时，在本地复现和修复。不得直接修改生产静态文件；每个新 hotfix SHA 都需要新的部署授权。

## 4. 构建与 release manifest

生产构建必须在 clean `main == origin/main == approved SHA` 上执行：

```bash
MEDICAL_AUDIT_DEPLOY_SHA=<40-char-sha> \
NEXT_PUBLIC_MEDICAL_AUDIT_API_ACCESS_MODE=public-shell-readonly \
pnpm web:build:release
```

manifest 必须绑定：

- `source_sha`。
- `pnpm-lock.yaml` 哈希。
- Node.js 和 pnpm 版本。
- `NEXT_PUBLIC_MEDICAL_AUDIT_API_ACCESS_MODE` 等公开构建变量。
- 静态文件路径、大小和 SHA-256。

构建目录出现 symlink、额外文件、缺失文件或 manifest 不一致时停止部署。

## 5. 部署门禁

本 Playbook 不授予部署权限。获得明确授权后，部署还必须满足：

1. 候选 PR 已审阅并 squash merge，形成唯一发布 SHA。
2. 已 fresh fetch，且发布工作树 clean。
3. 最终测试收据绑定同一 SHA。
4. 生产域名确认、approved SHA 和备份 stamp 精确提供。
5. 初次发布不执行 schema migration。

部署脚本先生成完整备份，再部署同一 exact SHA。失败时保留锁和证据，不在未知状态下重复执行。

## 6. 备份

完整生产批次由同一 timestamp 的以下类别组成：

- app。
- env。
- db。
- nginx。
- web。
- transaction。

只考虑超过 72 小时且类别完整的批次。始终保留：

- 最新两个完整批次。
- 当前和上一版本回滚批次。
- 最近成功部署批次。
- 至少一个经过隔离恢复验证的完整批次。

`pg_dump` 和 `pg_restore` 使用与数据库主版本匹配的容器内工具。大型 dump 先通过进程、`pg_stat_activity`、文件增长和 I/O 诊断，不直接运行完整 `gzip -t` 消耗多 GB I/O。

## 7. 恢复

恢复前必须具备：

- 精确备份 stamp。
- app、env、db、nginx、web 和 transaction 完整性证明。
- 数据库主版本和恢复工具兼容证明。
- 隔离环境恢复结果。
- 回滚目标 SHA 和停止条件。

恢复步骤必须在隔离环境验证后才可进入生产授权。没有新鲜隔离恢复证明时，生产备份删除状态为 `blocked`。

## 8. 安全清理

### 本地

先生成 exact-path manifest，记录绝对路径、大小、最后有效活动、Git 状态、HEAD、祖先关系、哈希、alternates、worktree 注册和引用关系。

移动前展示清单、总空间和恢复路径，并取得最终确认。确认后使用系统 Trash；不得使用 `rm -rf` 或 `git clean`。永久清空 Trash 需要第二次授权。

明确保护：

- `tmp/knowledge-query-indexes`。
- 唯一数据库 dump。
- 私有数据。
- 被引用截图和交付收据。
- `.git`、tracked 归档、活动 `.venv` 和 `node_modules`。
- 所有本地 Docker 资源。

### 生产

生产备份删除是独立门禁。使用精确绝对路径，不使用 glob，不跟随 symlink。删除后重新检查 SHA、健康、磁盘、备份完整性和审计增量。

## 9. 故障处理

### 受保护接口返回 `200`

这是 fail-open。立即停止生产验收，保存响应状态和 runtime metadata，不读取响应业务内容。在本地复现访问门禁，并通过新 hotfix SHA 重新走部署授权。

### 页面加载但出现业务请求

检查构建变量和 `runtime-access.ts`。生产壳层不得请求受保护 API。不要通过临时 Nginx 规则隐藏前端缺陷。

### Store 不可用

页面必须显示 unavailable，不得回退为可写 Sample。记录依赖状态和最早错误，停止写入操作。

### 签发或整改状态未知

先查询任务或整改详情。只有确认上次请求未生效时才重试，避免重复签发或重复状态迁移。

## 10. 证据字段

每份运行报告至少包含：

- `run_id`。
- `observed_at`。
- `git_sha` 或 `expected_deploy_sha`。
- `evidence_grade`。
- `production_side_effect`。
- `database_write`。
- `provider_call_status`。
- 执行命令和退出状态。
- failed、blocked、not_run 的原因。

健康容器、文件存在或历史记忆都不能单独作为部署完成证明。

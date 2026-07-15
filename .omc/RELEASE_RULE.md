---
title: medical_audit release rules
doc_type: release-rules
module: repository
status: active
created: 2026-07-15
updated: 2026-07-15
owner: self
source: repository-audit
---

# Release Rules
<!-- last-analyzed: 2026-07-15T01:33:03Z -->

## Version Sources

- `pyproject.toml`: `[project].version`，当前 `0.1.0`。
- `src/medical_audit_kb/__init__.py`: `__version__`，当前 `0.1.0`；FastAPI health/OpenAPI 使用该值，必须与 `pyproject.toml` 同步。
- `uv.lock`: `medical-audit-kb` package version，必须通过 `uv lock` 派生，不手改。
- `web/package.json`: private Web package version，当前 `0.1.0`；不发布 npm。
- 根 `package.json` 无 version 且 `private: true`。
- 未发现自动版本同步工具；当前生产发布身份以完整 Git SHA、deploy stamp 和远端 `.deploy-sha` 为准，不以 SemVer/tag 为准。

## Release Trigger

- 仓库没有 CI/CD workflow；merge、tag 或 GitHub Release 不会自动部署。
- 人工发布路径：功能分支本地门禁 -> PR 合入 `main` -> clean `main` 执行生产部署。
- `scripts/deploy-tencent-cloud-production.py` 默认只做 preflight；生产执行必须显式传入：
  - `--execute`
  - `--confirm-production audit.lute-tlz-dddd.top`
  - `--approved-sha <完整 40 位 SHA>`
- execute 前脚本 fetch `origin/main`，并强制 branch 为 `main`、worktree 干净、`HEAD == origin/main == approved_sha`。
- `--allow-dirty` 仅用于非 execute 检查；生产 execute 禁止使用。
- schema、query/provider、review 写入分别需要 `--apply-schema`、`--include-query-provider-smoke`、`--include-review-write` 和对应生产写确认，不能隐式合并为普通部署步骤。
- PR merge、tag、GitHub Release 与生产 deploy 是独立证据阶段。

## Test Gate

仓库没有自动 CI 门禁；合并/部署前必须人工执行并保存新鲜输出：

```bash
git diff --check
uv run ruff check .
uv run mypy src
uv run pytest
pnpm web:lint
pnpm web:typecheck
pnpm web:test
pnpm web:build
pnpm web:build:static
pnpm web:e2e
pnpm local:fullstack:e2e
pnpm local:permission:readonly
```

- 浏览器/端口环境不可用时必须明确记录未验证，不能视为通过。
- 部署脚本不会替代 Ruff、Mypy、Pytest、Web lint/typecheck/test 或 Playwright 门禁。
- execute 默认执行 Web static build、远端 preflight、stamp-scoped 备份、部署后 health/proxy 检查和默认生产 smoke。
- `--skip-web-build`、`--skip-app-rebuild`、`--skip-smoke` 会降低证据强度，只能在 release manifest 中有明确理由和审批时使用。
- `--apply-schema` 会执行生产 SQL，自动 rollback 不恢复数据库。
- 生产验收必须分别记录脚本退出、`.deploy-sha`、容器状态、GET-only smoke、权限 smoke、前端验收，以及任何 audit-log/database/provider side effect 的独立授权和增量证据。

## Registry / Distribution

- Python 使用 Hatchling，但未发现 PyPI build/publish 流程。
- 根/Web npm packages 均为 private，未发现 npm registry publish。
- 未发现 Docker registry push 或 immutable image artifact；应用使用远端本地标签 `medical-audit-kb:prod`。
- 发布通过 rsync 同步源码到 `/opt/medical-audit/app` 后在生产主机构建；Next static 输出同步到 `/var/www/audit`。
- execute 固定顺序：preflight -> static build -> app/env/db/nginx/web 备份 -> rsync -> 可选 schema -> build/recreate app -> health/Nginx/route checks -> 写 `.deploy-sha` -> 默认 smoke。
- 自动 rollback 恢复 app、Web 和 `.deploy-sha`，保留 env，不恢复数据库或 Nginx；schema/data 回滚必须独立设计。

## Release Notes Strategy

- 未发现 `CHANGELOG`、release body 或自动 release-note generator。
- commit 多采用 Conventional Commit 风格，但未自动校验。
- `.kiro/plan/release_manifest.md` 是发布证据清单，不是用户可读 changelog。
- 正式 tag release 前应按 Breaking Changes、New Features、Bug Fixes、Operational Changes 生成 release notes，并关联 PR 与部署 SHA。

## CI Workflow Files

- 未发现 `.github/workflows/`、`.circleci/`、`.travis.yml`、`Jenkinsfile`、`gitlab-ci.yml` 或 `bitbucket-pipelines.yml`。
- 人工发布规则来源：`package.json`、`pyproject.toml`、`web/package.json`、`.kiro/plan/release_manifest.md`、部署 workflow、deploy/smoke/audit scripts、Dockerfile 和 production Compose。

## First-Time Setup Gaps

- [P0] 无 CI workflow，PR 不能自动阻断 Ruff/Mypy/Pytest/Web/build 回归。
- [P1] 无 immutable release artifact；生产主机从 rsync 源码重新构建。
- [P1] production Dockerfile 未复制 `uv.lock`，`uv pip install .` 配合 `>=` dependency range 使构建不可完全复现。
- [P1] Web build 前未运行 `pnpm install --frozen-lockfile`，依赖现有本地 `node_modules`。
- [P1] app/base/service images 未 pin digest。
- [P1] app/Web rollback 不恢复数据库；任何 schema 发布必须单独规划数据库兼容和恢复。
- [已解决] `.gitnexus/` 已被根 `.gitignore`、`.dockerignore` 和 rsync excludes 统一排除；本地 `output/` 证据目录也已被 Docker context 和 rsync 排除。
- [P2] Python version facts 手工重复，存在漂移风险。
- [P2] 本地无 Git tags，且无正式 changelog/release notes。
- [P2] 历史 workflow 含 `--allow-dirty` 旧记录；当前 production execute 必须以代码的 fail-closed 规则为准。
- 已满足：常见 build、coverage、Next、Playwright、tmp 和 tsbuildinfo 产物已被忽略。
- 未核验：远端 branch protection、required reviews 和 required checks。

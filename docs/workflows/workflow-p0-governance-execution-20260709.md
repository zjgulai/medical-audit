---
title: medical_audit P0 治理第一批执行记录
doc_type: workflow
module: project-governance
status: active
created: 2026-07-09
updated: 2026-07-09
owner: codex
source: production-readonly+local-git-inventory
---

# medical_audit P0 治理第一批执行记录

## 1. 执行边界

- 本批只做治理建账、证据压缩和下一步决策准备。
- 未修改业务代码、前端 UI、后端 API 或生产配置。
- 未删除生产备份、Docker 资源、worktree、分支或草稿文件。
- 未写生产数据库，未执行生产部署。
- 生产侧只做 SSH read-only 采样和现有部署状态审计。

## 2. 本批已产出

- 生产部署状态审计：`tmp/outputs/p0-production-state-20260709.json`。
- 生产备份与磁盘原始 manifest：`tmp/outputs/p0-production-backup-disk-manifest-20260709.json`。
- 根目录脏树原始 manifest：`tmp/outputs/p0-root-dirty-manifest-20260709.json`。
- worktree 原始 manifest：`tmp/outputs/p0-worktree-manifest-20260709.json`。
- PR #186 原始 manifest：`tmp/outputs/p0-pr186-manifest-20260709.json`。
- 可提交汇总 manifest：`docs/workflows/manifests/medical-audit-p0-governance-manifest-20260709.json`。

`tmp/outputs` 下的文件是本地运行证据，不作为长期合同；长期引用以 `docs/workflows/manifests/medical-audit-p0-governance-manifest-20260709.json` 为准。

## 3. 核心事实

### 3.1 生产环境

- 生产 deploy SHA：`d6ae4c191453b0e5619d451cb26b41e3aeb68bee`。
- 生产状态审计：`status=pass`，`issues=[]`，`warnings=[]`。
- 生产容器：`medical_audit_app`、`medical_audit_pg`、`medical_audit_clamav` 均为 running/healthy。
- 生产根分区只读采样：`used_pct=90.54`，`free_bytes=15271452672`。
- `/opt/medical-audit/backups` 总量：`132` 个文件，`125908896663` bytes。
- 3 天前备份候选量：`40` 个文件，`35345615098` bytes。

### 3.2 本地根目录

- 根目录：`/Users/pray/project/medical_audit`。
- 当前根目录 `main` 仍落后 `origin/main`，且有 `367` 条未收敛变更。
- 分组计数：
  - `.kiro-plan`: `20`
  - `drafts-analysis`: `298`
  - `docs`: `4`
  - `repo-config`: `3`
  - `scripts`: `5`
  - `src-backend`: `9`
  - `tests`: `7`
  - `web-frontend`: `19`
  - `output-generated`: `1`
  - `other`: `1`

结论：根目录不能作为开发基线，只能作为待治理对象。

### 3.3 Worktree

- 当前 worktree 总数：`44`。
- `prunable`: `4`。
- `detached`: `15`。
- branch worktree：`29`。
- dirty existing worktree：`2`。

脏 worktree：

- `/Users/pray/project/medical_audit`：`367` 条，建议保留但禁止继续开发，先做分组决策。
- `/Users/pray/project/medical_audit-prod-clean-b5ad9fce`：`1` 条，建议人工检查后再决定归档或移除。

### 3.4 PR #186

- PR：`https://github.com/zjgulai/medical-audit/pull/186`。
- 状态：`OPEN`。
- 分支：`codex/project-governance-20260706`。
- 结论：不建议原样合并。该 PR 的事实基线早于当前生产与当前治理 manifest。
- 建议：先确认其中 `docs/api/frontend-backend-page-contract.json` 是否仍有唯一价值；如无唯一价值，关闭或以当前 manifest 替代。

## 4. 下一批 TODO

1. 生产备份清理授权包
   - 输入：`docs/workflows/manifests/medical-audit-p0-governance-manifest-20260709.json`。
   - 动作：生成删除候选清单，默认只包含 3 天前备份；保留最近 3 天和最新成功部署备份。
   - 边界：需要单独明确授权后才能删除。
   - 验收：删除前后记录磁盘、备份数量、容器健康和 deploy SHA。

2. Worktree 元数据 prune 与移除候选确认
   - 输入：manifest 中的 `prunable_paths` 和 `recommendation_counts`。
   - 动作：先处理 4 个 prunable 元数据；detached worktree 逐个确认用途。
   - 边界：不移除 dirty worktree。
   - 验收：`git worktree list --porcelain` 数量下降，根目录仍保留。

3. 根目录脏树分组决策
   - 输入：manifest 中的 `local_root_dirty_tree.groups`。
   - 动作：按 `keep / archive / migrate / discard-candidate` 标注每组。
   - 边界：不在根目录直接开发，不用 `git add .`。
   - 验收：每组都有处置结论，后续提交按组拆分。

4. PR #186 处置
   - 输入：PR #186 文件列表和当前 manifest。
   - 动作：比较是否有唯一内容；若无，关闭并在评论中指向当前治理 manifest。
   - 边界：关闭 PR 前先给出结论，避免误丢仍有价值的合同文档。
   - 验收：GitHub 只保留当前有效治理入口。

## 5. 完成标准

- 当前治理事实有单一可引用 manifest。
- 生产清理候选和本地清理候选已经分离。
- 下一步的删除、移除、关闭 PR 都有独立授权点。
- 项目继续开发只能从干净 `origin/main` worktree 开始。

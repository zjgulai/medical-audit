---
title: medical_audit 项目治理与生产线收敛
status: active
created_at: 2026-07-06
owner: codex
evidence_grade: mixed
---

# medical_audit 项目治理与生产线收敛

## 当前事实基线

- 本地根工作树：`/Users/pray/project/medical_audit`，分支 `main`，当前落后 `origin/main`，且存在多组未提交/未跟踪变更。
- 正确重构前端基线：PR #185，已合并到 `main`，merge commit `edae456790c2abb3d2ee896179a0b67be3e696fa`。
- 生产当前已从干净 `main@edae4567` 部署；生产 `.deploy-sha` 已观测为 `edae456790c2abb3d2ee896179a0b67be3e696fa`。
- 本地 Docker 项目边界：只管理 compose project `medical_audit`，当前对应容器 `medical-audit-kb-postgres`。
- 生产 Docker 项目边界：只管理 `medical_audit_app`、`medical_audit_pg`、`medical_audit_clamav`、`medical_audit_pgdata`、`medical_audit_clamav_data`、`medical_audit_internal`。

## 证据层级

- `local-validation`：本地测试、类型检查、lint、静态构建、worktree 状态。
- `production-read-only`：公网浏览器、HTTP smoke、SSH 只读状态审计、Nginx config test。
- `authorized-live`：PR merge、生产部署、远端文件同步、容器 rebuild/recreate、备份或静态目录覆盖。

结论必须明确证据层级。不得把本地验证、PR 可合并、生产只读可见、生产写入完成混成一个状态。

## Git 与 worktree 治理

- 不在脏 `main` 上继续业务开发；新功能和治理操作必须从干净 worktree 或明确 release branch 执行。
- PR #185 是前端恢复基线；已合并后以 `main@edae4567` 作为下一阶段前端基线。
- 所有 worktree 在清理前先登记：路径、branch、HEAD、dirty 状态、用途、保留建议。
- 可直接移除的候选只限干净、已替代、无唯一成果的临时 worktree；非空 dirty worktree 先保存 diff/manifest。

## 文件与材料治理

- 源码：`src/`、`web/src/`、`scripts/`、`configs/`、`tests/`。
- 正式文档：`docs/`，其中稳定流程放 `docs/workflows/`。
- 阶段性计划与分析：`drafts/analysis/`。
- 一次性验收输出：`tmp/outputs/`、`output/`、`web/output/`，默认不进 Git。
- 误生成嵌套输出：`web/web/`，先保留并登记，后续只在确认无唯一价值后归档。
- KB 后端变更独立处理，不与前端恢复、文档治理或生成物忽略策略混合提交。

## Docker 与生产治理

- 本地禁止 `docker system prune`；只允许针对 compose project `medical_audit` 做只读核验或明确的项目内操作。
- 生产清理只限定 `/opt/medical-audit`、`/var/www/audit` 和 `medical_audit_*` 资源。
- 备份清理必须先产出 manifest，默认保留最近 3 天和最近一次成功部署备份；真正删除需要单独授权。
- `/pages/*` 旧后端路由暂列为 legacy compatibility；新前端与 API 合同闭环后再分阶段退休。

## 下一阶段合同冻结

- `docs/api/frontend-backend-page-contract.json` 是页面到后端能力的唯一合同入口。
- 每个页面必须记录当前数据来源、目标 API、fallback 策略和验收方式。
- 后端接入阶段只改数据与 API 连接，不改已经恢复的 UI 风格。

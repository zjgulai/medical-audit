---
title: medical_audit 生产备份删除授权包
doc_type: workflow
module: production-governance
status: executed-via-followup
created: 2026-07-09
updated: 2026-07-09
owner: codex
source: production-readonly
---

# medical_audit 生产备份删除授权包

## 边界

- 本文件是删除前授权包；原始授权 JSON 保持 `delete_executed=false`，用于保留删除前证据。
- 删除动作已在后续授权批次执行，执行记录见 `docs/workflows/workflow-production-backup-delete-execution-20260709.md`。
- 默认保留最近 3 天备份，并保护每个分类最新备份。

## 当前采样

- 生产根分区使用率：`90.54%`。
- 备份总文件：`132`。
- 备份总大小：`125908896663` bytes。
- 候选文件：`46`。
- 候选大小：`40549758482` bytes。

## 验收方式

1. 删除前重新执行只读 manifest，确认候选未漂移。
2. 删除时只删除本授权包内候选路径。
3. 删除后复查磁盘、`medical_audit_*` 容器状态、deploy SHA 和 Nginx 配置。

## 候选清单

- `/opt/medical-audit/backups/app/pre-deploy-postmerge-main-a7a81da6-20260705.tar.gz` | `app` | `185231566` bytes | mtime `2026-07-05T17:53:38+0800` | age `3.88` days
- `/opt/medical-audit/backups/env/medical-audit.env.pre-deploy-postmerge-main-a7a81da6-20260705` | `env` | `2576` bytes | mtime `2026-07-05T17:53:38+0800` | age `3.88` days
- `/opt/medical-audit/backups/db/pre-deploy-postmerge-main-a7a81da6-20260705.sql.gz` | `db` | `4834954411` bytes | mtime `2026-07-05T18:09:07+0800` | age `3.86` days
- `/opt/medical-audit/backups/web/audit-web-pre-deploy-postmerge-main-a7a81da6-20260705.tar.gz` | `web` | `643150` bytes | mtime `2026-07-05T18:09:07+0800` | age `3.86` days
- `/opt/medical-audit/backups/nginx/nginx.conf.pre-deploy-postmerge-main-a7a81da6-20260705` | `nginx` | `33029` bytes | mtime `2026-07-05T18:09:07+0800` | age `3.86` days
- `/opt/medical-audit/backups/app/pre-deploy-login-gate-579d3983-20260705T1958.tar.gz` | `app` | `198434728` bytes | mtime `2026-07-05T19:58:41+0800` | age `3.79` days
- `/opt/medical-audit/backups/env/medical-audit.env.pre-deploy-login-gate-579d3983-20260705T1958` | `env` | `2576` bytes | mtime `2026-07-05T19:58:41+0800` | age `3.79` days
- `/opt/medical-audit/backups/db/pre-deploy-login-gate-579d3983-20260705T1958.sql.gz` | `db` | `4834957770` bytes | mtime `2026-07-05T20:14:15+0800` | age `3.78` days
- `/opt/medical-audit/backups/web/audit-web-pre-deploy-login-gate-579d3983-20260705T1958.tar.gz` | `web` | `432289` bytes | mtime `2026-07-05T20:14:15+0800` | age `3.78` days
- `/opt/medical-audit/backups/nginx/nginx.conf.pre-deploy-login-gate-579d3983-20260705T1958` | `nginx` | `33029` bytes | mtime `2026-07-05T20:14:15+0800` | age `3.78` days
- `/opt/medical-audit/backups/app/pre-deploy-main-65a7ca61-login-gate-20260706.tar.gz` | `app` | `185131923` bytes | mtime `2026-07-06T00:59:06+0800` | age `3.58` days
- `/opt/medical-audit/backups/env/medical-audit.env.pre-deploy-main-65a7ca61-login-gate-20260706` | `env` | `2576` bytes | mtime `2026-07-06T00:59:06+0800` | age `3.58` days
- `/opt/medical-audit/backups/db/pre-deploy-main-65a7ca61-login-gate-20260706.sql.gz` | `db` | `4834962238` bytes | mtime `2026-07-06T01:14:39+0800` | age `3.57` days
- `/opt/medical-audit/backups/web/audit-web-pre-deploy-main-65a7ca61-login-gate-20260706.tar.gz` | `web` | `550366` bytes | mtime `2026-07-06T01:14:39+0800` | age `3.57` days
- `/opt/medical-audit/backups/nginx/nginx.conf.pre-deploy-main-65a7ca61-login-gate-20260706` | `nginx` | `33029` bytes | mtime `2026-07-06T01:14:39+0800` | age `3.57` days
- `/opt/medical-audit/backups/nginx/nginx.conf.pre-api-v1-prefix-2adee6e4-20260706T022056+0800` | `nginx` | `33029` bytes | mtime `2026-07-06T02:20:56+0800` | age `3.52` days
- `/opt/medical-audit/backups/app/pre-deploy-legacy-page-retire-docker-b5ad9fce-20260706T030541+0800.tar.gz` | `app` | `184818184` bytes | mtime `2026-07-06T03:06:38+0800` | age `3.49` days
- `/opt/medical-audit/backups/env/medical-audit.env.pre-deploy-legacy-page-retire-docker-b5ad9fce-20260706T030541+0800` | `env` | `2576` bytes | mtime `2026-07-06T03:06:38+0800` | age `3.49` days
- `/opt/medical-audit/backups/db/pre-deploy-legacy-page-retire-docker-b5ad9fce-20260706T030541+0800.sql.gz` | `db` | `4834973471` bytes | mtime `2026-07-06T03:22:13+0800` | age `3.48` days
- `/opt/medical-audit/backups/web/audit-web-pre-deploy-legacy-page-retire-docker-b5ad9fce-20260706T030541+0800.tar.gz` | `web` | `637092` bytes | mtime `2026-07-06T03:22:13+0800` | age `3.48` days
- `/opt/medical-audit/backups/nginx/nginx.conf.pre-legacy-page-retire-nginx-b5ad9fce-20260706T032743+0800` | `nginx` | `33028` bytes | mtime `2026-07-06T03:27:43+0800` | age `3.48` days
- `/opt/medical-audit/backups/nginx/nginx.conf.pre-deploy-legacy-page-retire-docker-b5ad9fce-20260706T030541+0800` | `nginx` | `33028` bytes | mtime `2026-07-06T03:22:13+0800` | age `3.48` days
- `/opt/medical-audit/backups/app/pre-deploy-main-65a7ca61-replica-recovery-20260706T0415.tar.gz` | `app` | `185292269` bytes | mtime `2026-07-06T04:18:26+0800` | age `3.44` days
- `/opt/medical-audit/backups/env/medical-audit.env.pre-deploy-main-65a7ca61-replica-recovery-20260706T0415` | `env` | `2576` bytes | mtime `2026-07-06T04:18:26+0800` | age `3.44` days
- `/opt/medical-audit/backups/db/pre-deploy-main-65a7ca61-replica-recovery-20260706T0415.sql.gz` | `db` | `4834972882` bytes | mtime `2026-07-06T04:33:58+0800` | age `3.43` days
- `/opt/medical-audit/backups/web/audit-web-pre-deploy-main-65a7ca61-replica-recovery-20260706T0415.tar.gz` | `web` | `629222` bytes | mtime `2026-07-06T04:33:58+0800` | age `3.43` days
- `/opt/medical-audit/backups/nginx/nginx.conf.pre-deploy-main-65a7ca61-replica-recovery-20260706T0415` | `nginx` | `33317` bytes | mtime `2026-07-06T04:33:58+0800` | age `3.43` days
- `/opt/medical-audit/backups/app/pre-deploy-release-6178cff1-restore-ui-agents-20260706.tar.gz` | `app` | `185038253` bytes | mtime `2026-07-06T05:14:17+0800` | age `3.4` days
- `/opt/medical-audit/backups/env/medical-audit.env.pre-deploy-release-6178cff1-restore-ui-agents-20260706` | `env` | `2576` bytes | mtime `2026-07-06T05:14:17+0800` | age `3.4` days
- `/opt/medical-audit/backups/app/pre-deploy-replica-workspace-recovery-f3c34ff3-20260706.tar.gz` | `app` | `185328289` bytes | mtime `2026-07-06T09:40:18+0800` | age `3.22` days
- `/opt/medical-audit/backups/env/medical-audit.env.pre-deploy-replica-workspace-recovery-f3c34ff3-20260706` | `env` | `2576` bytes | mtime `2026-07-06T09:40:18+0800` | age `3.22` days
- `/opt/medical-audit/backups/db/pre-deploy-replica-workspace-recovery-f3c34ff3-20260706.sql.gz` | `db` | `4834978447` bytes | mtime `2026-07-06T09:55:50+0800` | age `3.21` days
- `/opt/medical-audit/backups/web/audit-web-pre-deploy-replica-workspace-recovery-f3c34ff3-20260706.tar.gz` | `web` | `631593` bytes | mtime `2026-07-06T09:55:50+0800` | age `3.21` days
- `/opt/medical-audit/backups/nginx/nginx.conf.pre-deploy-replica-workspace-recovery-f3c34ff3-20260706` | `nginx` | `33317` bytes | mtime `2026-07-06T09:55:50+0800` | age `3.21` days
- `/opt/medical-audit/backups/app/pre-deploy-main-edae4567-replica-governance-20260706.tar.gz` | `app` | `185275676` bytes | mtime `2026-07-06T10:58:25+0800` | age `3.16` days
- `/opt/medical-audit/backups/env/medical-audit.env.pre-deploy-main-edae4567-replica-governance-20260706` | `env` | `2576` bytes | mtime `2026-07-06T10:58:25+0800` | age `3.16` days
- `/opt/medical-audit/backups/db/pre-deploy-main-edae4567-replica-governance-20260706.sql.gz` | `db` | `4834979509` bytes | mtime `2026-07-06T11:13:55+0800` | age `3.15` days
- `/opt/medical-audit/backups/web/audit-web-pre-deploy-main-edae4567-replica-governance-20260706.tar.gz` | `web` | `504254` bytes | mtime `2026-07-06T11:13:55+0800` | age `3.15` days
- `/opt/medical-audit/backups/nginx/nginx.conf.pre-deploy-main-edae4567-replica-governance-20260706` | `nginx` | `33317` bytes | mtime `2026-07-06T11:13:55+0800` | age `3.15` days
- `/opt/medical-audit/backups/app/pre-deploy-main-9a73d3b7-backend-connectivity-20260706.tar.gz` | `app` | `185273153` bytes | mtime `2026-07-06T14:00:35+0800` | age `3.04` days
- `/opt/medical-audit/backups/env/medical-audit.env.pre-deploy-main-9a73d3b7-backend-connectivity-20260706` | `env` | `2576` bytes | mtime `2026-07-06T14:00:35+0800` | age `3.04` days
- `/opt/medical-audit/backups/db/pre-deploy-main-9a73d3b7-backend-connectivity-20260706.sql.gz` | `db` | `4834984288` bytes | mtime `2026-07-06T14:16:13+0800` | age `3.03` days
- `/opt/medical-audit/backups/web/audit-web-pre-deploy-main-9a73d3b7-backend-connectivity-20260706.tar.gz` | `web` | `504749` bytes | mtime `2026-07-06T14:16:13+0800` | age `3.03` days
- `/opt/medical-audit/backups/nginx/nginx.conf.pre-deploy-main-9a73d3b7-backend-connectivity-20260706` | `nginx` | `33317` bytes | mtime `2026-07-06T14:16:13+0800` | age `3.03` days
- `/opt/medical-audit/backups/app/pre-deploy-main-58258277-projects-cockpit-20260706.tar.gz` | `app` | `185281510` bytes | mtime `2026-07-06T14:33:53+0800` | age `3.01` days
- `/opt/medical-audit/backups/env/medical-audit.env.pre-deploy-main-58258277-projects-cockpit-20260706` | `env` | `2576` bytes | mtime `2026-07-06T14:33:53+0800` | age `3.01` days

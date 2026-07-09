---
title: medical_audit 生产备份删除执行记录
doc_type: workflow
module: production-governance
status: completed
created: 2026-07-09
updated: 2026-07-09
owner: codex
source: authorized-production-file-delete+production-readonly-postcheck
---

# medical_audit 生产备份删除执行记录

## 执行边界

- 本轮只删除已授权候选备份文件。
- 未部署生产。
- 未写生产数据库。
- 未删除 Docker 容器、镜像、网络或卷。
- 未删除备份根目录外文件、目录或 symlink。

## 删除前状态

- deployment state: `pass`
- deploy SHA: `d6ae4c191453b0e5619d451cb26b41e3aeb68bee`
- issues: `[]`

## 删除执行结果

- candidate_count: `46`
- candidate_bytes: `40549758482`
- deleted_count: `46`
- deleted_bytes: `40549758482`
- remaining_candidate_count: `0`
- disk_delta_free_bytes: `40549924864`

## 删除后验收

- deployment state: `pass`
- deploy SHA unchanged: `True`
- containers healthy after: `True`
- nginx test passed after: `True`
- used_pct_after: `76.33`
- free_bytes_after: `55789010944`

## 删除路径清单

- `/opt/medical-audit/backups/app/pre-deploy-postmerge-main-a7a81da6-20260705.tar.gz` | `185231566` bytes
- `/opt/medical-audit/backups/env/medical-audit.env.pre-deploy-postmerge-main-a7a81da6-20260705` | `2576` bytes
- `/opt/medical-audit/backups/db/pre-deploy-postmerge-main-a7a81da6-20260705.sql.gz` | `4834954411` bytes
- `/opt/medical-audit/backups/web/audit-web-pre-deploy-postmerge-main-a7a81da6-20260705.tar.gz` | `643150` bytes
- `/opt/medical-audit/backups/nginx/nginx.conf.pre-deploy-postmerge-main-a7a81da6-20260705` | `33029` bytes
- `/opt/medical-audit/backups/app/pre-deploy-login-gate-579d3983-20260705T1958.tar.gz` | `198434728` bytes
- `/opt/medical-audit/backups/env/medical-audit.env.pre-deploy-login-gate-579d3983-20260705T1958` | `2576` bytes
- `/opt/medical-audit/backups/db/pre-deploy-login-gate-579d3983-20260705T1958.sql.gz` | `4834957770` bytes
- `/opt/medical-audit/backups/web/audit-web-pre-deploy-login-gate-579d3983-20260705T1958.tar.gz` | `432289` bytes
- `/opt/medical-audit/backups/nginx/nginx.conf.pre-deploy-login-gate-579d3983-20260705T1958` | `33029` bytes
- `/opt/medical-audit/backups/app/pre-deploy-main-65a7ca61-login-gate-20260706.tar.gz` | `185131923` bytes
- `/opt/medical-audit/backups/env/medical-audit.env.pre-deploy-main-65a7ca61-login-gate-20260706` | `2576` bytes
- `/opt/medical-audit/backups/db/pre-deploy-main-65a7ca61-login-gate-20260706.sql.gz` | `4834962238` bytes
- `/opt/medical-audit/backups/web/audit-web-pre-deploy-main-65a7ca61-login-gate-20260706.tar.gz` | `550366` bytes
- `/opt/medical-audit/backups/nginx/nginx.conf.pre-deploy-main-65a7ca61-login-gate-20260706` | `33029` bytes
- `/opt/medical-audit/backups/nginx/nginx.conf.pre-api-v1-prefix-2adee6e4-20260706T022056+0800` | `33029` bytes
- `/opt/medical-audit/backups/app/pre-deploy-legacy-page-retire-docker-b5ad9fce-20260706T030541+0800.tar.gz` | `184818184` bytes
- `/opt/medical-audit/backups/env/medical-audit.env.pre-deploy-legacy-page-retire-docker-b5ad9fce-20260706T030541+0800` | `2576` bytes
- `/opt/medical-audit/backups/db/pre-deploy-legacy-page-retire-docker-b5ad9fce-20260706T030541+0800.sql.gz` | `4834973471` bytes
- `/opt/medical-audit/backups/web/audit-web-pre-deploy-legacy-page-retire-docker-b5ad9fce-20260706T030541+0800.tar.gz` | `637092` bytes
- `/opt/medical-audit/backups/nginx/nginx.conf.pre-legacy-page-retire-nginx-b5ad9fce-20260706T032743+0800` | `33028` bytes
- `/opt/medical-audit/backups/nginx/nginx.conf.pre-deploy-legacy-page-retire-docker-b5ad9fce-20260706T030541+0800` | `33028` bytes
- `/opt/medical-audit/backups/app/pre-deploy-main-65a7ca61-replica-recovery-20260706T0415.tar.gz` | `185292269` bytes
- `/opt/medical-audit/backups/env/medical-audit.env.pre-deploy-main-65a7ca61-replica-recovery-20260706T0415` | `2576` bytes
- `/opt/medical-audit/backups/db/pre-deploy-main-65a7ca61-replica-recovery-20260706T0415.sql.gz` | `4834972882` bytes
- `/opt/medical-audit/backups/web/audit-web-pre-deploy-main-65a7ca61-replica-recovery-20260706T0415.tar.gz` | `629222` bytes
- `/opt/medical-audit/backups/nginx/nginx.conf.pre-deploy-main-65a7ca61-replica-recovery-20260706T0415` | `33317` bytes
- `/opt/medical-audit/backups/app/pre-deploy-release-6178cff1-restore-ui-agents-20260706.tar.gz` | `185038253` bytes
- `/opt/medical-audit/backups/env/medical-audit.env.pre-deploy-release-6178cff1-restore-ui-agents-20260706` | `2576` bytes
- `/opt/medical-audit/backups/app/pre-deploy-replica-workspace-recovery-f3c34ff3-20260706.tar.gz` | `185328289` bytes
- `/opt/medical-audit/backups/env/medical-audit.env.pre-deploy-replica-workspace-recovery-f3c34ff3-20260706` | `2576` bytes
- `/opt/medical-audit/backups/db/pre-deploy-replica-workspace-recovery-f3c34ff3-20260706.sql.gz` | `4834978447` bytes
- `/opt/medical-audit/backups/web/audit-web-pre-deploy-replica-workspace-recovery-f3c34ff3-20260706.tar.gz` | `631593` bytes
- `/opt/medical-audit/backups/nginx/nginx.conf.pre-deploy-replica-workspace-recovery-f3c34ff3-20260706` | `33317` bytes
- `/opt/medical-audit/backups/app/pre-deploy-main-edae4567-replica-governance-20260706.tar.gz` | `185275676` bytes
- `/opt/medical-audit/backups/env/medical-audit.env.pre-deploy-main-edae4567-replica-governance-20260706` | `2576` bytes
- `/opt/medical-audit/backups/db/pre-deploy-main-edae4567-replica-governance-20260706.sql.gz` | `4834979509` bytes
- `/opt/medical-audit/backups/web/audit-web-pre-deploy-main-edae4567-replica-governance-20260706.tar.gz` | `504254` bytes
- `/opt/medical-audit/backups/nginx/nginx.conf.pre-deploy-main-edae4567-replica-governance-20260706` | `33317` bytes
- `/opt/medical-audit/backups/app/pre-deploy-main-9a73d3b7-backend-connectivity-20260706.tar.gz` | `185273153` bytes
- `/opt/medical-audit/backups/env/medical-audit.env.pre-deploy-main-9a73d3b7-backend-connectivity-20260706` | `2576` bytes
- `/opt/medical-audit/backups/db/pre-deploy-main-9a73d3b7-backend-connectivity-20260706.sql.gz` | `4834984288` bytes
- `/opt/medical-audit/backups/web/audit-web-pre-deploy-main-9a73d3b7-backend-connectivity-20260706.tar.gz` | `504749` bytes
- `/opt/medical-audit/backups/nginx/nginx.conf.pre-deploy-main-9a73d3b7-backend-connectivity-20260706` | `33317` bytes
- `/opt/medical-audit/backups/app/pre-deploy-main-58258277-projects-cockpit-20260706.tar.gz` | `185281510` bytes
- `/opt/medical-audit/backups/env/medical-audit.env.pre-deploy-main-58258277-projects-cockpit-20260706` | `2576` bytes

---
title: 腾讯云 AuditScope 知识库网站部署工作流
doc_type: workflow
module: deployment
topic: tencent-cloud-audit-lute-tlz-dddd
status: stable
created: 2026-06-03
updated: 2026-06-17
owner: self
source: human+ai
---

# 腾讯云 AuditScope 知识库网站部署工作流

## 1. 目标

将当前知识库网站部署到腾讯云轻量服务器：

- 服务器：`101.34.52.232`
- 主机名：`VM-0-16-ubuntu`
- 用户：`ubuntu`
- 域名：`audit.lute-tlz-dddd.top`
- 应用：`AuditScope 医保审核对话审证台`

部署边界：

- 新建独立 Docker Compose project：`medical-audit`。
- 新建独立 PostgreSQL/pgvector：`medical_audit_pg`。
- 新建独立 Docker volume：`medical_audit_pgdata`。
- 新建独立内部网络：`medical_audit_internal`。
- 不复用 `voc_bi_pg`、`promptforge_mysql` 或 AI Video 数据库。
- 不占用公网 `80/443` 端口；公网入口继续由现有 `ai_video_nginx` 统一接入。

## 2. 当前服务器事实

### 2026-06-17 PR #121 下载元信息部署后当前事实

- PR #117 `codex/personal-material-cos-production-readiness` 已合并到 `main` 并完成生产部署，生产部署 SHA 为 `a276eeb2cd9018ebac52193103d17f476dbe96a6`。
- PR #117 部署戳：`cos-sdk-local-provider-20260617`；远端已生成 `app`、`env`、`db`、`nginx` 和 `web` 备份。
- PR #118 `codex/production-dotgit-cleanup` 和 PR #119 `codex/cos-production-state-doc-sync` 已合并到 `main`；`main@936d50afcfa40ee350fa66ebc9a7cf596a5d1c7b` 曾使用部署戳 `main-936d50af-dotgit-doc-sync-20260617` 轻量同步到生产。
- PR #121 `codex/document-download-access-metadata` 已合并到 `main`，业务部署基线 SHA 为 `e62254bb5f3f142d33fdbca28d0274332f52ec90`。
- PR #122 `codex/pr121-download-metadata-state-doc-sync` 已合并到 `main`，merge commit 为 `65fc07462fbae73e3b53a41ca797b7c6e170cbce`；该提交为 docs-only 状态同步，不代表业务运行代码变更。
- `main@e62254bb5f3f142d33fdbca28d0274332f52ec90` 已使用部署戳 `pr121-download-metadata-20260617` 发布到生产；本次重建并重启 `medical_audit_app` 容器。
- 本次部署脚本在远端 DB 备份落盘后出现本地 SSH 子进程未退出的残余脆弱点；已人工中断卡住的部署脚本，并按部署脚本顺序手工完成远端同步清理、应用 rsync、静态目录 rsync、`.deploy-sha` 写入、`docker compose build app`、`docker compose up -d app`、健康检查、生产 smoke 和部署状态审计。
- 部署后将 active env 从默认 local provider 切到 `MEDICAL_AUDIT_DOCUMENT_STORAGE_PROVIDER=tencent-cos`，切换前 env 备份为 `/opt/medical-audit/backups/env/medical-audit.env.pre-cos-provider-switch-20260617T163741`。
- 当前生产业务部署标记 SHA：`e62254bb5f3f142d33fdbca28d0274332f52ec90`，远端文件 `/opt/medical-audit/app/.deploy-sha` 已核验。
- 最新已核验 GitHub `main` docs-only merge commit：`65fc07462fbae73e3b53a41ca797b7c6e170cbce`；生产 `.deploy-sha` 保持在 #121 业务部署 SHA，未因 #122 docs-only 合并执行生产轻量同步。
- 当前生产配置：`MEDICAL_AUDIT_DOCUMENT_STORAGE_PROVIDER=tencent-cos`、COS region 为 `ap-guangzhou`、`MEDICAL_AUDIT_DOCUMENT_STORAGE_COS_SDK_BOOTSTRAP=1`、`MEDICAL_AUDIT_DOCUMENT_STORAGE_RECORD_OBJECTS=1`。
- `medical_audit_app` 容器 `running` 且 `health=healthy`；`medical_audit_pg` 容器 `running` 且 `health=healthy`。
- 当前生产检索后端为 PostgreSQL：`backend=postgres`、`ready=true`、`matching_embedding_count=49051`、`embedding_model=kimi-for-coding`。
- COS 写入型 E2E 已执行两次：容器内直连 `/documents/uploads` 写入 `document-upload-73805d5ac457`，公网 `/api/v1/documents/uploads` 写入 `document-upload-6ee427e0fd91`。
- 两次 COS 写入均已验证 DB `document_upload_records` 增量、`document_storage_objects` 增量、`provider=tencent-cos`、bucket `medical-audit-personal-materials-1304185125`、region `ap-guangzhou`、`storage_status=object-stored`、`encryption_mode=sse-cos`、COS `HEAD` 成功，以及上传人可读、其他普通 `auditor` 不可见、`department-head` 可读全部的权限边界。
- COS 写入后最新只读复核报告 `tmp/outputs/production-documents-cos-readonly-after-main-936d50af-deploy-20260617.json` 为 `status=pass`，两条既有写入记录 COS `HEAD` 均通过，容器本地文件均不存在。
- 下载元信息生产只读 E2E 报告 `tmp/outputs/production-documents-download-metadata-readonly-after-pr121-20260617.json` 为 `status=pass`；既有 COS 上传 `document-upload-73805d5ac457` 的 owner 返回 `200/access_scope=owner`，其他普通 `auditor` 返回 `404`，`department-head` 返回 `200/access_scope=read-all`，响应保持 `metadata-only` 且 `signed_url=null`。
- `main@e62254bb` 部署后状态巡检 `tmp/outputs/tencent-cloud-deployment-state-after-pr121-download-metadata-20260617.json` 为 `status=pass`，`issues=[]`。
- `main@e62254bb` 部署后生产 smoke `tmp/outputs/production-e2e-smoke-after-pr121-download-metadata-20260617.json` 为 `status=pass`。
- PR #118 `codex/production-dotgit-cleanup` 已合并并随 `main@936d50af` 轻量部署；部署脚本现在同时排除 `.git` 文件和 `.git/` 目录，并在远端同步清理阶段仅删除 app 根目录 `.git` 单文件。
- 生产侧已备份并删除历史残留 `/opt/medical-audit/app/.git` 单文件，备份路径为 `/opt/medical-audit/backups/app/remote-dotgit-file-pre-cleanup-20260617T165949`；清理后 `git rev-parse HEAD` 返回标准非 Git 仓库错误，不再指向本机 worktree。
- 清理后部署状态巡检 `tmp/outputs/tencent-cloud-deployment-state-after-dotgit-cleanup-20260617.json` 为 `status=pass`，`issues=[]`；随后 `main@e62254bb` 部署状态巡检继续为 `status=pass`。
- 证据边界：本轮证明个人材料上传对象已进入腾讯云 COS，生产部署目录不再残留本机 worktree Git 指针，生产 `.deploy-sha` 与 #121 业务部署 SHA 对齐，且下载元信息授权隔离可用；#122 是 docs-only 状态同步，不触发业务部署。不等于完成生产级病毒扫描、DLP/脱敏改写、真实文件下载交付、签名 URL、真实登录会话、个人材料实际入索引或长期存储生命周期策略。部署脚本备份阶段 SSH 退出仍存在脆弱点。

### 2026-06-17 个人材料对象记录元数据部署后历史事实

- PR #108 `codex/personal-material-storage-schema-gate` 已合并到 `main` 并完成生产部署，merge commit 为 `c7e54e04b4584ee394a9f428f3de13d7c70519b9`。
- PR #108 使用 `--apply-schema` 部署，生产创建 `document_storage_objects` 表及索引；当时生产 `.deploy-sha=c7e54e04b4584ee394a9f428f3de13d7c70519b9`，但 `MEDICAL_AUDIT_DOCUMENT_STORAGE_RECORD_OBJECTS` 初始仍保持关闭。
- PR #108 部署后普通生产 smoke `tmp/outputs/production-e2e-smoke-after-pr108-schema-gate-deploy-20260617.json` 为 `status=pass`；部署状态审计 `tmp/outputs/tencent-cloud-deployment-state-after-pr108-schema-gate-20260617.json` 为 `status=pass`。
- 打开 `MEDICAL_AUDIT_DOCUMENT_STORAGE_RECORD_OBJECTS` 后，首次 `/documents` 真实上传触发 `500`，报告为 `tmp/outputs/production-documents-storage-record-e2e-20260617.json`。根因是 `document_storage_objects` 与 `document_upload_records` 只有外键字段、没有 ORM relationship，flush 顺序可能先插入对象记录再插入上传记录，导致 FK violation。
- PR #109 `codex/document-storage-fk-flush-fix` 已合并到 `main` 并完成生产部署，merge commit 为 `6296cd504157171a1b212210dfe9bde1aa46b5a3`。
- 当时生产部署 SHA：`6296cd504157171a1b212210dfe9bde1aa46b5a3`，远端文件 `/opt/medical-audit/app/.deploy-sha` 已核验。
- PR #109 部署戳：`pr109-document-storage-fk-fix-20260617`；部署后普通生产 smoke `tmp/outputs/production-e2e-smoke-after-pr109-document-storage-fk-fix-deploy-20260617.json` 为 `status=pass`；部署状态审计 `tmp/outputs/tencent-cloud-deployment-state-after-pr109-document-storage-fk-fix-20260617.json` 为 `status=pass`。
- 当时生产配置：`MEDICAL_AUDIT_DOCUMENT_STORAGE_RECORD_OBJECTS=1`；`medical_audit_app` 容器 `running` 且 `health=healthy`，`medical_audit_pg` 容器 `running` 且 `health=healthy`。
- 当时生产检索后端为 PostgreSQL：`backend=postgres`、`ready=true`、`matching_embedding_count=49051`、`embedding_model=kimi-for-coding`。
- 生产 `/documents` 对象记录写入型 E2E 报告 `tmp/outputs/production-documents-storage-record-e2e-after-pr109-20260617.json` 为 `status=pass`；上传记录 `document-upload-25f283a6346e` 已写入 `document_upload_records`，对应本地对象记录已写入 `document_storage_objects`。
- 本轮写入文件：`production-documents-storage-record-e2e-after-pr109-20260617T1011.txt`；宿主机留存路径为 `/opt/medical-audit/document-uploads/2026/06/17/document-upload-25f283a6346e.txt`，`sha256=5a3a4fb1bb03506d1b95825d2f141b0cc05279a3f5653642f022d6bd945fa5e1`。
- 写入后数据库计数已核验：`document_upload_records=7`、`document_storage_objects=1`；上传人、其他普通审计员和管理员读取边界仍按预期生效。
- 首次失败上传遗留孤儿文件 `/opt/medical-audit/document-uploads/2026/06/17/document-upload-51043ab42e46.txt` 已确认在 `document_upload_records` 和 `document_storage_objects` 中均无记录；删除前已备份到 `/opt/medical-audit/backups/orphan-document-uploads/20260617/document-upload-51043ab42e46.txt.pre-delete`，备份 `sha256=89c0fee5185dbd1a42df6ae89165854f96a6f2c41d676c4cea796ac258027b3f`，原文件已删除，删除后 DB 行仍为 `0,0`。
- 证据边界：PR #109 本轮只证明个人材料本地对象记录元数据、schema gate、FK flush 顺序、对象记录写入和孤儿文件清理闭环；当时不等于完成腾讯云 COS/外部对象存储、生产级病毒扫描、DLP/脱敏改写、下载权限隔离、真实登录会话、个人材料实际入索引或长期存储生命周期策略。个人材料腾讯云 COS 对象存储在后续 PR #117 已单独完成生产启用和公网写入验收。

### 2026-06-17 COS 生产启用前置历史只读核验

- PR #116 `codex/personal-material-cos-preflight` 已合并到 `main`，merge commit 为 `f06013c21ddc9e858a2ac9cd1747bfcf79c82bbe`；该提交只新增本地 COS bootstrap preflight，不代表生产已部署或启用 COS。
- 当时生产部署 SHA 仍为 `6296cd504157171a1b212210dfe9bde1aa46b5a3`；`medical_audit_app` 和 `medical_audit_pg` 均为 `healthy`，后端 `/health` 返回 `status=ok`。
- 当时生产容器未配置 COS：`MEDICAL_AUDIT_DOCUMENT_STORAGE_PROVIDER`、COS bucket、COS region、COS secret env name 和 `MEDICAL_AUDIT_DOCUMENT_STORAGE_COS_SDK_BOOTSTRAP` 均未在运行容器中设置；容器内 YAML `document_storage={}`。
- 当时生产镜像中 `qcloud_cos` 不可用；这是 PR #116 后、PR #117 前的历史事实，不是当前运行态。
- 证据边界：本次只读核验只证明生产仍为 local storage 和未安装 COS SDK；未修改远端 env，未部署，未上传 COS object，未执行 `/documents` 生产写入型 E2E。

### 2026-06-16 个人材料入索引审批状态机部署后历史事实

- PR #103 `codex/document-upload-index-readiness-state-machine` 已合并到 `main` 并完成生产部署，merge commit 为 `b425e2123d55a94dc6b6c800b806384eec1de679`。
- 当时生产部署 SHA：`b425e2123d55a94dc6b6c800b806384eec1de679`，远端文件 `/opt/medical-audit/app/.deploy-sha` 已核验。
- 本轮部署戳：`pr103-index-readiness-20260616`；远端已生成 `app`、`env`、`db`、`nginx` 和 `web` 备份。
- 写入前 DB 备份：`/opt/medical-audit/backups/db/pre-deploy-pr103-index-readiness-20260616.sql.gz`，大小约 `979M`。
- 应用备份：`/opt/medical-audit/backups/app/pre-deploy-pr103-index-readiness-20260616.tar.gz`，大小约 `176M`。
- Web 静态资产备份：`/opt/medical-audit/backups/web/audit-web-pre-deploy-pr103-index-readiness-20260616.tar.gz`，大小约 `430K`。
- `medical_audit_app` 容器 `running` 且 `health=healthy`；`medical_audit_pg` 容器 `running` 且 `health=healthy`。
- 共享入口 `ai_video_nginx` 仍由 `lighthouse` Compose project 管理，`/var/www/audit` bind mount 存在且为只读，Nginx 配置测试通过。
- 当时生产检索后端为 PostgreSQL：`backend=postgres`、`ready=true`、`matching_embedding_count=49051`、`embedding_model=kimi-for-coding`。
- 部署脚本内普通生产 smoke 报告 `tmp/outputs/production-e2e-smoke-after-pr103-index-readiness-deploy-20260616.json` 为 `status=pass`。
- 部署后状态审计报告 `tmp/outputs/tencent-cloud-deployment-state-after-pr103-index-readiness-deploy-20260616.json` 为 `status=pass`，`issues=[]`。
- 生产 `/documents` 入索引审批写入型 E2E 报告 `tmp/outputs/production-documents-index-readiness-e2e-pr103-20260616.json` 为 `status=pass`；记录 `document-upload-29e6f19736ed` 的人工审批通过路径和 `document-upload-da1a475b381b` 的人工驳回路径均已写入 PostgreSQL，并验证宿主机留存文件 `sha256` 与 DB 一致。
- 写入型 E2E 已验证普通审计员只能读取本人上传、其它审计员不可见、管理员可读全部个人上传；普通 `auditor` 调用人工审批接口返回 `403` 并记录 `document-upload-index-approval-access-denied`。
- 人工审批通过路径已验证：`department-head` 可将 `manual-index-approval` check 置为 `passed` 并清除人工审批 blocker；由于生产病毒扫描和 DLP provider 当前仍为 `unconfigured`，整体 `index_readiness.status` 仍为 `blocked`，剩余 blockers 为 `virus-scan-required`、`dlp-review-required`。
- 人工驳回路径已验证：`department-head` 可将 `manual-index-approval` check 置为 `blocked`，blocker 为 `manual-index-approval-rejected`，整体 `index_readiness.status=rejected`、`next_action=review-manual-index-rejection`。
- 审计日志已验证：`document-upload-index-readiness-update` 和 `document-upload-index-approval-access-denied` 均按 `entity_type=document-upload`、`entity_id=<upload_id>` 落库。
- 证据边界：本轮只证明个人材料人工入索引审批状态机、审批拒绝权限边界、审计日志和持久化状态更新可用；不等于完成生产级病毒扫描、DLP/脱敏改写、对象存储、下载权限隔离、真实登录会话、个人材料实际入索引或长期存储生命周期策略。

### 2026-06-16 个人材料上传治理 provider 配置部署后历史事实

- PR #101 `codex/document-upload-governance-provider-config` 已合并到 `main` 并完成生产部署，merge commit 为 `6302f0a8baeb5695861f9682090f65786ea6d6e0`。
- 当时生产部署 SHA：`6302f0a8baeb5695861f9682090f65786ea6d6e0`，远端文件 `/opt/medical-audit/app/.deploy-sha` 已核验。
- 本轮部署戳：`20260616T135218+0800`；远端已生成 `app`、`env`、`db`、`nginx` 和 `web` 备份。
- 写入前 DB 备份：`/opt/medical-audit/backups/db/pre-deploy-20260616T135218+0800.sql.gz`，`gzip -t` 已通过，大小约 `979M`。
- 应用备份：`/opt/medical-audit/backups/app/pre-deploy-20260616T135218+0800.tar.gz`，`gzip -t` 已通过，大小约 `176M`。
- Web 静态资产备份：`/opt/medical-audit/backups/web/audit-web-pre-deploy-20260616T135218+0800.tar.gz`，`gzip -t` 已通过，大小约 `430K`。
- `medical_audit_app` 容器 `running` 且 `health=healthy`；`medical_audit_pg` 容器 `running` 且 `health=healthy`。
- 当时生产检索后端为 PostgreSQL：`backend=postgres`、`ready=true`、`matching_embedding_count=49051`、`embedding_model=kimi-for-coding`。
- 部署脚本内普通生产 smoke 报告 `tmp/outputs/production-e2e-smoke-after-deploy-20260616T135218+0800.json` 为 `status=pass`。
- 生产 `/documents` 写入型 E2E verified 报告 `tmp/outputs/production-documents-write-e2e-20260616T135913+0800-verified.json` 为 `status=pass`；记录 `document-upload-f81adf853774` 已写入 PostgreSQL，并留存在 `/opt/medical-audit/document-uploads/2026/06/16/document-upload-f81adf853774.txt`，文件 `sha256=90639f5b2a37ab3ec322067059e1f27034dcb4cd51b76794221694414e93d39e`。
- 写入型 E2E 已验证普通审计员只能读取本人上传、其它审计员不可见、管理员可读全部个人上传；上传记录当前 `retention_status=retained`、`index_status=not-indexed`。
- 新增 `index_readiness` 治理门禁已在生产响应和 DB `metadata` 中验证：默认 `unconfigured` 病毒扫描、默认 `unconfigured` DLP 审查和人工入索引审批均返回 `blocked`，blockers 为 `virus-scan-required`、`dlp-review-required`、`manual-index-approval-required`。
- 本轮首次 `/documents` 写入型 E2E 报告 `tmp/outputs/production-documents-write-e2e-20260616T135913+0800.json` 的失败原因为校验脚本 DB 查询返回空结果；API 写入、权限隔离实际成功，已由 `*-verified.json` 中的显式 psql 查询、宿主机文件和 `sha256` 校验覆盖。
- 证据边界：本轮只证明个人材料上传治理 provider 配置层、默认 blocked 门禁表达、个人材料留存和角色读取隔离可用；不等于完成生产级病毒扫描、DLP/脱敏改写、对象存储、下载权限隔离、真实登录会话、个人材料实际入索引或长期存储生命周期策略。

### 2026-06-16 部署脚本 SSH stdin 修复部署后历史事实

- PR #95 `codex/deploy-tooling-debt-fix` 已合并到 `main`，merge commit 为 `8281a0ea123cbbd5df519e20fd5c4cdf77b87e30`；生产部署验证失败，原因是 `docker exec -i ... pg_dump` 改法仍会导致本地 SSH 在 DB 备份完成后挂起，生产 `.deploy-sha` 未更新。
- PR #96 `codex/deploy-pgdump-stdin-fix` 已合并到 `main`，merge commit 为 `33522d24983b188587feed3b9a45cad066c87b4a`；生产部署验证失败，原因是 plain `docker exec ... pg_dump` 仍无法阻断远端脚本消耗 SSH stdin 后导致的本地挂起，生产 `.deploy-sha` 未更新。
- PR #97 `codex/deploy-ssh-stdin-fix` 已合并到 `main` 并完成生产部署，merge commit 为 `4901d6705a60494542f42b98aa0e6766e3224114`。
- 当时生产部署 SHA：`4901d6705a60494542f42b98aa0e6766e3224114`，远端文件 `/opt/medical-audit/app/.deploy-sha` 已核验。
- 有效修复点：部署脚本中远端脚本式 `_ssh` 调用统一使用 `ssh -n` 断开本地 stdin；`rsync` 传输调用保持不加 `-n`。
- 本轮部署戳：`ssh-stdin-fix-20260616`；远端已生成 `app`、`env`、`db`、`nginx` 和 `web` 备份。
- 写入前 DB 备份：`/opt/medical-audit/backups/db/pre-deploy-ssh-stdin-fix-20260616.sql.gz`，`gzip -t` 已通过，大小约 `979M`。
- 应用备份：`/opt/medical-audit/backups/app/pre-deploy-ssh-stdin-fix-20260616.tar.gz`，大小约 `176M`。
- Web 静态资产备份：`/opt/medical-audit/backups/web/audit-web-pre-deploy-ssh-stdin-fix-20260616.tar.gz`，大小约 `430K`。
- `medical_audit_app` 容器 `running` 且 `health=healthy`；`medical_audit_pg` 容器 `running` 且 `health=healthy`。
- 共享入口 `ai_video_nginx` 仍由 `lighthouse` Compose project 管理，Nginx 配置测试通过。
- 当时生产检索后端为 PostgreSQL：`backend=postgres`、`ready=true`、`matching_embedding_count=49051`、`embedding_model=kimi-for-coding`。
- 部署脚本内普通生产 smoke 报告 `tmp/outputs/production-e2e-smoke-after-ssh-stdin-fix-deploy-20260616.json` 为 `status=pass`。
- 部署后状态审计报告 `tmp/outputs/tencent-cloud-deployment-state-after-ssh-stdin-fix-deploy-20260616.json` 为 `status=pass`，`issues=[]`，`.deploy-sha=4901d6705a60494542f42b98aa0e6766e3224114`。
- 生产前端验收报告 `tmp/outputs/production-frontend-acceptance-after-ssh-stdin-fix-deploy-20260616.json` 为 `status=pass`，覆盖 `21` 个路由、`42` 个检查，`p0=[]`、`p1=[]`。
- 证据边界：本轮只证明部署脚本不再在 DB 备份完成后挂起，并且生产已更新到 PR #97；不改变产品功能范围、真实登录会话、数据库 schema、生产 env、Nginx 配置或既有业务数据，除部署备份和既有 smoke/验收日志外不引入新的业务写入结论。

### 2026-06-15 权限上下文兼容层部署后历史事实

- PR #94 `codex/auth-rbac-phase-a` 已合并到 `main` 并部署到生产。
- 当时生产部署 SHA：`bebcf57043197ff45dfff1185e071a1cf2d7d808`，远端文件 `/opt/medical-audit/app/.deploy-sha` 已核验。
- 本轮部署戳：`auth-rbac-phase-a-20260615`；远端已生成 `app`、`env`、`db`、`nginx` 和 `web` 备份。
- 写入前 DB 备份：`/opt/medical-audit/backups/db/pre-deploy-auth-rbac-phase-a-20260615.sql.gz`，大小约 `979M`。
- `medical_audit_app` 容器 `running` 且 `health=healthy`；`medical_audit_pg` 容器 `running` 且 `health=healthy`。
- 共享入口 `ai_video_nginx` 仍由 `lighthouse` Compose project 管理，`/var/www/audit` bind mount 存在且为只读；Nginx 配置测试通过。
- 当时生产检索后端为 PostgreSQL：`backend=postgres`、`ready=true`、`matching_embedding_count=49051`、`embedding_model=kimi-for-coding`。
- 部署脚本内普通生产 smoke 报告 `tmp/outputs/production-e2e-smoke-after-auth-rbac-phase-a-deploy-20260615.json` 为 `status=pass`。
- 部署后状态审计报告 `tmp/outputs/tencent-cloud-deployment-state-after-auth-rbac-phase-a-deploy-20260615.json` 为 `status=pass`，`issues=[]`。
- 生产前端验收报告 `tmp/outputs/production-frontend-acceptance-after-auth-rbac-phase-a-deploy-20260615.json` 为 `status=pass`，覆盖 `21` 个路由、`42` 个检查，`p0_count=0`、`p1_count=0`。
- 专项 RBAC smoke 报告 `tmp/outputs/production-auth-rbac-phase-a-smoke-20260615.json` 为 `status=pass`；已验证旧 `X-Role: it-admin` 兼容映射为 `system-admin`，新 `X-Role: system-admin` 可读治理日志，未授权审计日志访问返回 `403`。
- 专项 RBAC smoke 已验证 `auditor` 写 `/api/v1/index/versions/activate` 返回 `403`，`guest` 写 `/api/v1/agents` 和 `/api/v1/projects/SELF-CHECK-FUND-20260607/members` 返回 `403`，并均可在持久化审计日志中查到 `auth_source=legacy-header`、`normalized_role` 和 `attempted_action`。
- `ai_video.pem` 仍保留在项目本地用于 SSH；禁止删除，禁止提交到 Git。
- 证据边界：本轮只证明 legacy header 权限上下文兼容层和关键写接口拒绝审计链路，不等于完成真实登录会话、组织/科室级授权、会话态前端切换或全站细粒度 RBAC。

### 2026-06-15 门户配置写入拒绝审计部署后历史事实

- PR #90 `codex/portal-config-write-denial-audit` 已合并到 `main` 并部署到生产。
- 当时生产部署 SHA：`6ae514cf994ff0d0da612d5ea9bcce82bb7df1bc`，远端文件 `/opt/medical-audit/app/.deploy-sha` 已核验。
- 本轮部署戳：`portal-config-denial-audit-20260615`；远端已生成 `app`、`env`、`db`、`nginx` 和 `web` 备份。
- 写入前 DB 备份：`/opt/medical-audit/backups/db/pre-deploy-portal-config-denial-audit-20260615.sql.gz`，大小 `1025903476` bytes。
- `medical_audit_app` 容器 `running` 且 `health=healthy`；`medical_audit_pg` 容器 `running` 且 `health=healthy`。
- 共享入口 `ai_video_nginx` 仍由 `lighthouse` Compose project 管理，`/var/www/audit` bind mount 存在且为只读；Nginx 配置测试通过。
- 当时生产检索后端为 PostgreSQL：`backend=postgres`、`ready=true`、`matching_embedding_count=49051`、`embedding_model=kimi-for-coding`。
- 部署脚本内普通生产 smoke 报告 `tmp/outputs/production-e2e-smoke-after-portal-config-denial-deploy-20260615.json` 为 `status=pass`。
- 部署后状态审计报告 `tmp/outputs/tencent-cloud-deployment-state-after-portal-config-denial-deploy-20260615.json` 为 `status=pass`，`issues=[]`。
- 生产前端验收报告 `tmp/outputs/production-frontend-acceptance-after-portal-config-denial-deploy-20260615.json` 为 `status=pass`，覆盖 `21` 个路由、`42` 个检查，`p0_count=0`、`p1_count=0`。
- 专项权限 smoke 报告 `tmp/outputs/production-portal-config-denial-audit-smoke-20260615.json` 为 `status=pass`；用户 `portal-config-denial-e2e-20260615T122012Z` 使用 `X-Role: guest` 写 `/api/v1/agents` 和 `/api/v1/projects/SELF-CHECK-FUND-20260607/members` 均返回 `403 role is not allowed`。
- 管理员角色查询持久化审计日志时，`agent-access-denied` 和 `project-member-access-denied` 均返回 `matching_count=1`，store 为 `SqlAlchemyAuditLogStore`。
- `ai_video.pem` 仍保留在项目本地用于 SSH；禁止删除，禁止提交到 Git。
- 证据边界：本轮只证明门户配置写接口未知角色拒绝审计落库，不等于完成真实登录会话、科室级授权、组织模型、全站 RBAC 或生产 no-fallback 生成模型能力。

### 2026-06-15 文档检索边界能力部署与国家规章增量激活历史事实

- PR #83 `codex/documents-boundary-tasks` 已合并到 `main` 并部署到生产。
- 当时生产部署 SHA：`f864e370abd7309f6222376074b45ef2bc6c0ff4`，远端文件 `/opt/medical-audit/app/.deploy-sha` 已核验。
- 本轮部署戳：`20260615T121812+0800`；远端已生成 `app`、`env`、`db`、`nginx` 和 `web` 备份。
- 写入前 DB 备份：`/opt/medical-audit/backups/db/pre-deploy-20260615T121812+0800.sql.gz`，大小 `512967344` bytes。
- `medical_audit_app` 容器 `running` 且 `health=healthy`；`medical_audit_pg` 容器 `running` 且 `health=healthy`。
- 共享入口 `ai_video_nginx` 仍由 `lighthouse` Compose project 管理，`/var/www/audit` bind mount 存在且为只读；Nginx 配置测试通过。
- 当时生产检索后端为 PostgreSQL：`backend=postgres`、`ready=true`、`matching_embedding_count=49051`、`embedding_model=kimi-for-coding`。
- 生产已应用 `document_upload_records` 表和索引；个人文档留存目录 `/opt/medical-audit/document-uploads` 已创建并挂载到应用容器。
- 部署脚本内普通生产 smoke 报告 `tmp/outputs/production-e2e-smoke-after-deploy-20260615T121812+0800.json` 为 `status=pass`。
- 部署后状态审计报告 `tmp/outputs/tencent-cloud-deployment-state-after-documents-boundary-deploy-20260615.json` 为 `status=pass`，`issues=[]`。
- 生产前端验收报告 `tmp/outputs/production-frontend-acceptance-after-documents-boundary-deploy-20260615.json` 为 `status=pass`，覆盖 `21` 个路由、`42` 个检查，`p0_count=0`、`p1_count=0`。
- 生产 `/documents` 写入型 E2E 报告 `tmp/outputs/production-documents-write-e2e-20260615T122620+0800-verified.json` 为 `status=pass`；记录 `document-upload-1ba9d6e00cb7` 已写入 PostgreSQL，并留存在 `/opt/medical-audit/document-uploads/2026/06/15/document-upload-1ba9d6e00cb7.txt`，文件 `sha256=88fe90530c937d6ea6b534dafff636d5b7dec15b7c1131d786e5f00b007b466e`。
- 写入型 E2E 已验证普通审计员只能读取本人上传、其它审计员不可见、管理员可读全部个人上传；上传记录当前 `retention_status=retained`、`index_status=not-indexed`。
- `/api/v1/query` 已验证 `source_collection` 在 `citations` 与 `basis_groups.items` 中直接回显；生产响应仍为 `fallback_used=true`，只证明引用型 fallback 和来源过滤链路健康。
- 早先 `production-documents-write-e2e-20260615T122322+0800.json`、`20260615T122459+0800.json` 和 `20260615T122620+0800.json` 的失败原因为检查脚本 SQL quoting 问题；API 写入实际成功，已由 `*-verified.json` 中的显式 DB 行、宿主机文件和权限隔离检查覆盖。
- `ai_video.pem` 仍保留在项目本地用于 SSH；禁止删除，禁止提交到 Git。

- 2026-06-15 国家规章平台文档增量资料已完成生产激活，未执行代码重新部署；远端 `.deploy-sha` 仍为 `f864e370abd7309f6222376074b45ef2bc6c0ff4`。
- 当前 active index 为 `incremental-20260615-national-regulation-stable-20260615103344`，source package 为 `source-package-national-regulation-stable-incremental-20260615103344`。
- 当时生产检索后端为 PostgreSQL：`backend=postgres`、`ready=true`、`matching_embedding_count=49051`、`embedding_model=kimi-for-coding`、`embedding_dimension=1024`。
- 当前生产库索引版本状态为 `active=1`、`inactive=3`；active 计数为 `source_documents=503`、`document_chunks=49051`、`chunk_embeddings=49051`。
- 本次新增国家规章平台入库文档 `17` 个、新增 chunks `66` 个；第一次全量重建候选 `full-rebuild-20260615093424` 因固定 52 case 回归为 `51/52` 未激活，并已置为 `inactive`。
- 激活后固定 52 case 检索评测、6 case 新增文档检索评测、4 case 新增文档答案评测均通过；生产 E2E 报告 `tmp/outputs/production-e2e-smoke-after-national-regulation-app-restart-20260615.json` 为 `status=pass`。
- 激活后 `/pages/chat` 曾因运行中 `uvicorn` 子进程持有旧导入路径返回 `500`，日志为 `TemplateNotFound: chat.html`；已仅重启 `medical_audit_app` 修复，未重建或修改 `medical_audit_pg`、`medical_audit_pgdata` 或共享 `ai_video_nginx`。
- 重启后 `/pages/chat` 内外网均返回 `200`，重启后日志未再出现 `TemplateNotFound`。

### 2026-06-15 AI 数据分析留存历史部署后历史事实

- PR #79 `codex/analytics-upload-retention-history` 已合并到 `main` 并部署到生产。
- PR #79 当时部署后生产 SHA：`cbd93324119b28a7097712ea7b50b2d96b72de31`，远端文件 `/opt/medical-audit/app/.deploy-sha` 当时已核验。
- 本轮部署戳：`analytics-retention-20260615`；远端已生成 `app`、`env`、`db`、`nginx` 和 `web` 备份。
- 写入前 DB 备份：`/opt/medical-audit/backups/db/pre-deploy-analytics-retention-20260615.sql.gz`，`gzip -t` 通过，大小 `512961688` bytes，`sha256=876bb9ecc1a0a39aa23085688c613000ca44dc4133b428ab2fdb3cb26d66f68d`。
- `medical_audit_app` 容器 `running` 且 `health=healthy`；`medical_audit_pg` 容器 `running` 且 `health=healthy`。
- 共享入口 `ai_video_nginx` 仍由 `lighthouse` Compose project 管理，`/var/www/audit` bind mount 存在且为只读；Nginx 配置测试通过。
- PR #79 当时生产检索后端为 PostgreSQL：`backend=postgres`、`ready=true`、`matching_embedding_count=48985`、`embedding_model=kimi-for-coding`。
- 生产已应用 `analytics_upload_records` 表和索引；上传留存目录 `/opt/medical-audit/analytics-uploads` 已创建，宿主机目录权限为 `ubuntu:ubuntu 775`。
- 部署脚本内普通生产 smoke 报告 `tmp/outputs/production-e2e-smoke-after-analytics-retention-deploy-20260615.json` 为 `status=pass`。
- 部署后状态审计报告 `tmp/outputs/tencent-cloud-deployment-state-after-analytics-retention-deploy-20260615.json` 为 `status=pass`，`issues=[]`。
- 生产前端验收报告 `tmp/outputs/production-frontend-acceptance-after-analytics-retention-deploy-20260615.json` 为 `status=pass`，`p0_count=0`、`p1_count=0`。
- 生产 API 上传留存写入报告 `tmp/outputs/production-analytics-retention-write-e2e-20260615.json` 为 `status=pass`；记录 `analytics-upload-b3a1898e38d1` 已写入 PostgreSQL，并留存在 `/opt/medical-audit/analytics-uploads/2026/06/15/analytics-upload-b3a1898e38d1.csv`。
- 生产 UI 上传联调报告 `tmp/outputs/production-analytics-ui-upload-retention-e2e-20260615.json` 为 `status=pass`；页面上传 `production-analytics-ui-upload-retention-20260615.csv` 后最新历史记录为 `analytics-upload-f39d652d3f81`，`retention_status=retained`，DB 和宿主机文件 `sha256` 校验一致。
- 运维观察项：留存文件由容器写出后在宿主机呈现为 `root:root 644`，功能和读取不受影响，但后续人工清理需要 sudo 或补充容器用户/文件权限治理。
- `ai_video.pem` 仍保留在项目本地用于 SSH；禁止删除，禁止提交到 Git。

### 2026-06-14 PR #73 部署后历史事实

- PR #73 `接入答案生成 provider 并强化 no-fallback 生产门禁` 已合并到 `main` 并部署到生产。
- 当时部署后生产 SHA：`281981ce072b549ebbcc4332db6d5ae1a06801e5`，远端文件 `/opt/medical-audit/app/.deploy-sha` 已核验。
- 本轮部署戳：`pr73-answer-gate-20260614`；远端已生成 `app`、`env`、`db`、`nginx` 和 `web` 备份。
- `medical_audit_app` 容器 `running` 且 `health=healthy`；`medical_audit_pg` 容器 `running` 且 `health=healthy`。
- 共享入口 `ai_video_nginx` 仍由 `lighthouse` Compose project 管理，`/var/www/audit` bind mount 存在且为只读；Nginx 配置测试通过。
- 生产检索后端仍为 PostgreSQL：`backend=postgres`、`ready=true`、`matching_embedding_count=48985`、`embedding_model=kimi-for-coding`。
- 部署脚本内普通生产 smoke 报告 `tmp/outputs/production-e2e-smoke-after-pr73-answer-gate-deploy-20260614.json` 为 `status=pass`。
- 部署后普通生产 smoke 复核报告 `tmp/outputs/production-e2e-smoke-after-pr73-answer-gate-deploy-verification-retry-20260614.json` 为 `status=pass`，覆盖 TLS、health、search backend、页面渲染、审计日志权限、查询引用、原文预览、底稿导出和边缘域名回归。
- 生产前端验收报告 `tmp/outputs/production-frontend-acceptance-after-pr73-answer-gate-deploy-20260614.json` 为 `status=pass`，覆盖 `21` 个路由、`42` 个检查，`p0_count=0`、`p1_count=0`。
- 部署状态审计报告 `tmp/outputs/tencent-cloud-deployment-state-after-pr73-answer-gate-deploy-retry-20260614.json` 为 `status=pass`，`issues=[]`。
- 生产容器未设置 `MEDICAL_AUDIT_KB_ANSWER_*`；当前只有既有 `KIMI_API_KEY` 存在，`MOONSHOT_API_KEY`、`OPENAI_API_KEY`、`ANTHROPIC_API_KEY` 和 `DEEPSEEK_API_KEY` 均未设置。
- no-fallback 生产 smoke 报告 `tmp/outputs/production-e2e-smoke-require-generated-answer-after-pr73-deploy-20260614.json` 为 `status=fail`，失败点仅为 `query-api-with-citations`，错误为 `query response used fallback answer instead of generated answer`。
- `query-api-with-citations` 普通链路仍返回 `fallback_used=true`；这证明检索引用 fallback 链路可用，不证明真实生成模型能力可用。
- 部署后曾出现一次普通 smoke `query-api-with-citations` 读超时，报告为 `tmp/outputs/production-e2e-smoke-after-pr73-answer-gate-deploy-verification-20260614.json`；随后直接请求生产 `/query` 约 `2.94s` 返回 `200`，普通 smoke 复核通过。该现象记录为短期稳定性观察项，不作为当前部署失败结论。
- `ai_video.pem` 仍保留在项目本地用于 SSH；禁止删除，禁止提交到 Git。

### 2026-06-14 项目成员生产写入验收

- 验收范围：项目成员管理 API 和生产 PostgreSQL `audit_project_members` 持久化写入。
- 写入前 DB 备份：`/opt/medical-audit/backups/db/pre-project-member-write-smoke-20260614T212850+0800.sql.gz`。
- 备份校验：`gzip -t` 通过，权限 `600`，大小 `512950686` bytes，`sha256=2f0c119410ad58690934f555cf6d807a91c70cf6588a8189dcc4d058f0c4b8a0`。
- 生产 API 写入报告：`tmp/outputs/production-project-member-write-smoke-20260614.json`，状态 `pass`。
- 写入结果：`CATALOG-LIMIT-202606` 新增成员 `member-custom-e152673f93f9`，`created_by=codex-production-e2e-20260614`，成员数从 `4` 增至 `5`。
- 数据库直查：`audit_project_members` 当前自定义记录数为 `1`，记录为 `member-custom-e152673f93f9|CATALOG-LIMIT-202606|生产联调审计员|审计员|codex-production-e2e-20260614`。
- 写入后生产前端验收：`tmp/outputs/production-frontend-acceptance-after-project-member-write-20260614.json`，状态 `pass`，覆盖 `21` 个路由、`42` 个检查，`p0_count=0`、`p1_count=0`。
- 边界：本轮只验证项目成员新增和持久化；真实权限生效、邀请审批、成员禁用/移除和组织级用户体系仍未完成。

### 2026-06-14 智能体生产写入验收

- 验收范围：提示词型智能体 API 和生产 PostgreSQL `audit_agents` 持久化写入。
- 写入前 DB 备份：`/opt/medical-audit/backups/db/pre-agent-write-smoke-20260614T215017+0800.sql.gz`。
- 备份校验：`gzip -t` 通过，权限 `600`，大小 `512951265` bytes，`sha256=5d06dd8919f71f7d73446203424e8907dd1fc7677fc2a3d40e819bf6109026db`。
- 生产 API 写入报告：`tmp/outputs/production-agent-write-smoke-20260614.json`，状态 `pass`。
- 写入结果：新增智能体 `agent-custom-ec210547464a`，`created_by=codex-production-agent-e2e-20260614`，智能体列表从 `3` 增至 `4`。
- 数据库直查：`audit_agents` 当前自定义记录数为 `1`，记录为 `agent-custom-ec210547464a|生产联调提示词助手|业务类|项目成员生产验收后的证据复核|codex-production-agent-e2e-20260614`。
- 写入后生产前端验收：`tmp/outputs/production-frontend-acceptance-after-agent-write-20260614.json`，状态 `pass`，覆盖 `21` 个路由、`42` 个检查，`p0_count=0`、`p1_count=0`。
- 边界：本轮只验证新增提示词型智能体和持久化；提示词版本治理、上下架、删除/停用、权限生效和复杂智能体编排仍未完成。

### 2026-06-14 AI 数据分析生产上传验收

- 验收范围：`/api/v1/analytics/table-upload` 生产上传解析链路。
- 生产上传报告：`tmp/outputs/production-analytics-upload-smoke-20260614.json`，状态 `pass`。
- CSV 上传结果：`production-analytics-e2e.csv` 返回 `200`、`status=parsed`、`row_count=4`、`column_count=7`、`duplicate_row_count=1`、`empty_cell_count=1`，识别金额/费用、患者/就诊、日期/时间、项目/药品/目录、医保支付和数量字段。
- XLSX 上传结果：`production-analytics-e2e.xlsx` 返回 `200`、`status=parsed`、`sheet_name=审计数据`、`row_count=4`、`column_count=7`、`duplicate_row_count=1`、`empty_cell_count=1`，识别同等审计信号。
- 非法扩展验证：`.txt` 上传返回 `422 unsupported table file extension`。
- 写入后生产前端验收：`tmp/outputs/production-frontend-acceptance-after-analytics-upload-20260614.json`，状态 `pass`，覆盖 `21` 个路由、`42` 个检查，`p0_count=0`、`p1_count=0`。
- 边界：本轮只验证瞬时上传解析，不保存上传文件，不写入数据库业务表；病毒扫描、脱敏留存、对象存储、历史分析记录和正式工作簿治理仍未完成。

### 2026-06-14 文档检索生产查询验收

- 验收范围：`/api/v1/query` 生产查询、来源过滤、引用证据、证据分组和 `/pages/preview/{chunk_id}` 原文预览链路。
- 生产查询报告：`tmp/outputs/production-documents-query-smoke-20260614.json`，状态 `pass`。
- 全库重复收费查询：返回 `200`，`citation_count=3`，证据类型为 `rule_basis`，首个引用预览页返回 `200`。
- 法规政策过滤查询：`source_collections=["medical-insurance-laws"]` 返回 `200`，`citation_count=3`，证据类型为 `legal_basis`，首个引用预览页返回 `200`。
- 医保目录过滤查询：`source_collections=["medical-insurance-catalog"]` 返回 `200`，`citation_count=3`，证据类型为 `catalog_basis`，首个引用预览页返回 `200`。
- 验收后生产前端验收：`tmp/outputs/production-frontend-acceptance-after-documents-query-20260614.json`，状态 `pass`，覆盖 `21` 个路由、`42` 个检查，`p0_count=0`、`p1_count=0`。
- 边界：`/api/v1/query` 会写入进程内查询日志和 preview reference，但不写入数据库业务表；本轮未完成搜索历史持久化、个人知识库上传、文档权限模型，也未补充响应中的 `source_collection` 直接回显字段。

### 2026-06-15 AI 数据分析留存历史生产验收

- 本地实现范围：`/api/v1/analytics/table-upload` 上传成功后留存原始文件、写入 `analytics_upload_records`，并通过 `GET /api/v1/analytics/table-uploads` 返回最近上传历史。
- 本地联调证据：`tmp/screenshots/tmp-screenshot-analytics-retention-history-20260615.png`；上传 `charge-retention-final.csv` 后最新历史记录为 `analytics-upload-28a10ca6ac89`，`retention_status=retained`。
- 生产部署已完成 host 目录 `/opt/medical-audit/analytics-uploads` 创建和 Compose 挂载：`${MEDICAL_AUDIT_ANALYTICS_UPLOAD_ROOT_HOST:-/opt/medical-audit/analytics-uploads}:/app/analytics-uploads`。
- 生产 schema 已应用 `analytics_upload_records` 表和索引。
- 生产 API 写入型验收：`tmp/outputs/production-analytics-retention-write-e2e-20260615.json`，状态 `pass`；`analytics-upload-b3a1898e38d1` 历史、DB 行和宿主机留存文件均验证通过。
- 生产 UI 上传联调：`tmp/outputs/production-analytics-ui-upload-retention-e2e-20260615.json`，状态 `pass`；`analytics-upload-f39d652d3f81` 由 `/analytics` 页面上传产生，历史、DB 行和宿主机留存文件均验证通过。
- 边界：本轮完成文件留存和历史记录，不等于完成病毒扫描、脱敏改写、对象存储、下载权限隔离、正式工作簿治理或长期存储生命周期策略。

### 2026-06-14 Phase 1 历史基线事实

- 本轮已完成 Phase 1 基线复核、生产只读 smoke、生产前端语义验收和生产写入型 E2E smoke；未执行部署、schema 写入或远端配置修改。
- 写入前只读状态审计命令：`python3 scripts/audit-tencent-cloud-deployment-state.py --ssh-key ai_video.pem`。
- 写入前审计采集时间：`2026-06-14T10:53:45+0800`。
- 写入前审计状态：`status=pass`，`issues=[]`。
- 写入后只读状态审计采集时间：`2026-06-14T10:58:09+0800`。
- 写入后审计状态：`status=pass`，`issues=[]`。
- 当时生产部署 SHA：`32027049eb7fa2b9d336af217a228b0f21dca990`。
- `medical_audit_app` 容器 `running` 且 `health=healthy`，Compose project 为 `medical-audit`。
- `medical_audit_pg` 容器 `running` 且 `health=healthy`，Compose project 为 `medical-audit`。
- 共享公网入口 `ai_video_nginx` 仍在运行，Compose project 为 `lighthouse`。
- Nginx 配置测试通过，`/var/www/audit` 到 `ai_video_nginx` 的 bind mount 存在且为只读。
- 生产本地后端 `/health` 返回 `status=ok`、`version=0.1.0`。
- 生产检索后端返回 `backend=postgres`、`ready=true`、`matching_embedding_count=48985`、`embedding_model=kimi-for-coding`、`embedding_dimension=1024`、`api_key_env=KIMI_API_KEY`。
- 远端最新备份类别覆盖 `app`、`env`、`db`、`nginx` 和 `web`；写入型 E2E 前已新增 DB 备份 `/opt/medical-audit/backups/db/pre-review-write-smoke-phase1-20260614T105417+0800.sql.gz`。
- 写入前 DB 备份已执行 `gzip -t` 校验通过，权限为 `600`，大小约 `490M`，`sha256=169eeec6a99ff09e1a0a277d75f2f70620d01ff6b71dd03ea4c68a7b98cbb777`。
- 生产只读 smoke 报告 `tmp/outputs/production-e2e-smoke-phase1-readonly-20260614.json` 为 `status=pass`，覆盖 `8` 个步骤。
- 生产写入型 smoke 报告 `tmp/outputs/production-e2e-smoke-phase1-review-write-20260614.json` 为 `status=pass`，覆盖 `9` 个步骤。
- 写入型 smoke 已创建并更新 `review-task-0011`，`create_status=200`，`update_status=200`。
- 生产前端语义验收报告 `tmp/outputs/production-frontend-acceptance-phase1-20260614.json` 为 `status=pass`，覆盖 `20` 个路由、桌面和移动共 `40` 次检查，`p0=[]`，`p1=[]`。
- 本地 Phase 1 代码基线：`uv run ruff check src tests scripts` 通过，`uv run mypy src` 通过，`uv run pytest` 结果为 `241 passed, 1 warning`。
- 本地 Phase 1 前端基线：`pnpm --dir web lint`、`typecheck`、`test` 和 `build:static` 均通过；前端测试为 `10` 个 test files、`51` 个 tests，通过；静态构建生成 `20/20` 页面。
- 远端 DB 备份目录已确认无残留 `*.uploading` 文件。
- 当前本地分支为 `codex/post-deploy-doc-sync`，本地 HEAD 为 `912965d6 同步腾讯云生产部署记录`，相对本地 `origin/main` ahead 1。
- 当前本地存在 `.kiro/`、`.playwright-mcp/`、`drafts/analysis/analysis-production-acceptance-p0-p1-*.md`、`drafts/analysis/analysis-reference-material-*.md`、`opendesign/` 和 `ref/` 等未跟踪资料；部署脚本已排除这些目录，不能把它们同步到生产。
- `ai_video.pem` 仍作为腾讯云 SSH key 保留在项目本地；禁止删除，禁止提交到 Git。
- 当前生产健康和写入型 smoke 通过不等于 V1.0 完成：门户壳层、检索、引用、预览和任务级复核写入链路可用；真实医院数据验收、真实生成模型、真实权限系统和案件级合规闭环仍需单独完成。
- `query-api-with-citations` 仍返回 `fallback_used=true`，只能证明引用型 fallback 链路健康，不能证明真实生成模型能力可用。

### 2026-06-14 no-fallback 生成模型门禁复核

- PR #73 `接入答案生成 provider 并强化 no-fallback 生产门禁` 已合并并部署到生产。
- PR #73 只提供代码门禁能力和 no-fallback 验收能力，不等于生产真实生成模型已经启用。
- 本地门禁已复核通过：`uv run ruff check src tests scripts`、`uv run mypy src`、`uv run pytest -q`。
- PR #73 部署前生产 `.deploy-sha` 曾为 `89fe9215a2617bd3d933d2274739561e403c3c28`；部署后生产 `.deploy-sha` 为 `281981ce072b549ebbcc4332db6d5ae1a06801e5`。
- 生产未写入 `MEDICAL_AUDIT_KB_ANSWER_*`，因此 no-fallback 门禁仍应失败。
- 生产容器当前只有 `KIMI_API_KEY` 存在；`MOONSHOT_API_KEY`、`OPENAI_API_KEY`、`ANTHROPIC_API_KEY`、`DEEPSEEK_API_KEY` 均未设置。
- 现有 `KIMI_API_KEY` 对 `https://api.moonshot.cn/v1` 和 `https://api.moonshot.ai/v1` 的常规 Chat Completions endpoint 返回 `401 Invalid Authentication`。
- 现有 `KIMI_API_KEY` 对 `https://api.kimi.com/coding/v1` 返回 `403 access_terminated_error`，错误说明该路径仅面向 Coding Agents，不能作为普通审计问答 chat provider。
- 本机 `ANTHROPIC_API_KEY` 存在，但 `answer-provider-smoke` 使用 `claude-haiku-4-5-20251001` 和 `claude-sonnet-4-6` 均返回 `401 invalid x-api-key`；不能迁移到生产。
- 当前 no-fallback smoke 报告 `tmp/outputs/production-e2e-smoke-require-generated-answer-after-pr73-deploy-20260614.json` 为 `status=fail`，失败点仅为 `query-api-with-citations`：`query response used fallback answer instead of generated answer`。TLS、health、search backend、page rendering 和 audit logs permission 均通过。

生产启用真实生成模型前必须先满足：

1. 提供一个只用于服务端的有效 chat provider key，不得写入 Git、PR、日志或前端。
2. 在本机或生产容器内运行 `answer-provider-smoke`，确认 `success=true`、`citation_marker_present=true`、`required_term_present=true`。
3. 备份远端 `configs/deploy/tencent-cloud/medical-audit.env`，再写入 `MEDICAL_AUDIT_KB_ANSWER_PROVIDER`、`MEDICAL_AUDIT_KB_ANSWER_API_KEY_ENV`、`MEDICAL_AUDIT_KB_ANSWER_MODEL`、`MEDICAL_AUDIT_KB_ANSWER_BASE_URL`、`MEDICAL_AUDIT_KB_ANSWER_MAX_OUTPUT_TOKENS` 和 `MEDICAL_AUDIT_KB_ANSWER_TEMPERATURE`。
4. 写入 provider env 并重启生产应用后运行：

```bash
python3 scripts/run-production-e2e-smoke.py \
  --base-url https://audit.lute-tlz-dddd.top \
  --expected-matching-embeddings 0 \
  --require-generated-answer \
  --report tmp/outputs/production-e2e-smoke-require-generated-answer-latest.json
```

未满足以上前置条件时，禁止把 `fallback_used=true` 的 smoke 结果表述为真实生成模型验收通过。

### 2026-06-13 当前事实

- 当前远端 `main` merge commit：`596d6967ba5b6c3d2a7d2253c8a31b264fb7ae82`，来自 PR #70 `集成审计门户核心工作台`。
- 当时生产部署 SHA：`32027049eb7fa2b9d336af217a228b0f21dca990 放宽部署前共享网关漂移阻断`；该提交已作为 `main` 的祖先保留，避免生产领先主干。
- `medical_audit_app` 容器 healthy，宿主机仍仅暴露 `127.0.0.1:18080->8000`。
- `medical_audit_pg` 容器 healthy，继续使用独立 volume `medical_audit_pgdata`。
- 公网 `/api/v1/index/search-backend` 返回 `backend=postgres`、`ready=true`、`matching_embedding_count=48985`、`embedding_model=kimi-for-coding`。
- 生产前端已升级为 `AI智能审计管理系统` 门户壳层，静态页面包含 `/workspace`、`/chat`、`/agents`、`/agent-market`、`/knowledge-base`、`/documents`、`/analytics`、`/graph`、`/rules`、`/reports`、`/remediation`、`/archive`、`/projects`、`/guided-check`、`/knowledge-query` 和 `/findings`。
- 生产 read-only smoke `production-e2e-smoke-after-p5-reference-shell-20260613` 已通过，覆盖 TLS、health、PostgreSQL 检索、页面渲染、查询引用、原文预览、底稿导出和边缘域名回归。
- 生产前端验收 `production-frontend-acceptance-after-p5-reference-shell-20260613` 已通过，20 个路由桌面/移动检查 `p0_count=0`、`p1_count=0`。
- 生产状态审计 `production-state-audit-after-p5-reference-shell-20260613` 已通过，确认备份戳 `p5-reference-shell-20260613`、远端 `.deploy-sha` 和 active search backend 均符合预期。
- 部署同步脚本已显式排除 `.kiro/`、`.playwright-mcp/`、`drafts/`、`ref/`、`opendesign/`、`tmp/`、密钥和 env 文件，避免参考材料、草稿、临时产物或密钥进入生产应用目录。
- 本地缺少 `KIMI_API_KEY` 时，本地 `/index/search-backend/postgres` 会返回 `409 missing embedding api key env: KIMI_API_KEY`；这是本地运行态密钥缺口，不表示生产 search backend 不可用。
- 当前答案生成仍为 citation fallback：检索、引用、预览和底稿导出可用，但不能表述为外部生成式大模型答案已完成。

### 2026-06-12 当前事实

- 当时生产部署 SHA：`9f98c8d36ea72a660c69f27b41a156f5a292b23a 修复疑点复核任务状态同步`。
- `medical_audit_app` 容器 healthy，宿主机仅暴露 `127.0.0.1:18080->8000`。
- `medical_audit_pg` 容器 healthy，继续使用独立 volume `medical_audit_pgdata`。
- 公网 `https://audit.lute-tlz-dddd.top/` 返回 `200`，`/api/v1/index/search-backend` 返回 `backend=postgres`、`ready=true`、`matching_embedding_count=48985`，`/api/v1/audit-findings` 返回 `200` 且 store 为 `SqlAlchemyAuditFindingStore`。
- 当前生产已写入受控脱敏 fixture 链路：`audit_projects=1`、`his_source_batches=1`、`his_table_schemas=1`、`his_field_mappings=9`、`his_staging_rows=3`、`audit_data_snapshots=1`、`audit_tasks=1`、`audit_runs=1`、`audit_rules=1`、`rule_versions=1`、`audit_findings=1`、`finding_evidence_items=1`；`/api/v1/audit-findings.generation_readiness.status=generated`。该数据来自 `production-fixture-bootstrap`，只证明规则生成链路和页面联通，不代表真实医院疑点或客户数据。
- fixture finding `finding-f044ebd309b659dc` 已创建并链接 `review-task-0007`；当前疑点复核状态为 `confirmed-violation`，复核任务报告门禁为 `ready_for_report=true`，任务 Markdown 导出和报告草稿 JSON/Markdown 导出均可用。
- `review-task-0007` 已完成受控 fixture 正式报告签发和整改跟踪验收：正式报告 `signed-report-03cb4bed3dd4`、正文 SHA256 `f16561b3f5fbab81497fb3313782609d40867cf10bee7f6d53c3ae75687c3bd5`、整改事项 `rectification-44526138b71e`、整改状态 `accepted`、结案门禁 `ready_to_close=true`；任务状态仍保留为 `confirmed-violation`，未执行结案。
- 生产认证桥接已采用 Nginx 内部注入 `X-API-Key`，secret 只保存在远端 Nginx 配置与 env 中，未进入 Git、镜像或本地文档。
- `MEDICAL_AUDIT_KB_ALLOW_EXTERNAL_AI` 已改为由远端 `medical-audit.env` 控制；当前生产 env 显式为 `1`，用于支持 query embedding，出站前 PII 扫描仍由 `egress_policy` 执行。
- `ai_video_nginx` 仍为共享公网入口；本次只修改 `audit.lute-tlz-dddd.top` 对应 server block，没有重启或改动 `ai_video_frontend`、`voc_superset`、`promptforge_app` 等其它业务容器。
- `ai_video_nginx` 已通过 `/opt/ai-video/deploy/lighthouse/docker-compose.prod.yml` 挂载 `/var/www/audit:/var/www/audit:ro`，静态发布只需同步宿主机 `/var/www/audit`，容器会直接读取该目录。
- 共享 `ai_video_nginx` 已定义 `upstream medical_audit_app { server medical_audit_app:8000; }`；`audit.lute-tlz-dddd.top` server block 内 `proxy_pass` 必须使用 `http://medical_audit_app`，不得再写 `:8000`。
- Next.js 静态前端当前包含 `/workspace`、`/knowledge-query` 和 `/findings`；主导航“查询工作台”指向 `/knowledge-query`，“疑点清单”指向 `/findings`，后端 `/pages/query` 与 `/pages/audit-findings` 保留为兼容入口，根路径 `/query` 继续作为后端 API 精确代理入口。

### 2026-06-06 当前事实

- `medical_audit_app` 容器仍在运行，宿主机 `127.0.0.1:18080` 可访问。
- `medical_audit_pg` 容器健康，服务器内 `/index/search-backend` 返回 `backend=postgres`、`ready=true`。
- `ai_video_nginx` 与 `medical_audit_app` 位于同一 Docker 网络，可通过容器名路由。
- 公网 `https://audit.lute-tlz-dddd.top/health` 已恢复到 medical_audit 应用。
- 2026-06-06 曾出现反代漂移：`audit.lute-tlz-dddd.top` 落到 AI video fallback。根因是共享 `ai_video_nginx` 的宿主机源配置 `/opt/ai-video/deploy/lighthouse/nginx.conf` 缺少 `audit.lute-tlz-dddd.top` HTTPS server block。
- 已在用户确认后备份并修复宿主机源配置，新增 `audit.lute-tlz-dddd.top` server block 指向 `medical_audit_app:8000`，`nginx -t` 和 reload 成功。
- 反代修复后发现生产镜像滞后于本地专题代码；已重建并重启 `medical_audit_app`，医保基金使用合规专题入口和专题查询参数已上线。

已核验：

- `audit.lute-tlz-dddd.top` A 记录指向 `101.34.52.232`。
- Docker 已安装：`Docker 26.1.3`，`Docker Compose v2.27.1`。
- 当前公网入口容器：`ai_video_nginx`，占用 `80/443`。
- 现有业务容器包括 `promptforge_app`、`voc_superset`、`ai_video_frontend`、`ai_video_backend`。
- 当前证书 `/etc/letsencrypt/live/lute-tlz-dddd.top/fullchain.pem` 已包含 `audit.lute-tlz-dddd.top`。
- 服务器磁盘约 `178G`，剩余约 `107G`。
- 内存约 `7.3G`，可用约 `4.7G`。
- Swap `1G` 已满，导入 pgvector 数据时必须避免并发高负载。

## 3. 已完成的隔离环境

已在远端创建：

- `/opt/medical-audit/`
- `/opt/medical-audit/app/configs/deploy/tencent-cloud/`
- `/opt/medical-audit/backups/`
- `/opt/medical-audit/tmp/`
- `/opt/medical-audit/audit-log-archive/`
- `/opt/medical-audit/audit-reports/`
- Docker network：`medical_audit_internal`
- Docker volume：`medical_audit_pgdata`
- PostgreSQL/pgvector 容器：`medical_audit_pg`

已执行 schema 初始化：

- `pgcrypto` extension 已存在。
- `vector` extension 已存在。
- public schema 当前表数量：`10`。

历史公网发布基线：

- `medical_audit_app` 已启动，监听宿主机 `127.0.0.1:18080`，不直接暴露公网端口。
- `medical_audit_pg` 使用独立 volume `medical_audit_pgdata`，不复用其它项目数据库。
- `full-rebuild-20260603085815` 已激活为 active index，`full-rebuild-20260531142344` 已变为 inactive rollback target。
- `ai_video_nginx` 已加入 `audit.lute-tlz-dddd.top` HTTPS 反代块。
- Let's Encrypt 证书已扩展 SAN，包含 `audit.lute-tlz-dddd.top`。
- 公网入口：`https://audit.lute-tlz-dddd.top/pages/chat`。

注意：2026-06-06 修复说明了一个运维约束：`ai_video_nginx` 内 `/etc/nginx/nginx.conf` 是宿主机只读 bind mount，后续必须修改 `/opt/ai-video/deploy/lighthouse/nginx.conf` 并先执行 `nginx -t`，不能尝试在容器内覆盖正式配置文件。

## 4. 部署资产

项目内新增生产部署资产：

- `configs/deploy/tencent-cloud/Dockerfile`
- `configs/deploy/tencent-cloud/docker-compose.prod.yaml`
- `configs/deploy/tencent-cloud/medical-audit.env.example`
- `configs/deploy/tencent-cloud/nginx-audit-server.conf`
- `scripts/audit-tencent-cloud-deployment-state.py`
- `scripts/deploy-tencent-cloud-production.py`
- `scripts/run-audit-log-archive-audit.py`
- `scripts/run-document-cos-bootstrap-preflight.py`
- `scripts/run-production-frontend-acceptance.mjs`
- `.dockerignore`

密钥策略：

- `ai_video.pem` 只用于本地 SSH，不进入镜像。
- `KIMI_API_KEY` 只允许写入远端 `medical-audit.env`，权限必须为 `600`。
- `MEDICAL_AUDIT_AUDIT_LOG_SIGNING_SECRET` 只允许写入远端 `medical-audit.env`，用于审计日志归档 HMAC 验签；不得写入 git、报告或签名 manifest。
- `COS_SECRET_ID` 和 `COS_SECRET_KEY` 只允许写入远端 `medical-audit.env` 或等价密钥注入机制；报告和 PR 正文只允许记录 env name、是否存在和 preflight 状态，不记录真实值。
- 任何 `*.env`、`*.pem`、`*.key` 不允许进入 git。

## 5. 已执行上线记录

### 5.1 数据导入结果

远端 pgvector 已完成导入和激活。当前生产 active 基线：

- active `source_documents = 503`
- active `document_chunks = 49051`
- active `chunk_embeddings = 49051`
- active `index_version_key = incremental-20260615-national-regulation-stable-20260615103344`
- active `source_package_version_key = source-package-national-regulation-stable-incremental-20260615103344`
- index version status count：`active = 1`、`inactive = 3`
- `failed_files = 0`
- `pending_files = 0`
- `index_version_status = active`

说明：

- 当前 active index 的 `failed_files` 与 `pending_files` 均为 `0`。
- 2026-06-03 首次生产 active 版本为 `full-rebuild-20260603085815`，计数为 `486/48985/48985`；该版本已在 2026-06-15 国家规章平台增量激活后变为 `inactive`。
- 完整历史源文件仍保留在本地 `data/`，远端当前服务依赖 active source subset 和 pgvector 数据库。

### 5.2 运行环境

远端运行状态：

- Compose project：`medical-audit`
- App container：`medical_audit_app`
- Database container：`medical_audit_pg`
- Public proxy：`ai_video_nginx`
- App local endpoint：`http://127.0.0.1:18080`
- Public endpoint：`https://audit.lute-tlz-dddd.top`

搜索后端 ready 门槛已通过：

- `backend = postgres`
- `ready = true`
- `embedding_model = kimi-for-coding`
- `embedding_dimension = 1024`
- `matching_embedding_count = 49051`

### 5.3 证书与反代

已执行：

1. 备份 `/opt/ai-video/deploy/lighthouse/nginx.conf` 到 `/opt/medical-audit/backups/`。
2. 将 `audit.lute-tlz-dddd.top` 加入 80 端口 `server_name`。
3. 通过 ACME challenge webroot 探测。
4. 使用 certbot `--expand` 扩展 `lute-tlz-dddd.top` 证书 SAN。
5. 将 `configs/deploy/tencent-cloud/nginx-audit-server.conf` 合并进 nginx `http` 块。
6. 执行 `nginx -t` 并 reload `ai_video_nginx`。

### 5.4 审计日志归档巡检调度

已在 2026-06-05 部署 PR #36 对应的归档巡检调度入口：

- 同步前已创建应用备份 `/opt/medical-audit/backups/app/pre-archive-scheduler-sync-20260605T072618Z.tar.gz`。
- 同步前已创建 env 备份 `/opt/medical-audit/backups/env/medical-audit.env.pre-archive-scheduler-20260605T072618Z`。
- schema 补齐前已创建数据库备份 `/opt/medical-audit/backups/db/pre-archive-scheduler-schema-apply-20260605T072958Z.sql`。
- 已创建受控目录 `/opt/medical-audit/audit-log-archive` 和 `/opt/medical-audit/audit-reports`，权限为 `750`。
- 已在远端 `medical-audit.env` 写入 `MEDICAL_AUDIT_AUDIT_LOG_ARCHIVE_ROOT_HOST`、`MEDICAL_AUDIT_AUDIT_LOG_ARCHIVE_REPORT_DIR_HOST`、`MEDICAL_AUDIT_AUDIT_LOG_SIGNING_SECRET` 和 `MEDICAL_AUDIT_AUDIT_LOG_MIN_MANIFEST_COUNT`，env 权限为 `600`。
- 已重建并重启 `medical_audit_app`，`medical_audit_pg` 仍使用独立 volume `medical_audit_pgdata`。
- 首次重启后发现生产库缺少 `audit_log_events`，导致 `/index/search-backend` 因操作日志写入失败返回 `500`；已使用正式 `sql/knowledge-query-schema.sql` 幂等补齐 schema，补齐后 `audit_log_events` 可写入。
- 已安装 cron 文件 `/etc/cron.d/medical-audit-archive-audit`，服务器时区为 `Asia/Shanghai`，每天 `03:17` 执行只读 archive root 巡检。
- 手动执行同款 cron 命令已通过，latest 报告为 `/opt/medical-audit/audit-reports/audit-log-archive-audit-latest.json`，当前 `status=pass`、`manifest_count=0`、`failed_count=0`。
- 部署后生产只读 E2E `production-e2e-smoke-after-archive-scheduler-20260605` 已通过，覆盖 TLS、health、PostgreSQL 检索、页面渲染、查询引用、原文预览、底稿导出和边缘域名回归。

已在 2026-06-05 部署 PR #38 和 PR #39 对应的 webhook 告警能力：

- 同步前已创建应用备份 `/opt/medical-audit/backups/app/pre-webhook-alert-sync-20260605T075128Z.tar.gz`。
- 同步前已创建 env 备份 `/opt/medical-audit/backups/env/medical-audit.env.pre-webhook-alert-20260605T075128Z`。
- 已在远端 `medical-audit.env` 补充 `MEDICAL_AUDIT_AUDIT_LOG_ALERT_WEBHOOK_URL`、`MEDICAL_AUDIT_AUDIT_LOG_ALERT_TIMEOUT_SECONDS`、`MEDICAL_AUDIT_AUDIT_LOG_SEND_SUCCESS_ALERT` 和 `MEDICAL_AUDIT_AUDIT_LOG_ALERT_FAIL_ON_ERROR`。
- 当前 `MEDICAL_AUDIT_AUDIT_LOG_ALERT_WEBHOOK_URL` 为空，因此生产失败告警不会外发，只保留 cron 退出码、cron log 和 latest 报告。
- 手动巡检默认路径已通过，输出 `alert.status=not-requested`。
- 手动执行 `--send-success-alert --fail-on-alert-error` 在无 webhook URL 时返回 `exit_code=2`、`audit_exit_code=0` 和 `alert.status=not-configured`，证明告警通道验收不会误判为通过。
- 部署后生产只读 E2E `production-e2e-smoke-after-webhook-alert-20260605` 已通过，覆盖 TLS、health、PostgreSQL 检索、页面渲染、查询引用、原文预览、底稿导出和边缘域名回归。

### 5.5 审计页面 UI 与证据交互部署

已在 2026-06-05 部署 PR #41 对应的审计页面 UI 与证据交互一致性优化：

- PR #41 已合并到 `main`，merge commit 为 `6cc17e09878a0a8baff21d8789aac8d21891c6d7`。
- 同步前已创建应用备份 `/opt/medical-audit/backups/app/pre-pr41-ui-sync-20260605T083604Z.tar.gz`。
- 同步前已创建 env 备份 `/opt/medical-audit/backups/env/medical-audit.env.pre-pr41-ui-sync-20260605T083604Z`。
- 已同步 `main@6cc17e09878a0a8baff21d8789aac8d21891c6d7` 到 `/opt/medical-audit/app/`，同步时显式排除 `.git/`、`.venv/`、`.codegraph/`、`tmp/`、`data/`、`archive/`、env 和密钥文件。
- 已重建并重启 `medical_audit_app`，`medical_audit_pg` 仍使用独立 volume `medical_audit_pgdata`。
- 部署后 `/index/search-backend` 返回 `backend=postgres`、`ready=true`、`embedding_model=kimi-for-coding`、`matching_embedding_count=48985`。
- 部署后生产只读 E2E `production-e2e-smoke-after-pr41-ui-20260605` 已通过，覆盖 TLS、health、PostgreSQL 检索、页面渲染、查询引用、原文预览、底稿导出和边缘域名回归。
- 部署后生产视觉基线 `knowledge-query-chat-visual-baseline-prod-after-pr41-ui-20260605` 已通过，desktop/mobile 均无横向溢出，关键文案无缺失。

### 5.6 医保基金使用合规专题入口部署

已在 2026-06-06 部署医保基金使用合规专题入口与运行时专题过滤：

- 同步前已创建应用备份 `/opt/medical-audit/backups/app/pre-fund-topic-sync-20260606T111200+0800.tar.gz`。
- 已同步当前本地已验证的构建资产到 `/opt/medical-audit/app/`，同步时排除 `.git/`、`.venv/`、`tmp/`、`data/`、`archive/`、env、密钥和设计草稿。
- 已重建并重启 `medical_audit_app`，`medical_audit_pg` 仍使用独立 volume `medical_audit_pgdata`。
- 部署后 `/pages/chat?audit_topic=fund-usage-compliance` 显示“医保基金使用合规”专题入口，表单提交后保留 `audit_topic=fund-usage-compliance`。
- 部署后公网 `/query` 专题请求返回 `audit_topic=fund-usage-compliance`、`confidence=high`、`citation_count=3`、`basis_group_count=2`。
- 首条专题引用来自 active index `full-rebuild-20260603085815`，并可打开 `/pages/preview/{chunk_id}` 原文预览。
- 生产只读 E2E `production-e2e-smoke-after-fund-topic-deploy-20260606` 已通过。
- 生产视觉基线 `knowledge-query-chat-visual-baseline-prod-after-fund-topic-deploy-20260606` 已通过，desktop/mobile 均无横向溢出，关键文案无缺失。
- 证据边界：当前专题查询使用运行时分类过滤，不代表 `audit_topic/subtopic/risk_category` 已写入 active index。

### 5.7 医保基金使用合规专题映射优先查询部署

已在 2026-06-06 部署 active topic mapping 优先查询链路：

- 同步前已创建应用备份 `/opt/medical-audit/backups/app/pre-query-topic-mapping-sync-20260606T145146+0800.tar.gz`。
- 已同步本地已验证构建资产到 `/opt/medical-audit/app/`，同步时排除生产 env、密钥、data、tmp 和 archive。
- 已用正式 compose 重建并重启 `medical_audit_app`，`medical_audit_pg` 保持 healthy，未重建数据库 volume。
- 部署后公网 `/query` 专题请求返回 `topic_filter_source=active-mapping`、`confidence=high`、`citation_count=3`、`basis_group_count=2`。
- 部署后 `/pages/chat?...&audit_topic=fund-usage-compliance` 保留专题入口、专题参数和证据卷宗，首条引用原文预览返回 `200`。
- 证据边界：专题查询已优先消费 active mapping，但 9 张规则知识卡仍处于候选/评审状态，不得标记为 `stable`。

### 5.8 生产认证桥接与前后端联调部署

已在 2026-06-11 部署生产认证桥接、前端静态资产和当前分支验证版本：

- 最终生产部署 SHA：`e8e04f11 fix: 让生产外部 AI 开关尊重环境配置`。
- 应用代码同步基线：`8ac8ae5e test: 支持生产 E2E 认证参数`；后续追加 Compose 配置修复并将远端 `.deploy-sha` 更新为 `e8e04f11`。
- 同步前已创建应用备份 `/opt/medical-audit/backups/app/pre-deploy-20260611T153843+0800.tar.gz`。
- 同步前已创建 env 备份 `/opt/medical-audit/backups/env/medical-audit.env.pre-deploy-20260611T153843+0800`。
- 同步前已创建数据库备份 `/opt/medical-audit/backups/db/pre-deploy-20260611T153843+0800.sql`。
- 同步前已创建 Nginx 备份 `/opt/medical-audit/backups/nginx/nginx.conf.pre-deploy-20260611T153843+0800` 和认证桥接专项备份 `/opt/medical-audit/backups/nginx/nginx.conf.pre-auth-bridge-20260611T153911`。
- 同步前已创建 Web 静态资产备份 `/opt/medical-audit/backups/web/audit-web-pre-deploy-20260611T153843+0800.tar.gz`。
- 已补齐远端 `MEDICAL_AUDIT_KB_ADMIN_API_SECRET`，env 权限保持 `600`。
- 已在 `audit.lute-tlz-dddd.top` 反代块内注入内部 `X-API-Key`，并补齐 `/review-tasks/` legacy 导出反代；`nginx -t` 与 reload 均通过。
- 已同步后端应用代码到 `/opt/medical-audit/app/`，同步时排除 `.git/`、`.venv/`、`node_modules/`、`web/.next/`、`web/out/`、`tmp/`、`data/`、`archive/`、`opendesign/`、`*.pem`、`*.key`、`*.env`。
- 已用 `pnpm web:build:static` 生成本地 `web/out/`，并同步到 `/var/www/audit/`。
- 已幂等执行 `sql/knowledge-query-schema.sql`。
- 首次生产 E2E 发现 `/api/v1/query` 返回 `500`，根因为容器内 `MEDICAL_AUDIT_KB_ALLOW_EXTERNAL_AI=0` 阻断 query embedding；已将 Compose 覆盖项移除，改由远端 env 控制，并备份 env 到 `/opt/medical-audit/backups/env/medical-audit.env.pre-external-ai-20260611T154614`。
- 已只重建 `medical_audit_app`，未重建 `medical_audit_pg`，未删除或重建 `medical_audit_pgdata`。
- 生产只读 E2E `production-e2e-smoke-after-deploy-20260611-external-ai` 已通过；覆盖 TLS、health、PostgreSQL 检索、页面渲染、查询引用、原文预览、底稿导出和 `kg/video/voc/root` 边缘回归。
- 生产视觉基线 `knowledge-query-chat-visual-baseline-prod-after-deploy-20260611` 已通过，desktop/mobile 均无横向溢出，关键文案无缺失。
- 写入型 E2E 首次执行前已创建数据库备份 `/opt/medical-audit/backups/db/pre-review-write-e2e-20260611T160312+0800.sql`；首次失败点为 E2E harness 从历史页面链接误选已关闭的 `review-task-0001`，导致状态更新被只读锁定返回 `409`，不是生产写入链路不可用。
- 首次失败期间创建的 `review-task-0002` 已通过同款状态更新探针关闭，记录为 `production e2e smoke direct probe`。
- 已提交 E2E harness 修复 `d290f24a test: 修复生产写入 E2E 任务选择`，从页面所有导出链接中选择编号最大的最新任务。
- 写入型 E2E 复跑前已创建数据库备份 `/opt/medical-audit/backups/db/pre-review-write-e2e-20260611T160744+0800.sql`。
- 生产写入型 E2E `production-e2e-smoke-with-review-write-after-deploy-20260611` 已通过；创建并关闭 `review-task-0003`，`review_tasks` 从 `2` 增至 `3`，`review_actions` 从 `2` 增至 `3`，任务导出成功。
- 部署后 `docker ps` 显示 `medical_audit_app`、`medical_audit_pg`、`ai_video_nginx` 与其它业务容器均保持运行。

### 5.9 PR #45 合并后静态前端热修与联调

已在 2026-06-11 合并并部署 PR #45：

- PR #45 merge commit：`ed44c05ebbb2e0003d1f2b7bc2df92e8d97b732d`。
- 同步前已创建应用备份 `/opt/medical-audit/backups/app/pre-pr45-main-deploy-20260611T172026+0800.tar.gz`。
- 同步前已创建 env 备份 `/opt/medical-audit/backups/env/medical-audit.env.pre-pr45-main-deploy-20260611T172026+0800`。
- 同步前已创建数据库备份 `/opt/medical-audit/backups/db/pre-pr45-main-deploy-20260611T172026+0800.sql.gz`。
- 同步前已创建 Nginx 备份 `/opt/medical-audit/backups/nginx/nginx.conf.pre-pr45-main-deploy-20260611T172026+0800`。
- 同步前已创建 Web 静态资产备份 `/opt/medical-audit/backups/web/audit-web-pre-pr45-main-deploy-20260611T172026+0800.tar.gz`。
- 首次前后端联调发现公网仍加载旧 Next.js chunk，旧前端会请求 `/api/v1/api/v1/*` 并产生 `404`；根因是 `ai_video_nginx` 容器未挂载宿主机 `/var/www/audit`。
- 已备份容器内旧静态目录到 `/opt/medical-audit/backups/web-container/audit-web-container-pre-pr45-static-hotfix-20260611T173930+0800.tar.gz`。
- 已执行静态热修：`docker cp /var/www/audit/. ai_video_nginx:/var/www/audit`；热修后公网加载的 chunk 与本地 `web/out` 一致。
- 已修正生产 audit server block 使用共享 upstream `medical_audit_app`，`nginx -t` 通过；未重启或重建共享 `ai_video_nginx`。
- 生产写入型 E2E `production-e2e-smoke-with-review-write-after-pr45-main-deploy-20260611` 已通过，创建并关闭 `review-task-0004`。
- 浏览器前后端联调创建 `review-task-0005`、`review-task-0006`，并通过页面表单更新承办人、复核意见、底稿编号；JSON 导出包含写入值。
- 热修后浏览器联调覆盖 `/`、`/workspace`、`/analytics`、`/documents`、`/findings`、`/rules`、`/reports`、`/archive`、`/graph`、`/guided-check`、`/remediation`、`/pages/chat`、`/pages/query`、`/pages/review-tasks`、`/pages/index-admin`、`/pages/audit-findings`、`/pages/audit-logs`，未再出现旧前端 `404` 请求或控制台错误。

### 5.10 共享 Nginx 静态目录 bind mount 固化

已在 2026-06-11 将临时 `docker cp` 静态热修升级为正式 bind mount：

- 变更文件：`/opt/ai-video/deploy/lighthouse/docker-compose.prod.yml`。
- 新增挂载：`/var/www/audit:/var/www/audit:ro`。
- 变更前备份：`/opt/medical-audit/backups/ai-video-nginx-bind-mount/docker-compose.prod.yml.pre-audit-bind-mount-20260611T175105+0800`。
- 变更前容器静态资产备份：`/opt/medical-audit/backups/ai-video-nginx-bind-mount/audit-web-container-pre-bind-mount-20260611T175105+0800.tar.gz`。
- 变更前容器 inspect 备份：`/opt/medical-audit/backups/ai-video-nginx-bind-mount/ai_video_nginx.inspect.pre-compose-recreate-20260611T175148+0800.json`。
- 由于原 `ai_video_nginx` 缺少 Compose 标签，`docker compose up --force-recreate nginx` 首次因容器名冲突被阻止；已先备份 inspect，再 `docker stop` + `docker rm` 旧无状态 Nginx 容器，并用 Compose 创建新的 `ai_video_nginx`。
- 新 `ai_video_nginx` 已带 `com.docker.compose.project=lighthouse`、`com.docker.compose.service=nginx` 标签，后续可由 Compose 正常管理。
- `docker exec ai_video_nginx nginx -t` 通过。
- 宿主机 `/var/www/audit` 与容器内 `/var/www/audit` 文件哈希一致：`804851688fd72af83d3285071f1b98ecbb7993893400f98da4ef94d4f7a29963`。
- 生产只读 E2E `production-e2e-smoke-after-nginx-bind-mount-20260611` 已通过；`kg`、`video`、`voc` 和主域名回归均返回 `200`。

### 5.11 部署自动化入口固化

已新增正式部署脚本：`scripts/deploy-tencent-cloud-production.py`。

脚本边界：

- 默认模式只执行本地与远端只读预检，不写生产。
- 写入生产必须同时传入 `--execute --confirm-production audit.lute-tlz-dddd.top`。
- SSH key 默认读取项目根目录 `ai_video.pem`，也可通过 `MEDICAL_AUDIT_DEPLOY_SSH_KEY` 或 `--ssh-key` 指定。
- 写入流程会先创建 app、env、db、nginx、web 备份，再同步应用代码和 `web/out/`。
- 默认会执行 `pnpm web:build:static`、重建 `medical_audit_app` 并运行生产只读 smoke。
- schema 写入必须显式传入 `--apply-schema`。
- 复核任务写入 E2E 必须显式传入 `--include-review-write`。
- 脚本只校验共享 `ai_video_nginx` 的 `/var/www/audit` bind mount 与 `nginx -t`，不写入共享 Nginx 配置，不处理生产 secret。
- 远端脚本型 SSH 调用必须使用 `ssh -n`，避免本地 stdin 被远端命令链路继承；rsync transport 不使用 `-n`。
- 数据库备份必须使用 plain `docker exec ... pg_dump`，禁止在非交互 SSH 部署链路中使用 `docker exec -i` 或 `docker exec -t`，避免备份完成后本地 SSH 子进程卡住。
- 2026-06-16 已验证 `docker exec -i ... pg_dump` 仍会在备份完成后卡住本地 SSH 子进程；该形态不再作为生产部署脚本方案使用。
- 应用重建后必须等待 `medical_audit_app` health 进入 `healthy`，再执行本机 curl、公网 curl 和生产 smoke。
- 应用同步排除 `.deploy-sha`、`__pycache__/`、`*.pyc` 和本地缓存文件；`.deploy-sha` 只由脚本在同步后显式写入。
- 应用同步前会在备份完成后清理远端 `remote_app_dir/src` 下的 `*.pyc`、`*.pyo`、`*.uploading.cfg` 和空 `__pycache__`，避免旧缓存或云盘上传临时文件阻断 rsync 删除空目录；不得使用 `--delete-excluded`，防止误删远端 `data/`、env、密钥或其他刻意排除资产。

### 5.12 PR #48 部署自动化入口自举部署

已在 2026-06-11 合并并部署 PR #48：

- PR #48 merge commit：`cf6c1479de0b109d5abc9ee92ac8267e549ec2f6`。
- 同步前已创建应用备份 `/opt/medical-audit/backups/app/pre-deploy-20260611T180655+0800.tar.gz`。
- 同步前已创建 env 备份 `/opt/medical-audit/backups/env/medical-audit.env.pre-deploy-20260611T180655+0800`。
- 同步前已创建数据库备份 `/opt/medical-audit/backups/db/pre-deploy-20260611T180655+0800.sql.gz`。
- 同步前已创建 Nginx 备份 `/opt/medical-audit/backups/nginx/nginx.conf.pre-deploy-20260611T180655+0800`。
- 同步前已创建 Web 静态资产备份 `/opt/medical-audit/backups/web/audit-web-pre-deploy-20260611T180655+0800.tar.gz`。
- 已用 `scripts/deploy-tencent-cloud-production.py --execute --confirm-production audit.lute-tlz-dddd.top` 执行首次自举部署。
- 首次自举部署暴露脚本缺陷：`medical_audit_app` 重建后仍处于 `health: starting`，脚本立刻 curl 导致一次 `Connection reset`；生产容器随后自动转为 `healthy`。
- 已补充部署脚本等待 health 的逻辑，避免后续部署在容器启动窗口内误报失败。
- 自举部署后远端 `.deploy-sha=cf6c1479de0b109d5abc9ee92ac8267e549ec2f6`。
- 生产只读 E2E `production-e2e-smoke-after-pr48-deploy-20260611` 已通过；TLS、health、PostgreSQL 检索、页面渲染、查询引用、原文预览、底稿导出和 `kg/video/voc/root` 边缘回归均为 `pass`。

### 5.13 部署状态巡检与备份索引固化

已新增只读部署状态巡检脚本：`scripts/audit-tencent-cloud-deployment-state.py`。

脚本边界：

- 只通过 SSH 读取远端状态，不修改生产文件、容器、数据库或 Nginx。
- 不读取 `medical-audit.env` 内容，只检查备份文件路径、大小和修改时间。
- 默认检查 `medical_audit_app`、`medical_audit_pg`、`ai_video_nginx` 状态。
- 默认检查 `ai_video_nginx` 的 `/var/www/audit` 只读 bind mount 和 `nginx -t`。
- 默认检查本机 `127.0.0.1:18080/index/search-backend` 是否为 PostgreSQL ready，且 `matching_embedding_count >= 1`；报告会记录实际 `matching_embedding_count`，但不再与历史固定计数做精确相等比较。
- 如需提高门槛，使用 `--min-matching-embeddings <最小可接受计数>`；旧参数 `--expected-matching-embeddings` 仍兼容，但语义已调整为最小阈值而非精确值。
- 默认汇总本地 `tmp/outputs/production-e2e-smoke*.json` 的最近结果，报告仍保存在 `tmp/outputs/`，不进入正式资产区。

巡检命令：

```bash
uv run python scripts/audit-tencent-cloud-deployment-state.py \
  --ssh-key ./ai_video.pem \
  --expected-deploy-sha <当前生产 .deploy-sha> \
  --required-backup-stamp <本次部署备份戳>
```

默认输出：

- `tmp/outputs/tencent-cloud-deployment-state-latest.json`
- `tmp/outputs/tencent-cloud-deployment-state-latest.md`

通过条件：

- 远端 `.deploy-sha` 等于期望 SHA。
- `medical_audit_app` 和 `medical_audit_pg` 为 `healthy`。
- `ai_video_nginx nginx -t` 通过。
- `/var/www/audit` bind mount 存在且为只读。
- PostgreSQL 检索后端 ready，embedding 计数等于当前 active index 的 embedding 计数；2026-06-15 当前值为 `49051`。
- 指定部署戳对应的 app/env/db/nginx/web 备份均存在。
- 最近本地生产 smoke 报告不是 `fail`。
- 首次生产巡检 `tencent-cloud-deployment-state-after-pr48-20260611` 已通过，状态为 `pass`，阻断项为空。

### 5.14 PR #51 产品导航真实功能入口部署

已在 2026-06-11 合并并部署 PR #51：

- PR #51 merge commit：`de137e136ee5686b78d0cac6337b20872ee26433`。
- 同步前已创建应用备份 `/opt/medical-audit/backups/app/pre-deploy-20260611T183702+0800.tar.gz`。
- 同步前已创建 env 备份 `/opt/medical-audit/backups/env/medical-audit.env.pre-deploy-20260611T183702+0800`。
- 同步前已创建数据库备份 `/opt/medical-audit/backups/db/pre-deploy-20260611T183702+0800.sql.gz`。
- 同步前已创建 Nginx 备份 `/opt/medical-audit/backups/nginx/nginx.conf.pre-deploy-20260611T183702+0800`。
- 同步前已创建 Web 静态资产备份 `/opt/medical-audit/backups/web/audit-web-pre-deploy-20260611T183702+0800.tar.gz`。
- 远端 `.deploy-sha=de137e136ee5686b78d0cac6337b20872ee26433`，`medical_audit_app` 与 `medical_audit_pg` 均为 `healthy`。
- 主导航已从 Plan 03-11 占位模块收敛为 `/workspace` 加真实后端页面入口：`/pages/chat`、`/pages/query`、`/pages/audit-findings`、`/pages/review-tasks`、`/pages/audit-logs`、`/pages/index-admin`。
- 旧 Next.js 路由 `/guided-check`、`/rules`、`/documents`、`/findings`、`/remediation`、`/reports`、`/analytics`、`/graph`、`/archive` 保留为兼容桥接页，生产页面不再展示 `Plan 03` 至 `Plan 11` 占位文本。
- 生产只读 E2E `production-e2e-smoke-after-product-nav-bridge-20260611` 已通过；TLS、health、PostgreSQL 检索、页面渲染、查询引用、原文预览、底稿导出和边缘域名回归均为 `pass`。
- 生产 Playwright DOM 抽查已通过；`/workspace` 主导航的 7 个链接均指向预期路径，`/guided-check` 桥接到 `/pages/chat`。
- 本次部署暴露部署脚本缺陷：默认 `--report` 为空时被解析成仓库目录，导致部署主体成功后 smoke 报告写入误报 `IsADirectoryError`。已修复默认 report path 解析并补充回归测试。

### 5.15 PR #53 后端产品导航统一部署

已在 2026-06-11 合并并部署 PR #53：

- PR #53 merge commit：`5d01808229a2293be7c9466626fbb40a5d21af18`。
- 同步前已创建应用备份 `/opt/medical-audit/backups/app/pre-deploy-20260611T185250+0800.tar.gz`。
- 同步前已创建 env 备份 `/opt/medical-audit/backups/env/medical-audit.env.pre-deploy-20260611T185250+0800`。
- 同步前已创建数据库备份 `/opt/medical-audit/backups/db/pre-deploy-20260611T185250+0800.sql.gz`。
- 同步前已创建 Nginx 备份 `/opt/medical-audit/backups/nginx/nginx.conf.pre-deploy-20260611T185250+0800`。
- 同步前已创建 Web 静态资产备份 `/opt/medical-audit/backups/web/audit-web-pre-deploy-20260611T185250+0800.tar.gz`。
- 远端 `.deploy-sha=5d01808229a2293be7c9466626fbb40a5d21af18`，`medical_audit_app` 与 `medical_audit_pg` 均为 `healthy`。
- 后端真实功能页和原文预览页已统一使用共享 Jinja 产品导航，包含 `今日工作台 -> /workspace`、`对话审证`、`查询工作台`、`疑点清单`、`复核任务/底稿`、`审计日志` 和 `索引管理`。
- 生产只读 E2E `production-e2e-smoke-after-backend-nav-unification-20260611` 已通过；TLS、health、PostgreSQL 检索、页面渲染、查询引用、原文预览、底稿导出和边缘域名回归均为 `pass`。
- 生产 Playwright DOM 抽查已通过；`/pages/chat`、`/pages/query`、`/pages/audit-findings`、`/pages/review-tasks`、`/pages/audit-logs`、`/pages/index-admin` 和 `/pages/preview/{chunk_id}` 均包含 `今日工作台 -> /workspace`。
- 部署状态巡检 `tencent-cloud-deployment-state-after-pr53-20260611` 已通过，状态为 `pass`，阻断项为空。

### 5.16 PR #55 Next 原生查询工作台部署

已在 2026-06-11 合并并部署 PR #55：

- PR #55 merge commit：`92748b4d07a5f877065a5cf9f4fc372a91aed19f`。
- 同步前已创建应用备份 `/opt/medical-audit/backups/app/pre-deploy-20260611T190702+0800.tar.gz`。
- 同步前已创建 env 备份 `/opt/medical-audit/backups/env/medical-audit.env.pre-deploy-20260611T190702+0800`。
- 同步前已创建数据库备份 `/opt/medical-audit/backups/db/pre-deploy-20260611T190702+0800.sql.gz`。
- 同步前已创建 Nginx 备份 `/opt/medical-audit/backups/nginx/nginx.conf.pre-deploy-20260611T190702+0800`。
- 同步前已创建 Web 静态资产备份 `/opt/medical-audit/backups/web/audit-web-pre-deploy-20260611T190702+0800.tar.gz`。
- 远端 `.deploy-sha=92748b4d07a5f877065a5cf9f4fc372a91aed19f`，`medical_audit_app` 与 `medical_audit_pg` 均为 `healthy`。
- Next.js 静态导出已包含 `/knowledge-query`；该路由直接调用 `POST /api/v1/query`，规避生产 Nginx 对根路径 `/query` 的后端 API 精确代理冲突。
- 主导航“查询工作台”已指向 `/knowledge-query`；`/documents` 兼容桥接页也指向 `/knowledge-query`；`/pages/query` 继续作为后端兼容页保留。
- 生产 smoke `production-e2e-smoke-after-next-knowledge-query-20260611` 已通过；TLS、health、PostgreSQL 检索、页面渲染、查询引用、原文预览、底稿导出和边缘域名回归均为 `pass`。
- 生产浏览器联调 `production-next-knowledge-query-dom-api-20260611` 已通过；`/workspace` 导航、`POST /api/v1/query`、查询结果渲染、引用预览、转入对话审证和 `/documents` 桥接均为 `pass`。
- 部署状态巡检 `tencent-cloud-deployment-state-after-next-knowledge-query-20260611` 已通过，状态为 `pass`，阻断项为空。

### 5.17 PR #57 远端同步缓存清理部署

已在 2026-06-11 合并并部署 PR #57：

- PR #57 merge commit：`9bba75812819d4b1ded636617e04a1d80374df7d`。
- 同步前已创建应用备份 `/opt/medical-audit/backups/app/pre-deploy-20260611T210215+0800.tar.gz`。
- 同步前已创建 env 备份 `/opt/medical-audit/backups/env/medical-audit.env.pre-deploy-20260611T210215+0800`。
- 同步前已创建数据库备份 `/opt/medical-audit/backups/db/pre-deploy-20260611T210215+0800.sql.gz`。
- 同步前已创建 Nginx 备份 `/opt/medical-audit/backups/nginx/nginx.conf.pre-deploy-20260611T210215+0800`。
- 同步前已创建 Web 静态资产备份 `/opt/medical-audit/backups/web/audit-web-pre-deploy-20260611T210215+0800.tar.gz`。
- 远端 `.deploy-sha=9bba75812819d4b1ded636617e04a1d80374df7d`，`medical_audit_app` 与 `medical_audit_pg` 均为 `healthy`。
- 部署脚本已在备份后、rsync 前清理 `remote_app_dir/src` 下的 Python 缓存和云盘上传临时文件；`src/medical_audit_kb/topics/` 已由 rsync 成功删除。
- 部署后复核确认 `/opt/medical-audit/app/src` 下不存在 `*.uploading.cfg`，`src/medical_audit_kb/topics` 无残留内容。
- 生产 smoke `production-e2e-smoke-after-sync-artifact-cleanup-20260611` 已通过；TLS、health、PostgreSQL 检索、页面渲染、查询引用、原文预览、底稿导出和边缘域名回归均为 `pass`。
- 部署状态巡检 `tencent-cloud-deployment-state-after-sync-artifact-cleanup-20260611` 已通过，状态为 `pass`，阻断项为空。

### 5.18 PR #59 Next 原生疑点清单部署

已在 2026-06-11 合并并部署 PR #59：

- PR #59 merge commit：`47b731e049155a6ac00eaf4cd4e202deb85d4226`。
- 同步前已创建应用备份 `/opt/medical-audit/backups/app/pre-deploy-20260611T220658+0800.tar.gz`。
- 同步前已创建 env 备份 `/opt/medical-audit/backups/env/medical-audit.env.pre-deploy-20260611T220658+0800`。
- 同步前已创建数据库备份 `/opt/medical-audit/backups/db/pre-deploy-20260611T220658+0800.sql.gz`。
- 同步前已创建 Nginx 备份 `/opt/medical-audit/backups/nginx/nginx.conf.pre-deploy-20260611T220658+0800`。
- 同步前已创建 Web 静态资产备份 `/opt/medical-audit/backups/web/audit-web-pre-deploy-20260611T220658+0800.tar.gz`。
- 远端 `.deploy-sha=47b731e049155a6ac00eaf4cd4e202deb85d4226`，`medical_audit_app` 与 `medical_audit_pg` 均为 `healthy`。
- Next.js 静态导出已包含 `/findings`；主导航“疑点清单”已指向 `/findings`，后端 `/pages/audit-findings` 继续作为兼容入口和复核任务 POST 表单目标。
- 新增生产 API `GET /api/v1/audit-findings` 已通过只读联调，当前返回 `stats.total=0`、`store.ready=true`、`store.backend=SqlAlchemyAuditFindingStore`；这表示生产库当前没有规则命中疑点记录，不表示页面仍是 placeholder。
- 生产浏览器联调 `production-next-findings-dom-api-20260611` 已通过；`/findings` 页面标题为“规则命中疑点工作台”，复核状态筛选可见，兼容页链接为 `/pages/audit-findings`。
- 生产 smoke `production-e2e-smoke-after-next-findings-20260611` 已通过；TLS、health、PostgreSQL 检索、页面渲染、查询引用、原文预览、底稿导出和边缘域名回归均为 `pass`。
- 部署后发现远端历史 `opendesign` 目录残留 5 个 `*.uploading.cfg`，已先备份到 `/opt/medical-audit/backups/uploading-cfg-cleanup-20260611T141600Z.tar.gz`，再清理；复核后 `/opt/medical-audit/app` 下 `*.uploading.cfg` 数量为 `0`。
- 部署状态复核确认 `src/medical_audit_kb/topics` 不存在，`/var/www/audit/findings.html` 存在，上传临时残留为 `0`。

### 5.19 PR #61 疑点生成链路就绪诊断部署

已在 2026-06-11 合并并部署 PR #61：

- PR #61 merge commit：`3c45e46875ec4f9ca10fd07f91bf00d0f4caa461`。
- 同步前已创建应用备份 `/opt/medical-audit/backups/app/pre-deploy-20260611T225009+0800.tar.gz`。
- 同步前已创建 env 备份 `/opt/medical-audit/backups/env/medical-audit.env.pre-deploy-20260611T225009+0800`。
- 同步前已创建数据库备份 `/opt/medical-audit/backups/db/pre-deploy-20260611T225009+0800.sql.gz`。
- 同步前已创建 Nginx 备份 `/opt/medical-audit/backups/nginx/nginx.conf.pre-deploy-20260611T225009+0800`。
- 同步前已创建 Web 静态资产备份 `/opt/medical-audit/backups/web/audit-web-pre-deploy-20260611T225009+0800.tar.gz`。
- 远端 `.deploy-sha=3c45e46875ec4f9ca10fd07f91bf00d0f4caa461`，`medical_audit_app` 与 `medical_audit_pg` 均为 `healthy`。
- 生产 smoke `production-e2e-smoke-after-generation-readiness-20260611` 已通过；TLS、health、PostgreSQL 检索、页面渲染、查询引用、原文预览、底稿导出和边缘域名回归均为 `pass`。
- 生产只读联调 `production-findings-generation-readiness-20260611` 已通过；`/findings` 显示“疑点生成链路未就绪”，`/api/v1/audit-findings` 返回 `generation_readiness.status=blocked`、`ready=false`、`has_findings=false`。
- 生产 API 复核确认 `audit_projects`、`his_source_batches`、`his_table_schemas`、`his_field_mappings`、`his_staging_rows`、`audit_data_snapshots`、`audit_tasks`、`audit_runs`、`audit_rules`、`rule_versions`、`audit_findings` 和 `finding_evidence_items` 均为 `0`。
- 证据边界：本次没有写入任何 HIS 样本、规则上下文或疑点数据；只把缺失前置数据做成产品可见诊断。
- 部署状态复核确认 `src/medical_audit_kb/topics` 不存在，`/var/www/audit/findings.html` 存在，上传临时残留为 `0`。

### 5.20 CHARGE-RULE-001 fixture bootstrap 与疑点写入

已在 2026-06-11 执行受控 fixture 数据链路写入：

- fixture 写入前已创建数据库备份 `/opt/medical-audit/backups/db/pre-charge-rule-fixture-bootstrap-20260611T231102+0800.sql.gz`。
- bootstrap 写入 `audit-project-charge-fixture-v1`、`his-batch-charge-fixture-v1`、`his-schema-charge-detail-fixture-v1`、9 个 active field mappings、3 条 `his_staging_rows`、`snapshot-charge-fixture-v1`、`audit-task-charge-fixture-v1`、`CHARGE-RULE-001`、`CHARGE-RULE-001@v1` 和 `audit-run-charge-fixture-v1`。
- bootstrap 后 dry-run 通过：`finding_count=1`、`needs_evidence_count=1`、`created_finding_count=0`。
- 疑点写入前已创建数据库备份 `/opt/medical-audit/backups/db/pre-charge-rule-fixture-execute-20260611T231356+0800.sql.gz`。
- execute 写入成功：`created_finding_count=1`、`created_evidence_item_count=1`，finding key 为 `finding-f044ebd309b659dc`。
- 生产只读联调 `production-charge-rule-fixture-execute-20260611` 已通过；`/findings` 显示 `duplicate-charge` 和 `audit-run-charge-fixture-v1`，导出链接 `/audit-findings/finding-f044ebd309b659dc/export` 可用。
- 导出接口返回 `format=audit-finding-v1`、`rule_key=CHARGE-RULE-001`、`rule_version_key=CHARGE-RULE-001@v1` 和 1 条证据项。
- 证据边界：该数据为 `production-fixture-bootstrap` 受控脱敏 fixture，只证明规则生成链路和页面联通，不代表真实医院疑点或客户数据。
- 远端状态复核确认 `.deploy-sha=3c45e46875ec4f9ca10fd07f91bf00d0f4caa461`，`medical_audit_app` 与 `medical_audit_pg` healthy，`*.uploading.cfg=0`。

### 5.21 PR #64 疑点复核任务状态同步部署

已在 2026-06-12 合并并部署 PR #64：

- PR #64 merge commit：`9f98c8d36ea72a660c69f27b41a156f5a292b23a`。
- 同步前已创建应用备份 `/opt/medical-audit/backups/app/pre-deploy-20260612T095022+0800.tar.gz`。
- 同步前已创建 env 备份 `/opt/medical-audit/backups/env/medical-audit.env.pre-deploy-20260612T095022+0800`。
- 同步前已创建数据库备份 `/opt/medical-audit/backups/db/pre-deploy-20260612T095022+0800.sql.gz`。
- 同步前已创建 Nginx 备份 `/opt/medical-audit/backups/nginx/nginx.conf.pre-deploy-20260612T095022+0800`。
- 同步前已创建 Web 静态资产备份 `/opt/medical-audit/backups/web/audit-web-pre-deploy-20260612T095022+0800.tar.gz`。
- 已用正式部署脚本重建并重启 `medical_audit_app`，未重建或删除 `medical_audit_pgdata`。
- 生产只读 smoke `production-deploy-after-pr64-finding-review-sync-20260612` 已通过；TLS、health、PostgreSQL 检索、页面渲染、查询引用、原文预览、底稿导出和边缘域名回归均为 `pass`。
- 部署后 `review-task-0007` 的任务 Markdown 导出已从 `500` 修复为 `200`，返回 `AuditScope 规则疑点底稿导出`、`finding-f044ebd309b659dc`、`matched_charge_detail_ids` 和 `workpaper-fixture-20260612-0007`。
- 复核任务状态同步前已创建专项数据库备份 `/opt/medical-audit/backups/db/pre-pr64-review-task-0007-resync-20260612T095430+0800.sql.gz`。
- 已重存 `review-task-0007` 的 `confirmed-violation` 状态以触发新同步逻辑；`review_actions` 从 `7` 增至 `8`，`audit_findings.review_status` 已从 `pending-review` 同步为 `confirmed-violation`。
- `/findings` 浏览器抽查已通过：疑点统计为总数 `1`、待复核 `0`、已建任务 `1`，`finding-f044ebd309b659dc` 显示“确认违规”和“已创建复核任务：review-task-0007”。
- `review-task-0007/report-draft?format=json` 和 `format=markdown` 均可导出，报告门禁 `ready_for_report=true`，附件登记为 `2` 条。
- 部署状态巡检 `tencent-cloud-deployment-state-after-pr64-review-sync-20260612` 已通过；远端 `.deploy-sha=9f98c8d36ea72a660c69f27b41a156f5a292b23a`，`medical_audit_app` 与 `medical_audit_pg` healthy，`ai_video_nginx nginx -t` 通过，`/var/www/audit` 只读 bind mount 存在。
- 证据边界：`review-task-0007` 仍是受控脱敏 fixture 任务，只证明疑点、复核、底稿和报告草稿链路打通，不代表真实医院违规结论。

### 5.22 PR #64 后续：正式报告签发与整改跟踪 fixture 验证

已在 2026-06-12 对 `review-task-0007` 执行受控 fixture 正式报告签发和整改跟踪写入：

- 签发前已创建数据库备份 `/opt/medical-audit/backups/db/pre-pr64-review-task-0007-signoff-rectification-20260612T100832+0800.sql.gz`。
- 已通过生产页面表单签发正式报告，签发人 `fixture-signoff-owner`，签发时间 `2026-06-12T02:10:22Z`。
- 正式报告导出已通过：`/review-tasks/review-task-0007/signed-report?format=json` 返回 `format=review-task-signed-report-v1`、`signed=true`、`report_id=signed-report-03cb4bed3dd4`、`content_sha256=f16561b3f5fbab81497fb3313782609d40867cf10bee7f6d53c3ae75687c3bd5`、`attachment_count=2`；Markdown 导出返回 `review-task-0007`、`fixture-signoff-owner` 和 `finding-f044ebd309b659dc`。
- 整改写入前已创建数据库备份 `/opt/medical-audit/backups/db/pre-pr64-review-task-0007-rectification-20260612T101600+0800.sql.gz`。
- 已生成整改事项 `rectification-44526138b71e`，整改状态 `accepted`，责任科室 `fixture-charge-office`，责任人 `fixture-owner`，完成期限 `2026-06-30`。
- 整改导出已通过：`/review-tasks/review-task-0007/rectification/export?format=json` 返回 `format=review-task-rectification-v1`、`event_count=1`、`source_report_id=signed-report-03cb4bed3dd4`、`source_report_sha256=f16561b3f5fbab81497fb3313782609d40867cf10bee7f6d53c3ae75687c3bd5`；Markdown 导出返回 `AuditScope 整改跟踪记录`、`已验收 (accepted)` 和责任科室信息。
- 任务整体导出显示 `close_gate.ready_to_close=true`、`status_label=允许结案`，但任务状态仍为 `confirmed-violation`，本轮未执行结案。
- 生产只读复核确认 `/api/v1/audit-findings` 统计为总数 `1`、待复核 `0`、已建任务 `1`，`finding-f044ebd309b659dc.review_status=confirmed-violation`、`review_task_id=review-task-0007`。
- 数据库只读复核确认 `review_tasks=7`、`review_actions=10`、`review-task-0007.status=confirmed-violation`、`audit_findings.review_status=confirmed-violation`。
- `/pages/review-tasks` 浏览器联调已通过：页面可见 `review-task-0007`、`正式报告已签发`、`整改已验收`、`允许结案`、`signed-report-03cb4bed3dd4` 和 `rectification-44526138b71e`。
- 证据边界：本节只证明受控脱敏 fixture 的签发、整改、导出和结案门禁链路可用，不代表真实医院审计报告、真实整改验收或客户授权证据。

### 5.23 PR #70 AI 智能审计门户核心工作台部署

已在 2026-06-13 部署并合并 PR #70：

- PR #70 merge commit：`596d6967ba5b6c3d2a7d2253c8a31b264fb7ae82`。
- 生产部署 SHA：`32027049eb7fa2b9d336af217a228b0f21dca990`。
- 同步前已创建应用备份 `/opt/medical-audit/backups/app/pre-deploy-p5-reference-shell-20260613.tar.gz`。
- 同步前已创建 env 备份 `/opt/medical-audit/backups/env/medical-audit.env.pre-deploy-p5-reference-shell-20260613`。
- 同步前已创建数据库备份 `/opt/medical-audit/backups/db/pre-deploy-p5-reference-shell-20260613.sql.gz`。
- 同步前已创建 Nginx 备份 `/opt/medical-audit/backups/nginx/nginx.conf.pre-deploy-p5-reference-shell-20260613`。
- 同步前已创建 Web 静态资产备份 `/opt/medical-audit/backups/web/audit-web-pre-deploy-p5-reference-shell-20260613.tar.gz`。
- 已用正式部署脚本重建并重启 `medical_audit_app`，未重建或删除 `medical_audit_pgdata`。
- 已将部署同步排除规则补齐为排除 `.kiro/`、`.playwright-mcp/`、`drafts/`、`ref/`、`opendesign/`、`tmp/`、密钥和 env 文件；本次参考附件和草稿未同步到生产。
- 部署期间共享 `ai_video_nginx` 曾出现无关 upstream 漂移导致 `nginx -t` warning；部署脚本已将共享网关全局配置漂移降级为 warning，最终仍以 app health、公网 smoke、前端验收和部署状态审计作为发布门禁。
- 生产只读 smoke `production-e2e-smoke-after-p5-reference-shell-20260613` 已通过；TLS、health、PostgreSQL 检索、页面渲染、查询引用、原文预览、底稿导出和边缘域名回归均为 `pass`。
- 生产前端验收 `production-frontend-acceptance-after-p5-reference-shell-20260613` 已通过；20 个路由桌面/移动检查 `p0_count=0`、`p1_count=0`。
- 生产状态审计 `production-state-audit-after-p5-reference-shell-20260613` 已通过；远端 `.deploy-sha=32027049eb7fa2b9d336af217a228b0f21dca990`，`medical_audit_app` 与 `medical_audit_pg` healthy，`/var/www/audit` 只读 bind mount 存在，active search backend 仍为 `matching_embedding_count=48985`。
- 公网页面截图抽查已通过：`/analytics`、`/documents`、`/rules` 均返回 `200`，无横向溢出、无 console error、无 failed request。
- 证据边界：当前生产问答仍使用 citation fallback；检索、引用、预览和底稿导出可用，但不能表述为外部生成式大模型答案已完成。

### 5.24 PR #83 文档检索边界能力部署

已在 2026-06-15 合并并部署 PR #83：

- PR #83 merge commit：`f864e370abd7309f6222376074b45ef2bc6c0ff4`。
- 部署前本地 `main` worktree 已快进到 `f864e370abd7309f6222376074b45ef2bc6c0ff4`；部署从 `/Users/pray/project/medical_audit_minimal_pr` 执行。
- 部署命令使用正式脚本：`python3 scripts/deploy-tencent-cloud-production.py --execute --confirm-production audit.lute-tlz-dddd.top --allow-dirty --apply-schema`。
- 部署戳：`20260615T121812+0800`。
- 同步前已创建应用、env、数据库、Nginx 和 Web 静态资产备份；数据库备份为 `/opt/medical-audit/backups/db/pre-deploy-20260615T121812+0800.sql.gz`。
- 已用正式 schema 幂等应用 `document_upload_records` 表和相关索引。
- 已创建并挂载个人文档留存目录 `/opt/medical-audit/document-uploads`。
- 已重建并重启 `medical_audit_app`，未重建或删除 `medical_audit_pgdata`。
- 部署后普通生产 smoke `tmp/outputs/production-e2e-smoke-after-deploy-20260615T121812+0800.json` 已通过；TLS、health、PostgreSQL 检索、页面渲染、审计日志权限、查询引用、原文预览、底稿导出和边缘域名回归均为 `pass`。
- 部署状态巡检 `tmp/outputs/tencent-cloud-deployment-state-after-documents-boundary-deploy-20260615.json` 已通过；远端 `.deploy-sha=f864e370abd7309f6222376074b45ef2bc6c0ff4`，`medical_audit_app` 与 `medical_audit_pg` healthy，`ai_video_nginx nginx -t` 通过，`/var/www/audit` 只读 bind mount 存在，active search backend 仍为 `matching_embedding_count=48985`。
- 生产前端语义验收 `tmp/outputs/production-frontend-acceptance-after-documents-boundary-deploy-20260615.json` 已通过；覆盖 `21` 个路由、`42` 个检查，`p0=[]`、`p1=[]`，`/audit/logs` 与 `/audit/logs/export` 均满足无角色 `403`、管理员角色 `200`。
- `/documents` 生产写入型 E2E `tmp/outputs/production-documents-write-e2e-20260615T122620+0800-verified.json` 已通过；上传记录 `document-upload-1ba9d6e00cb7` 的 DB 行、宿主机留存文件和 `sha256` 均校验通过。
- 写入型 E2E 权限边界已验证：上传人可读本人记录，其他普通审计员不可见，管理员可读全部个人上传。
- `/api/v1/query` 来源过滤回显已验证：`medical-insurance-laws` 查询返回 1 条 citation 和 1 个 basis item，二者均回显 `source_collection=medical-insurance-laws`，同时返回 `query_log_id=9d6ec14e-1406-4e15-88b1-5978f6588891`。
- 证据边界：本轮完成个人材料留存和角色读取隔离，不等于完成个人材料实际入索引、真实登录会话、病毒扫描、DLP/脱敏改写、对象存储、下载权限隔离或长期存储生命周期策略。

### 5.25 PR #101 个人材料上传治理 provider 配置部署

已在 2026-06-16 合并并部署 PR #101：

- PR #101 merge commit：`6302f0a8baeb5695861f9682090f65786ea6d6e0`。
- 部署从 `/Users/pray/project/medical_audit_minimal_pr` 的 `main` 执行，部署前本地 `HEAD`、`origin/main` 均为 `6302f0a8baeb5695861f9682090f65786ea6d6e0`。
- 部署命令使用正式脚本：`uv run python scripts/deploy-tencent-cloud-production.py --execute --confirm-production audit.lute-tlz-dddd.top`。
- 部署戳：`20260616T135218+0800`。
- 同步前已创建应用、env、数据库、Nginx 和 Web 静态资产备份；数据库备份为 `/opt/medical-audit/backups/db/pre-deploy-20260616T135218+0800.sql.gz`，`gzip -t` 通过，大小约 `979M`。
- 已重建并重启 `medical_audit_app`，未重建或删除 `medical_audit_pgdata`。
- 部署后普通生产 smoke `tmp/outputs/production-e2e-smoke-after-deploy-20260616T135218+0800.json` 已通过；TLS、health、PostgreSQL 检索、页面渲染、审计日志权限、查询引用、原文预览、底稿导出和边缘域名回归均为 `pass`。
- 生产 `/documents` 写入型 E2E `tmp/outputs/production-documents-write-e2e-20260616T135913+0800-verified.json` 已通过；上传记录 `document-upload-f81adf853774` 的 DB 行、宿主机留存文件和 `sha256=90639f5b2a37ab3ec322067059e1f27034dcb4cd51b76794221694414e93d39e` 均校验通过。
- 写入型 E2E 权限边界已验证：上传人可读本人记录，其他普通审计员不可见，管理员可读全部个人上传。
- `index_readiness` 治理门禁已验证：病毒扫描、DLP 审查和人工入索引审批三项 check 均进入响应和 DB `metadata`；默认生产 provider 为 `unconfigured`，因此当前门禁状态仍为 `blocked`。
- 证据边界：本轮完成治理 provider 配置层和默认门禁表达，不等于完成生产级病毒扫描、DLP/脱敏改写、对象存储、下载权限隔离、个人材料实际入索引或真实登录会话。

### 5.26 PR #103 个人材料入索引审批状态机部署

已在 2026-06-16 合并并部署 PR #103：

- PR #103 merge commit：`b425e2123d55a94dc6b6c800b806384eec1de679`。
- 部署从 `/Users/pray/project/medical_audit_minimal_pr` 的 `main` 执行，部署前本地 `HEAD`、`origin/main` 均为 `b425e2123d55a94dc6b6c800b806384eec1de679`。
- 部署命令使用正式脚本：`python3 scripts/deploy-tencent-cloud-production.py --execute --confirm-production audit.lute-tlz-dddd.top --stamp pr103-index-readiness-20260616 --report tmp/outputs/production-e2e-smoke-after-pr103-index-readiness-deploy-20260616.json`。
- 部署戳：`pr103-index-readiness-20260616`。
- 同步前已创建应用、env、数据库、Nginx 和 Web 静态资产备份；数据库备份为 `/opt/medical-audit/backups/db/pre-deploy-pr103-index-readiness-20260616.sql.gz`，大小约 `979M`。
- 应用备份：`/opt/medical-audit/backups/app/pre-deploy-pr103-index-readiness-20260616.tar.gz`，大小约 `176M`。
- Web 静态资产备份：`/opt/medical-audit/backups/web/audit-web-pre-deploy-pr103-index-readiness-20260616.tar.gz`，大小约 `430K`。
- 已重建并重启 `medical_audit_app`，未重建或删除 `medical_audit_pgdata`。
- 部署后普通生产 smoke `tmp/outputs/production-e2e-smoke-after-pr103-index-readiness-deploy-20260616.json` 已通过；TLS、health、PostgreSQL 检索、页面渲染、审计日志权限、查询引用、原文预览、底稿导出和边缘域名回归均为 `pass`。
- 部署状态巡检 `tmp/outputs/tencent-cloud-deployment-state-after-pr103-index-readiness-deploy-20260616.json` 已通过；远端 `.deploy-sha=b425e2123d55a94dc6b6c800b806384eec1de679`，`medical_audit_app` 与 `medical_audit_pg` healthy，`ai_video_nginx nginx -t` 通过，`/var/www/audit` 只读 bind mount 存在，active search backend 为 `matching_embedding_count=49051`。
- 生产 `/documents` 入索引审批写入型 E2E `tmp/outputs/production-documents-index-readiness-e2e-pr103-20260616.json` 已通过。
- 审批通过路径上传记录：`document-upload-29e6f19736ed`，文件名 `production-documents-index-approval-pr103-index-readiness-20260616.txt`，上传人 `documents-e2e-owner-pr103-pr103-index-readiness-20260616`，宿主机文件 `/opt/medical-audit/document-uploads/2026/06/16/document-upload-29e6f19736ed.txt`，`sha256=d1138be8268699bf221138d5eb7d5e91abe0f471db3bac07e5bb9d7f0f63bc34`。
- 审批通过路径已验证：`department-head` 将 `manual-index-approval` check 置为 `passed`，人工审批 blocker 被清除；由于生产病毒扫描和 DLP provider 仍为 `unconfigured`，整体仍为 `blocked`，剩余 blockers 为 `virus-scan-required` 和 `dlp-review-required`。
- 审批驳回路径上传记录：`document-upload-da1a475b381b`，文件名 `production-documents-index-rejection-pr103-index-readiness-20260616.txt`，上传人 `documents-e2e-owner-pr103-pr103-index-readiness-20260616`，宿主机文件 `/opt/medical-audit/document-uploads/2026/06/16/document-upload-da1a475b381b.txt`，`sha256=c08e90a5a644725dda1effb367f7e17ddc6d87e6cf35e1fd8ba9d92746bb2284`。
- 审批驳回路径已验证：`department-head` 将 `manual-index-approval` check 置为 `blocked`，blocker 为 `manual-index-approval-rejected`，整体 `status=rejected`、`next_action=review-manual-index-rejection`。
- 权限边界已验证：普通 `auditor` 调用人工审批接口返回 `403`；上传人可读本人记录，其他普通审计员不可见，管理员可读全部个人上传。
- 审计日志已验证：`document-upload-index-approval-access-denied` 和 `document-upload-index-readiness-update` 均以 `entity_type=document-upload`、`entity_id=<upload_id>` 落库。
- 证据边界：本轮完成个人材料人工入索引审批状态机和审批审计链路，不等于完成生产级病毒扫描、DLP/脱敏改写、对象存储、下载权限隔离、个人材料实际入索引、真实登录会话或长期存储生命周期策略。

### 5.27 PR #108/#109 个人材料对象记录元数据部署

已在 2026-06-17 合并并部署 PR #108 与 PR #109：

- PR #108 merge commit：`c7e54e04b4584ee394a9f428f3de13d7c70519b9`；部署时使用 `--apply-schema` 创建 `document_storage_objects` 表及索引，部署后 `.deploy-sha=c7e54e04b4584ee394a9f428f3de13d7c70519b9`。
- PR #108 部署后普通生产 smoke `tmp/outputs/production-e2e-smoke-after-pr108-schema-gate-deploy-20260617.json` 已通过；部署状态审计 `tmp/outputs/tencent-cloud-deployment-state-after-pr108-schema-gate-20260617.json` 已通过。
- 打开对象记录开关后的首个生产写入 E2E `tmp/outputs/production-documents-storage-record-e2e-20260617.json` 失败为 `500`；根因为 ORM flush 可能先写 `document_storage_objects` 再写 `document_upload_records`，触发 FK violation。
- PR #109 merge commit：`6296cd504157171a1b212210dfe9bde1aa46b5a3`；部署戳为 `pr109-document-storage-fk-fix-20260617`，当时生产 `.deploy-sha=6296cd504157171a1b212210dfe9bde1aa46b5a3`。
- PR #109 部署后普通生产 smoke `tmp/outputs/production-e2e-smoke-after-pr109-document-storage-fk-fix-deploy-20260617.json` 已通过；部署状态巡检 `tmp/outputs/tencent-cloud-deployment-state-after-pr109-document-storage-fk-fix-20260617.json` 已通过。
- 当时生产 `MEDICAL_AUDIT_DOCUMENT_STORAGE_RECORD_OBJECTS=1`，`document_storage_objects` 对象记录写入已启用。
- 生产 `/documents` 对象记录写入型 E2E `tmp/outputs/production-documents-storage-record-e2e-after-pr109-20260617.json` 已通过；上传 `document-upload-25f283a6346e` 同时写入 `document_upload_records` 和 `document_storage_objects`。
- 验收文件：`/opt/medical-audit/document-uploads/2026/06/17/document-upload-25f283a6346e.txt`，`sha256=5a3a4fb1bb03506d1b95825d2f141b0cc05279a3f5653642f022d6bd945fa5e1`；写入后计数为 `document_upload_records=7`、`document_storage_objects=1`。
- 首次失败上传遗留孤儿文件 `/opt/medical-audit/document-uploads/2026/06/17/document-upload-51043ab42e46.txt` 已备份到 `/opt/medical-audit/backups/orphan-document-uploads/20260617/document-upload-51043ab42e46.txt.pre-delete` 并删除；备份 `sha256=89c0fee5185dbd1a42df6ae89165854f96a6f2c41d676c4cea796ac258027b3f`，删除后原路径不存在且两张表均无孤儿记录。
- 证据边界：本轮完成个人材料本地对象记录元数据和 FK flush 修复，不等于完成腾讯云 COS/外部对象存储、生产级病毒扫描、DLP/脱敏改写、下载权限隔离、真实登录会话、个人材料实际入索引或长期存储生命周期策略。

### 5.28 PR #117/#118/#121 个人材料 COS 启用、生产目录 Git 清理与下载元信息

已在 2026-06-17 完成 PR #117 生产部署、active env 切换、COS 写入型 E2E、PR #118/#119 合并、`main@936d50af` 轻量生产部署、PR #121 合并和 `main@e62254bb` 生产部署：

- PR #117 merge commit：`a276eeb2cd9018ebac52193103d17f476dbe96a6`；部署戳为 `cos-sdk-local-provider-20260617`，完成 COS 生产启用和业务镜像部署。
- PR #118 merge commit：`e8aeb34a032bfaed96aad78b80ea7a665bb5575a`；该提交修复部署脚本误同步 worktree 形态 `.git` 文件的问题。
- PR #119 merge commit：`936d50afcfa40ee350fa66ebc9a7cf596a5d1c7b`；该提交同步 COS 生产状态文档。
- PR #121 merge commit：`e62254bb5f3f142d33fdbca28d0274332f52ec90`；该提交新增 `GET /documents/uploads/{upload_id}/download` 授权元信息接口。
- `main@936d50afcfa40ee350fa66ebc9a7cf596a5d1c7b` 轻量部署戳为 `main-936d50af-dotgit-doc-sync-20260617`；该次跳过 app rebuild，运行中的 app 容器未重建。
- `main@e62254bb5f3f142d33fdbca28d0274332f52ec90` 部署戳为 `pr121-download-metadata-20260617`，当前生产 `.deploy-sha=e62254bb5f3f142d33fdbca28d0274332f52ec90`；本次已重建并重启 `medical_audit_app`。
- 本次 PR #121 自动部署脚本在远端 DB 备份完成后出现本地 SSH 子进程未退出；远端备份文件已落盘，随后人工按脚本顺序完成同步、重建、健康检查和 smoke。该现象记录为部署工具链脆弱点，不影响本轮生产运行结论。
- active env 切换前备份：`/opt/medical-audit/backups/env/medical-audit.env.pre-cos-provider-switch-20260617T163741`。
- 当前生产个人材料 storage provider 为 `tencent-cos`，COS region 为 `ap-guangzhou`，SDK bootstrap 和对象记录写入均已启用。
- 容器内直连写入 `document-upload-73805d5ac457`，公网 `/api/v1` 写入 `document-upload-6ee427e0fd91`；两条记录均写入 `document_upload_records`、`document_storage_objects` 和腾讯云 COS，并通过 COS `HEAD`。
- 最新只读复核报告：`tmp/outputs/production-documents-cos-readonly-after-main-936d50af-deploy-20260617.json`，状态 `pass`。
- 最新下载元信息只读 E2E 报告：`tmp/outputs/production-documents-download-metadata-readonly-after-pr121-20260617.json`，状态 `pass`。
- 最新部署状态巡检：`tmp/outputs/tencent-cloud-deployment-state-after-pr121-download-metadata-20260617.json`，状态 `pass`，`issues=[]`。
- 最新生产 smoke：`tmp/outputs/production-e2e-smoke-after-pr121-download-metadata-20260617.json`，状态 `pass`。
- 生产侧历史残留 `/opt/medical-audit/app/.git` 单文件已备份到 `/opt/medical-audit/backups/app/remote-dotgit-file-pre-cleanup-20260617T165949` 并删除。
- 清理后部署状态巡检：`tmp/outputs/tencent-cloud-deployment-state-after-dotgit-cleanup-20260617.json`，状态 `pass`，`issues=[]`。
- 证据边界：本轮完成个人材料 COS 对象存储、部署目录 Git 清理、#121 业务部署 SHA 与生产 `.deploy-sha` 对齐，以及下载元信息授权隔离；PR #122 是 docs-only 状态同步，未触发生产轻量同步。不等于完成生产级病毒扫描、DLP/脱敏改写、真实文件下载交付、签名 URL、真实登录会话、个人材料实际入索引或长期存储生命周期策略。

## 6. 后续维护流程

### 6.1 代码与资产同步

首选使用正式脚本做预检：

```bash
uv run python scripts/deploy-tencent-cloud-production.py \
  --ssh-key ./ai_video.pem
```

预检通过后再执行生产写入：

```bash
uv run python scripts/deploy-tencent-cloud-production.py \
  --execute \
  --confirm-production audit.lute-tlz-dddd.top \
  --ssh-key ./ai_video.pem
```

常用开关：

- schema 变更部署：追加 `--apply-schema`。
- 只同步静态前端或文档、不重建 app：追加 `--skip-app-rebuild`。
- 已提前生成 `web/out/`：追加 `--skip-web-build`。
- 验证复核写入链路：追加 `--include-review-write`；执行前必须确认数据库备份已完成。

脚本执行的同步规则：

1. 执行 `pnpm web:build:static`，确认 `web/out/` 已生成。
2. 将当前工作树同步到 `/opt/medical-audit/app/`。
3. 排除 `.git`、`.git/`、`.venv/`、`tmp/`、`data/`、`archive/`、缓存、密钥和本地环境文件。
4. 将 `web/out/` 同步到宿主机 `/var/www/audit/`。`ai_video_nginx` 已将该目录以只读方式挂载到容器内，不再需要常规执行 `docker cp`。
5. 抽查公网 HTML 中 `_next/static/chunks` 是否与本次构建一致；只有在 bind mount 异常或容器临时目录丢失时，才允许把 `docker cp /var/www/audit/. ai_video_nginx:/var/www/audit` 作为应急手段。

手工同步只作为脚本失败时的排障路径。需要同步 `data/医保审核前期资料` 或 `tmp/knowledge-query-indexes/real-data-kimi-20260531` 时，先确认是否属于索引数据更新任务，不并入普通应用部署。

### 6.1.1 部署后状态巡检

每次生产部署、Nginx 变更、静态前端热修或写入型 E2E 后，必须执行部署状态巡检：

```bash
uv run python scripts/audit-tencent-cloud-deployment-state.py \
  --ssh-key ./ai_video.pem \
  --expected-deploy-sha <当前生产 .deploy-sha> \
  --required-backup-stamp <本次部署备份戳>
```

巡检失败时先处理阻断项，不继续执行新的部署或回滚。报告中的 `issues` 是处置入口：

- `deploy-sha-mismatch`：先确认是否存在“代码已合并但未部署”的正常差异。
- `medical_audit_app-not-healthy`：先查看 app 容器日志和 healthcheck，不直接重建数据库。
- `nginx-config-test-failed`：恢复最近的 Nginx 备份后再 reload。
- `audit-static-bind-mount-missing`：检查共享 Nginx Compose 中 `/var/www/audit:/var/www/audit:ro`。
- `search-backend-not-ready`：检查 PostgreSQL 容器、env 和 active index，不先动前端静态文件。
- `missing-required-backup-stamp:*`：先补齐或确认备份，不继续写入型 E2E。

### 6.2 数据库导入

1. 确认 `medical_audit_pg` healthy。
2. 执行 `pgvector-import-plan`，确认 artifact 完整。
3. 执行 `pgvector-import --execute` 写入 `candidate`。
4. 执行 `medical-audit-kb index-activate` 激活目标版本。
5. 查询数据库计数：
   - `source_documents = 503`
   - `document_chunks = 49051`
   - `chunk_embeddings = 49051`
   - `failed_files = 0`
   - `pending_files = 0`

### 6.3 应用启动

1. 在 `/opt/medical-audit/app/configs/deploy/tencent-cloud/medical-audit.env` 写入运行环境变量。
2. `docker compose -f docker-compose.prod.yaml --env-file medical-audit.env build app`
3. `docker compose -f docker-compose.prod.yaml --env-file medical-audit.env up -d app`
4. 应用容器启动后必须自动加载 PostgreSQL search backend。
5. 后端 ready 门槛：
   - `backend = postgres`
   - `ready = true`
   - `matching_embedding_count = 49051`

### 6.4 nginx 与证书

1. 备份 `/opt/ai-video/deploy/lighthouse/nginx.conf`。
2. 先把 `audit.lute-tlz-dddd.top` 加入 80 端口 `server_name`，保证 ACME challenge 可达。
3. 执行 `nginx -t`。
4. reload `ai_video_nginx`。
5. 使用 certbot webroot 扩展 SAN，加入 `audit.lute-tlz-dddd.top`。
6. 将 `configs/deploy/tencent-cloud/nginx-audit-server.conf` 中的 server block 合并到 nginx `http` 块。
7. 再次执行 `nginx -t`。
8. reload `ai_video_nginx`。

## 7. 测试计划

### 7.1 服务器内部测试

```bash
docker compose -f configs/deploy/tencent-cloud/docker-compose.prod.yaml \
  --env-file configs/deploy/tencent-cloud/medical-audit.env ps

curl -fsS http://127.0.0.1:18080/health
curl -fsS http://127.0.0.1:18080/index/search-backend
curl -fsS 'http://127.0.0.1:18080/pages/chat?question=医保基金审核依据'
```

### 7.2 容器网络测试

```bash
docker exec ai_video_nginx wget -qO- http://medical_audit_app:8000/health
docker exec ai_video_nginx wget -qO- http://medical_audit_app:8000/index/search-backend
```

### 7.3 公网域名测试

```bash
curl -I https://audit.lute-tlz-dddd.top/health
curl -fsS https://audit.lute-tlz-dddd.top/index/search-backend
curl -fsS 'https://audit.lute-tlz-dddd.top/pages/chat?question=医保基金审核依据'
```

### 7.4 功能 smoke

必须覆盖：

- `/pages/chat` 能返回对话审证页。
- `/pages/query` 能返回查询工作台。
- `/pages/review-tasks` 能返回复核任务台。
- `/pages/index-admin` 能返回索引管理页。
- 对话查询返回引用。
- 引用可打开 `/pages/preview/{chunk_id}`。
- 单轮底稿可导出 Markdown/JSON。
- 复核任务可创建、更新、导出。

### 7.5 视觉基线

公网切换后执行：

```bash
uv run python scripts/capture-chat-workbench-visual-baseline.py \
  --base-url https://audit.lute-tlz-dddd.top \
  --report tmp/outputs/knowledge-query-chat-visual-baseline-prod.json
```

通过条件：

- `status = pass`
- desktop/mobile 均无横向溢出。
- 关键文案无缺失。

### 7.6 生产 E2E smoke

公网部署、证书更新、依赖重启或知识库索引切换后执行：

```bash
uv run python scripts/run-production-e2e-smoke.py \
  --base-url https://audit.lute-tlz-dddd.top \
  --report tmp/outputs/production-e2e-smoke-latest.json
```

默认覆盖范围：

- TLS 证书 SAN。
- `/health` 和公网 `/api/v1/index/search-backend`，由 Nginx 转发到后端 `/index/search-backend`。
- `/pages/chat`、`/pages/query`、`/pages/review-tasks`、`/pages/index-admin`。
- 公网 `/api/v1/query` 引用型回答，由 Nginx 转发到后端 `/query`。
- `/pages/preview/{chunk_id}` 原文预览。
- `/pages/chat/export` 底稿导出。
- 现有 `kg`、`video`、`voc`、主域名回归。

默认生产巡检保持只读，不创建复核任务。只有在明确需要验证 PostgreSQL 复核写入流时，才使用：

```bash
uv run python scripts/run-production-e2e-smoke.py \
  --base-url https://audit.lute-tlz-dddd.top \
  --include-review-write \
  --report tmp/outputs/production-e2e-smoke-with-review-write-latest.json
```

### 7.6.1 生产前端语义验收

静态前端热修、导航改版、视觉系统变更或产品入口整合后，执行只读前端语义验收：

```bash
pnpm production:frontend-acceptance -- \
  --base-url https://audit.lute-tlz-dddd.top \
  --output tmp/outputs/production-frontend-acceptance-latest.json \
  --screenshot-dir tmp/screenshots/production-frontend-acceptance-latest \
  --admin-role it-admin
```

标准复用模板：

```bash
pnpm production:frontend-acceptance -- \
  --base-url https://audit.lute-tlz-dddd.top \
  --output tmp/outputs/production-frontend-acceptance-latest.json \
  --screenshot-dir tmp/screenshots/production-frontend-acceptance-latest \
  --admin-role it-admin
```

该脚本覆盖 Next 原生门户和后端深链页面的桌面/移动视口，检查状态码、控制台错误、失败请求、横向溢出、占位文案、关键业务信号、AI 数据分析上传入口、智能体提示词入口和项目成员管理入口。

该脚本新增以下 API 鉴权闭环：

- `/audit/logs` 和 `/audit/logs/export`：无 `X-Role` 期望 `403`，`X-Role: it-admin`（或 `--admin-role` 指定值）期望 `200`。
- 报告 `summary.api_checks` 必须包含 `/audit/logs` 与 `/audit/logs/export` 两个路径，且 `denied_status=403`、`allowed_status=200`。
- 无需提交业务数据；脚本只读。

### 7.7 增量更新 dry-run 演练

新增源文档后，先只生成增量计划，不直接构建或激活索引：

```bash
medical-audit-kb index-incremental-plan \
  --source-root /opt/medical-audit/app/data/医保审核前期资料 \
  --package-version-key source-package-$(date +%Y%m%d%H%M%S) \
  --database-url-env MEDICAL_AUDIT_KB_DATABASE_URL \
  --output /opt/medical-audit/app/tmp/outputs/knowledge-query-incremental-plan-latest.md \
  --json-output /opt/medical-audit/app/tmp/outputs/knowledge-query-incremental-plan-latest.json
```

通过条件：

- `ready_for_incremental_build = true`。
- `failed_files = 0`。
- `added_files`、`modified_files`、`deleted_files` 与预期源文件变更一致。
- 不改变 `index_versions.active`、`source_documents`、`document_chunks`、`chunk_embeddings` 当前计数。

### 7.8 审计日志归档定时巡检

生产环境必须先创建受控目录，并限制为部署用户和应用容器可读写：

```bash
sudo mkdir -p /opt/medical-audit/audit-log-archive /opt/medical-audit/audit-reports
sudo chown -R ubuntu:ubuntu /opt/medical-audit/audit-log-archive /opt/medical-audit/audit-reports
chmod 750 /opt/medical-audit/audit-log-archive /opt/medical-audit/audit-reports
```

`configs/deploy/tencent-cloud/medical-audit.env` 必须包含：

```bash
MEDICAL_AUDIT_AUDIT_LOG_ARCHIVE_ROOT_HOST=/opt/medical-audit/audit-log-archive
MEDICAL_AUDIT_AUDIT_LOG_ARCHIVE_REPORT_DIR_HOST=/opt/medical-audit/audit-reports
MEDICAL_AUDIT_AUDIT_LOG_SIGNING_SECRET=replace-with-hmac-secret
MEDICAL_AUDIT_AUDIT_LOG_MIN_MANIFEST_COUNT=0
MEDICAL_AUDIT_AUDIT_LOG_ALERT_WEBHOOK_URL=
MEDICAL_AUDIT_AUDIT_LOG_ALERT_TIMEOUT_SECONDS=10
MEDICAL_AUDIT_AUDIT_LOG_SEND_SUCCESS_ALERT=0
MEDICAL_AUDIT_AUDIT_LOG_ALERT_FAIL_ON_ERROR=0
```

手动巡检：

```bash
cd /opt/medical-audit/app
docker compose -f configs/deploy/tencent-cloud/docker-compose.prod.yaml \
  --env-file configs/deploy/tencent-cloud/medical-audit.env \
  exec -T app python scripts/run-audit-log-archive-audit.py
```

定时任务示例：

```cron
17 3 * * * cd /opt/medical-audit/app && docker compose -f configs/deploy/tencent-cloud/docker-compose.prod.yaml --env-file configs/deploy/tencent-cloud/medical-audit.env exec -T app python scripts/run-audit-log-archive-audit.py >> /opt/medical-audit/audit-reports/audit-log-archive-audit-cron.log 2>&1
```

告警判定：

- 脚本退出码 `0`：巡检通过。
- 脚本退出码 `2`：归档缺失、路径逃逸、sha256 不匹配、签名失败或 manifest 数量不足，必须按审计事件处理。
- 其他非零退出码：环境错误或密钥缺失，必须先修复运行环境，不能视为无归档异常。
- 配置 `MEDICAL_AUDIT_AUDIT_LOG_ALERT_WEBHOOK_URL` 后，脚本会在失败或异常时发送最小 JSON webhook 告警；默认成功不发送。
- 手动验收外部告警通道时，可临时传入 `--send-success-alert`；若要求 webhook 失败也阻断验收，再同时传入 `--fail-on-alert-error`。
- 最新机器可读报告固定为 `/opt/medical-audit/audit-reports/audit-log-archive-audit-latest.json`。

### 7.9 个人材料 COS bootstrap 只读 preflight

COS 生产启用必须分成三步：依赖和脚本先部署、候选 env 只读 preflight、最后才允许应用重启和写入型 E2E。任一步失败都停止，不进入下一步。2026-06-17 个人材料上传链路已按该流程启用腾讯云 COS；后续仍按本节作为回归和新环境启用 SOP。

前置条件：

- 当前代码已包含 `cos-python-sdk-v5` 运行时依赖。
- 当前代码已包含 `scripts/run-document-cos-bootstrap-preflight.py`。
- 远端 `configs/deploy/tencent-cloud/medical-audit.env` 已备份，权限保持 `600`。
- COS bucket、region、secret env name 和 secret value 已通过远端 env 或等价密钥注入方式准备好。
- 尚未重启 `medical_audit_app`，尚未执行 `/documents` 写入型 E2E。

候选 env 必须包含：

```bash
MEDICAL_AUDIT_DOCUMENT_STORAGE_PROVIDER=tencent-cos
MEDICAL_AUDIT_DOCUMENT_STORAGE_COS_BUCKET=<bucket-with-appid>
MEDICAL_AUDIT_DOCUMENT_STORAGE_COS_REGION=ap-guangzhou
MEDICAL_AUDIT_DOCUMENT_STORAGE_COS_PREFIX=personal-materials/prod
MEDICAL_AUDIT_DOCUMENT_STORAGE_COS_SECRET_ID_ENV=COS_SECRET_ID
MEDICAL_AUDIT_DOCUMENT_STORAGE_COS_SECRET_KEY_ENV=COS_SECRET_KEY
MEDICAL_AUDIT_DOCUMENT_STORAGE_COS_ENCRYPTION=sse-cos
MEDICAL_AUDIT_DOCUMENT_STORAGE_COS_STORAGE_CLASS=STANDARD
MEDICAL_AUDIT_DOCUMENT_STORAGE_COS_SDK_BOOTSTRAP=1
COS_SECRET_ID=<remote-secret-value>
COS_SECRET_KEY=<remote-secret-value>
```

只读 preflight 使用一次性容器执行，不能复用已运行 app 容器的旧环境：

```bash
cd /opt/medical-audit/app
docker compose -f configs/deploy/tencent-cloud/docker-compose.prod.yaml \
  --env-file configs/deploy/tencent-cloud/medical-audit.env \
  run --rm --no-deps app \
  python scripts/run-document-cos-bootstrap-preflight.py \
  --config /app/configs/knowledge-query-engine-dev.yaml
```

通过条件：

- 退出码为 `0`。
- JSON `status` 为 `pass`。
- `provider_is_tencent_cos=true`。
- `cos_sdk_bootstrap_enabled=true`。
- bucket、region、secret env name 和 secret env value 均为 present。
- `qcloud_cos_available=true`。
- 输出中不得出现 `COS_SECRET_ID` 或 `COS_SECRET_KEY` 的真实值。

阻断条件：

- 退出码为 `2` 或 JSON `status=blocked`。
- 任一 `issues` 非空。
- 输出包含真实 secret value。
- 一次性容器执行过程中出现网络上传、`/documents` 写入或对象创建证据。

阻断后的处置：

1. 不重启 `medical_audit_app`。
2. 不执行 `/documents` 生产写入型 E2E。
3. 恢复或修正远端 `medical-audit.env`。
4. 重新执行只读 preflight，直到 `status=pass`。

## 8. 验收标准

当前已通过的验收：

- `https://audit.lute-tlz-dddd.top/health` 返回 `200`。
- TLS 证书 SAN 包含 `audit.lute-tlz-dddd.top`。
- `/index/search-backend` 返回 `ready=true`。
- `matching_embedding_count=49051`。
- `/pages/chat` 页面可访问，并能渲染带引用的查询结果。
- `/pages/query`、`/pages/review-tasks`、`/pages/index-admin` 均返回 `200`。
- `/query` 公网调用返回 `confidence=high`、`citation_count=3`、`basis_group_count=2`。
- `/pages/preview/{chunk_id}` 可打开首条引用原文预览。
- `/pages/chat/export?format=markdown` 可导出带引用的审计底稿。
- `scripts/run-production-e2e-smoke.py` 默认只读生产 E2E 已通过；默认流程不创建复核任务。
- 复核任务创建、状态更新与导出只在显式传入 `--include-review-write` 时执行。
- 视觉基线脚本通过 desktop/mobile 检查，未发现横向溢出或关键文案缺失。
- 2026-06-15 国家规章平台稳定增量激活已通过，当前 active source documents 为 `503`，active embeddings 为 `49051`；旧的 `486/48985/48985` 仅作为 2026-06-03 至 2026-06-14 历史基线保留。
- 初始索引回滚就绪审计已执行，旧状态下生产库 `active=1`、`inactive=0`、`rollback_target=0`，真实 rollback 被安全阻止且数据库计数未变化。
- candidate 发布就绪审计已执行：active-key artifact 被 `candidate-index-version-key-matches-active` 阻断，旧 candidate `full-rebuild-20260603081846` 被 48,985 个 active chunk id 跨 source package 碰撞阻断，数据库计数均未变化。
- package-aware chunk id 修复已部署到生产镜像，新 fixed candidate `full-rebuild-20260603085815` 构建完成，`embedding_reused_count=48985`，`embedding_created_count=0`，pending/failed 均为 `0`。
- fixed candidate 的 `pgvector-import-plan` 和 `pgvector-import` dry-run 通过，发布就绪审计返回 `status=pass`、`safe_to_execute_candidate_write=true`、`chunk_collision_check.collision_count=0`。
- 受控 candidate 写入已执行，生产库曾包含 active `full-rebuild-20260531142344` 和 candidate `full-rebuild-20260603085815`；总计 `source_documents=972`、`document_chunks=97970`、`chunk_embeddings=97970`。
- 受控 `index-activate` 已执行，2026-06-03 当时 active 为 `full-rebuild-20260603085815`，旧 active `full-rebuild-20260531142344` 已变为 inactive。
- 线上 PostgreSQL search backend 当时已重载，`/index/search-backend` 返回 `matching_embedding_count=48985`，查询引用版本为 `full-rebuild-20260603085815`。
- candidate DB vector self-query 通过，candidate PostgreSQL 固定 52 case 检索评测通过，candidate fallback 答案评测 8 case 全部通过。
- 生产只读 E2E smoke `production-e2e-smoke-readonly-after-candidate-fix-20260603` 通过；TLS、health、PostgreSQL 检索后端、页面渲染、查询引用、原文预览、底稿导出和边缘域名回归均为 `pass`，复核任务写入流已跳过。
- 生产只读 E2E smoke `production-e2e-smoke-readonly-after-candidate-write-20260603` 通过；证明 candidate 写入后线上 active 查询未回归。
- 激活后线上综合评测 run `45f56a84-c4a8-4ad3-8450-e2b1cce1b786` 通过：52 case 检索、8 case fallback 答案和 UI smoke 均为 `pass`。
- 生产只读 E2E smoke `production-e2e-smoke-readonly-after-activation-20260603` 通过；首条引用已来自新 active chunk。
- rollback readiness `knowledge-query-index-rollback-readiness-after-activation-20260603` 通过，`rollback_target_count=1`。
- 真实 rollback rehearsal 已执行：`knowledge-query-index-rollback-rehearsal-to-20260531-20260603` 将 active 临时切回 `full-rebuild-20260531142344`，reload 后查询引用版本、生产只读 E2E 和线上综合评测均通过。
- rehearsal 已切回新 active：`knowledge-query-index-rollback-rehearsal-return-to-20260603-20260603` 将 active 恢复为 `full-rebuild-20260603085815`，reload 后查询引用版本、生产只读 E2E、线上综合评测和 rollback readiness 均通过。
- `main` 合并后已同步部署到腾讯云，`production-e2e-smoke-readonly-after-main-deploy-20260603` 通过；TLS、health、PostgreSQL 检索后端、页面渲染、查询引用、原文预览、底稿导出和边缘域名回归均为 `pass`。
- PR #5 已合并并部署到腾讯云，merge commit 为 `4fd2d5032c09cdd0f306cf79150744c52e11b8b9`。
- 部署前已创建应用备份 `/opt/medical-audit/backups/app/pre-pr5-sync-20260604T033000Z.tar.gz` 和 schema 备份 `/opt/medical-audit/backups/db/pre-pr5-schema-20260604T033000Z.sql`。
- `sql/knowledge-query-schema.sql` 已在生产库幂等执行，`review_tasks` 已补齐 `reviewer_note` 和 `conclusion` 两列。
- 生产只读 E2E smoke `production-e2e-smoke-readonly-after-review-task-postgres-store-20260604` 通过；TLS、health、PostgreSQL 检索后端、页面渲染、查询引用、原文预览、底稿导出和边缘域名回归均为 `pass`。
- 生产写入型 E2E smoke `production-e2e-smoke-with-review-write-after-review-task-postgres-store-20260604` 通过；创建并关闭 `review-task-0001`，任务导出成功。
- app 重启后 `review-task-0001` 仍可导出，数据库直接查询返回 `review_task_count=1`、`review_action_count=1`，active 计数保持 `486/48985/48985`。
- 重启后生产只读 E2E smoke `production-e2e-smoke-readonly-after-review-task-postgres-store-restart-20260604` 通过。
- 审计日志归档巡检调度已部署，`/etc/cron.d/medical-audit-archive-audit` 每天 `03:17` CST 执行只读巡检，latest JSON 报告当前为 `status=pass`、`manifest_count=0`、`failed_count=0`。
- webhook 告警能力已部署到 `medical_audit_app`；当前真实 webhook URL 为空，`--send-success-alert --fail-on-alert-error` 会按预期返回 `2`，防止未配置告警通道时误判验收通过。
- 生产库已通过正式 schema SQL 补齐 `audit_log_events`，部署后 `/index/search-backend` 返回 `backend=postgres`、`ready=true`、`matching_embedding_count=48985`。
- 生产只读 E2E smoke `production-e2e-smoke-after-archive-scheduler-20260605` 通过；TLS、health、PostgreSQL 检索后端、页面渲染、查询引用、原文预览、底稿导出和边缘域名回归均为 `pass`。
- 生产只读 E2E smoke `production-e2e-smoke-after-webhook-alert-20260605` 通过；TLS、health、PostgreSQL 检索后端、页面渲染、查询引用、原文预览、底稿导出和边缘域名回归均为 `pass`。
- PR #41 已合并并部署到腾讯云，merge commit 为 `6cc17e09878a0a8baff21d8789aac8d21891c6d7`。
- 生产只读 E2E smoke `production-e2e-smoke-after-pr41-ui-20260605` 通过；TLS、health、PostgreSQL 检索后端、页面渲染、查询引用、原文预览、底稿导出和边缘域名回归均为 `pass`。
- 生产视觉基线 `knowledge-query-chat-visual-baseline-prod-after-pr41-ui-20260605` 通过；desktop/mobile 均无横向溢出，关键文案无缺失。
- 医保基金使用合规专题入口已部署到生产，`/pages/chat?audit_topic=fund-usage-compliance` 可见专题入口且提交后保留专题参数。
- `/query` 专题请求返回 `audit_topic=fund-usage-compliance`、`confidence=high`、`citation_count=3`、`basis_group_count=2`，首条引用可打开原文预览。
- 生产只读 E2E `production-e2e-smoke-after-fund-topic-deploy-20260606` 通过。
- 生产视觉基线 `knowledge-query-chat-visual-baseline-prod-after-fund-topic-deploy-20260606` 通过。
- 生产认证桥接、静态前端热修、共享 Nginx bind mount 固化、部署自动化入口、产品导航真实功能入口、后端产品导航统一、Next 原生查询工作台、远端同步缓存清理、Next 原生疑点清单、疑点生成链路就绪诊断、CHARGE-RULE-001 受控 fixture 疑点生成、疑点复核任务状态同步、正式报告签发、整改跟踪 fixture 验证和 AI 智能审计门户核心工作台部署均已完成；该历史阶段对应的生产部署 SHA 曾为 `32027049eb7fa2b9d336af217a228b0f21dca990`，fixture finding 为 `finding-f044ebd309b659dc`，关联 `review-task-0007`。
- PR #83 文档检索边界能力已部署到生产；当前 `.deploy-sha=f864e370abd7309f6222376074b45ef2bc6c0ff4`，个人上传记录 `document-upload-1ba9d6e00cb7` 已通过 DB 行、宿主机文件和角色读取隔离验收。
- 生产只读 E2E `production-e2e-smoke-after-deploy-20260611-external-ai` 通过；TLS、health、PostgreSQL 检索后端、页面渲染、查询引用、原文预览、底稿导出和边缘域名回归均为 `pass`。
- 生产视觉基线 `knowledge-query-chat-visual-baseline-prod-after-deploy-20260611` 通过；desktop/mobile 均无横向溢出，关键文案无缺失。
- 生产写入型 E2E `production-e2e-smoke-with-review-write-after-deploy-20260611` 通过；创建、关闭并导出 `review-task-0003`，数据库 `review_tasks/review_actions` 计数均按预期增加 1。
- PR #45 合并后生产写入型 E2E `production-e2e-smoke-with-review-write-after-pr45-main-deploy-20260611` 通过；创建、关闭并导出 `review-task-0004`。
- 生产静态前端热修后，浏览器前后端联调已通过；旧 Next.js chunk 导致的 `/api/v1/api/v1/*` 404 已消除，`review-task-0005`、`review-task-0006` 已通过 UI 表单写入和导出验证。
- 共享 `ai_video_nginx` 已完成 `/var/www/audit:/var/www/audit:ro` bind mount 固化；`production-e2e-smoke-after-nginx-bind-mount-20260611` 通过，`kg`、`video`、`voc`、主域名回归均为 `200`。
- CHARGE-RULE-001 受控 fixture 已写入生产并生成 1 条疑点；`/api/v1/audit-findings.generation_readiness.status=generated`，`/findings` 显示 `finding-f044ebd309b659dc`，导出接口返回 1 条证据项。
- 受控 fixture 疑点已创建复核任务并完成状态同步；`/api/v1/audit-findings` 中 `finding-f044ebd309b659dc.review_status=confirmed-violation`，`review-task-0007` 任务 Markdown 和报告草稿 JSON/Markdown 导出均可用。
- 受控 fixture 复核任务已完成正式报告签发与整改跟踪验收；`signed-report-03cb4bed3dd4`、`rectification-44526138b71e`、签发报告 JSON/Markdown、整改 JSON/Markdown 和 `close_gate.ready_to_close=true` 均已验证，任务未结案。
- 回归抽查 `kg`、`video`、`voc`、`lute-tlz-dddd.top` 均返回正常状态。

部署验收必须同时满足：

- `https://audit.lute-tlz-dddd.top/health` 返回 `200`。
- TLS 证书 SAN 包含 `audit.lute-tlz-dddd.top`。
- `/index/search-backend` 返回 `ready=true`。
- `matching_embedding_count=49051`。
- `/pages/chat`、`/pages/query`、`/pages/review-tasks`、`/pages/index-admin` 均返回 `200`。
- `/findings` 返回 Next 原生疑点工作台，主导航“疑点清单”指向 `/findings`。
- `/api/v1/audit-findings` 返回 `200`，且 `store.ready=true`。
- 生产未导入 HIS 业务数据底座时，`/api/v1/audit-findings.generation_readiness.status` 必须明确返回 `blocked`，页面必须显示缺失的前置数据，而不是只显示低信息量空态。
- 生产已写入受控 fixture 时，`/api/v1/audit-findings.generation_readiness.status` 必须返回 `generated`，`/findings` 必须显示 `finding-f044ebd309b659dc` 或当前受控 fixture 疑点。
- 受控 fixture 疑点创建复核任务并更新状态后，`/api/v1/audit-findings` 与 `/findings` 必须显示同步后的复核状态，`review-task-0007` 任务 Markdown 和报告草稿导出不得返回 `500`。
- 受控 fixture 复核任务签发和整改后，签发报告 JSON/Markdown、整改 JSON/Markdown、`close_gate.ready_to_close=true` 和“任务未结案”状态必须同时可验证。
- 生产前端语义验收 `pnpm production:frontend-acceptance -- --base-url https://audit.lute-tlz-dddd.top --admin-role it-admin` 返回 `status=pass`，P0/P1 均为 `0`；`summary.api_checks` 必须显示 `"/audit/logs"` 与 `"/audit/logs/export"` 为 `denied_status=403` 且 `allowed_status=200`。
- `/documents` 个人上传链路必须证明 DB 行、宿主机留存文件 `sha256`、本人可读、其他普通审计员不可读和管理员可读全部上传同时成立；个人上传未入索引时必须明确显示 `index_status=not-indexed`。
- 索引管理写接口拒绝审计必须证明普通审计角色访问 `/api/v1/index/versions/activate` 返回 `403`，且持久化审计日志中可按 `action=index-admin-access-denied` 与 `user_identifier` 查到对应事件。
- 固定 smoke question 返回至少 1 条引用。
- 原文预览可打开。
- 底稿导出和复核任务导出可用。
- 现有域名 `kg`、`video`、`voc`、`person`、`mkt` 不出现回归。
- `docker ps` 中原有容器持续 healthy 或保持部署前状态。

## 9. 待补强事项

- `pending_files = 13` 已完成分类：`11` 个图片需 OCR 或替换为文本/xlsx 原件，`2` 个压缩包需解包、去重和范围审查。
- 当前 active source subset 的增量 dry-run 为 `pending_files = 0`，但数据库历史 pending 记录仍为 `13`，两者含义不同。
- 修复前生成的旧 candidate artifact 仍禁止写入；只有 package-aware chunk id 修复后生成并通过 readiness gate 的 fixed candidate 才允许进入受控 candidate 写入步骤。
- 当前 fixed candidate 已完成受控写入、候选评测、active 激活、后置综合评测、生产 smoke 和真实 rollback rehearsal。
- rehearsal 后最终状态为 active `full-rebuild-20260603085815`、inactive `full-rebuild-20260531142344`。
- 真实 `index-rollback` 演练已执行并已切回新 active；当前仍有 inactive 目标 `full-rebuild-20260531142344`，再次演练前必须重新确认业务窗口和备份路径。
- 当前远端只同步 active source subset；如果后续要求远端具备完整源文件再处理能力，需要先解决超长中文文件名归档策略。
- `KIMI_API_KEY` 当前写入远端 env，后续应迁移到服务器级 secret 管理或 Docker secret，降低误操作风险。
- `MEDICAL_AUDIT_AUDIT_LOG_SIGNING_SECRET` 当前写入远端 env，后续应迁移到服务器级 secret 管理或 Docker secret。
- 真实生成模型启用仍被 chat provider key 阻塞；未通过 `answer-provider-smoke` 前，不得配置 `MEDICAL_AUDIT_KB_ANSWER_*` 或部署 no-fallback 验收。
- 审计日志 archive root 巡检已接入 cron，webhook 告警能力已具备；真实外部告警端点尚未配置时，只能通过 cron 退出码和 `/opt/medical-audit/audit-reports/` 报告排查。
- nginx 仍由共享 `ai_video_nginx` 承载公网入口；新增域名必须继续走备份、`nginx -t`、reload、回归抽查四步。

### 2026-06-15 索引管理拒绝审计部署

- 部署提交：`a3111bf615995bd03a95514c49447cd82087e5ab`。
- 部署戳：`index-admin-denial-audit-20260615`。
- 变更范围：索引管理写接口非 `it-admin` 拒绝时记录 `index-admin-access-denied`，并保留 `attempted_action`、`user_identifier`、`role`、`status_code` 和拒绝原因。
- 同步前已创建应用、env、数据库、Nginx 和 Web 静态资产备份。
- 写入前 DB 备份：`/opt/medical-audit/backups/db/pre-deploy-index-admin-denial-audit-20260615.sql.gz`，大小 `1025901424` bytes。
- 已重建并重启 `medical_audit_app`；`medical_audit_pg` 保持 running/healthy，未重建或删除 `medical_audit_pgdata`。
- 部署后基础 smoke：`tmp/outputs/production-e2e-smoke-after-index-admin-denial-audit-deploy-20260615.json`，状态 `pass`；TLS、health、PostgreSQL 检索、页面渲染、审计日志权限、查询引用、原文预览、底稿导出和边缘域名回归均通过。
- 部署状态巡检：`tmp/outputs/tencent-cloud-deployment-state-after-index-denial-deploy-20260615.json`，状态 `pass`，`issues=[]`；远端 `.deploy-sha=a3111bf615995bd03a95514c49447cd82087e5ab`，`medical_audit_app` 与 `medical_audit_pg` healthy，`ai_video_nginx nginx -t` 通过，`/var/www/audit` 只读 bind mount 存在，active search backend 为 `matching_embedding_count=49051`。
- 专项权限 smoke：`tmp/outputs/production-index-admin-denial-audit-smoke-20260615.json`，状态 `pass`；普通审计角色访问 `/api/v1/index/versions/activate` 返回 `403`，管理员角色查询持久化审计日志返回 `matching_count=1`。
- 证据边界：本轮只证明索引管理写接口拒绝审计落库，不等于完成真实登录会话、科室级授权、组织模型、全站 RBAC 或生产 no-fallback 生成模型能力。

### 2026-06-15 门户配置写入拒绝审计部署

- 部署提交：`6ae514cf994ff0d0da612d5ea9bcce82bb7df1bc`。
- 部署戳：`portal-config-denial-audit-20260615`。
- 变更范围：智能体和项目成员写接口遇到未知 `X-Role` 时返回 `403`，并分别记录 `agent-access-denied` 与 `project-member-access-denied`，payload 保留 `attempted_action`、`user_identifier`、`role`、`status_code` 和拒绝原因。
- 同步前已创建应用、env、数据库、Nginx 和 Web 静态资产备份。
- 写入前 DB 备份：`/opt/medical-audit/backups/db/pre-deploy-portal-config-denial-audit-20260615.sql.gz`，大小 `1025903476` bytes。
- 已重建并重启 `medical_audit_app`；`medical_audit_pg` 保持 running/healthy，未重建或删除 `medical_audit_pgdata`。
- 部署后基础 smoke：`tmp/outputs/production-e2e-smoke-after-portal-config-denial-deploy-20260615.json`，状态 `pass`；TLS、health、PostgreSQL 检索、页面渲染、审计日志权限、查询引用、原文预览、底稿导出和边缘域名回归均通过。
- 部署状态巡检：`tmp/outputs/tencent-cloud-deployment-state-after-portal-config-denial-deploy-20260615.json`，状态 `pass`，`issues=[]`；远端 `.deploy-sha=6ae514cf994ff0d0da612d5ea9bcce82bb7df1bc`，`medical_audit_app` 与 `medical_audit_pg` healthy，`ai_video_nginx nginx -t` 通过，`/var/www/audit` 只读 bind mount 存在，active search backend 为 `matching_embedding_count=49051`。
- 生产前端验收：`tmp/outputs/production-frontend-acceptance-after-portal-config-denial-deploy-20260615.json`，状态 `pass`，覆盖 `21` 个路由、`42` 个检查，`p0_count=0`、`p1_count=0`。
- 专项权限 smoke：`tmp/outputs/production-portal-config-denial-audit-smoke-20260615.json`，状态 `pass`；`guest` 角色写 `/api/v1/agents` 和 `/api/v1/projects/SELF-CHECK-FUND-20260607/members` 均返回 `403`，并在持久化 `audit_log_events` 中分别记录 `agent-access-denied` 与 `project-member-access-denied`。
- 证据边界：本轮只证明门户配置写接口未知角色拒绝审计落库，不等于完成真实登录会话、科室级授权、组织模型、全站 RBAC 或生产 no-fallback 生成模型能力。

### 2026-06-15 权限上下文兼容层部署

- 部署提交：`bebcf57043197ff45dfff1185e071a1cf2d7d808`。
- 部署戳：`auth-rbac-phase-a-20260615`。
- 变更范围：新增 `CurrentUser`、`PermissionContext`、`it-admin -> system-admin` 角色归一化、legacy header 权限上下文兼容层和统一 `auth_source=legacy-header` 审计 payload。
- 同步前已创建应用、env、数据库、Nginx 和 Web 静态资产备份。
- 写入前 DB 备份：`/opt/medical-audit/backups/db/pre-deploy-auth-rbac-phase-a-20260615.sql.gz`，大小约 `979M`。
- 已重建并重启 `medical_audit_app`；`medical_audit_pg` 保持 running/healthy，未重建或删除 `medical_audit_pgdata`。
- 部署后基础 smoke：`tmp/outputs/production-e2e-smoke-after-auth-rbac-phase-a-deploy-20260615.json`，状态 `pass`；TLS、health、PostgreSQL 检索、页面渲染、审计日志权限、查询引用、原文预览、底稿导出和边缘域名回归均通过。
- 部署状态巡检：`tmp/outputs/tencent-cloud-deployment-state-after-auth-rbac-phase-a-deploy-20260615.json`，状态 `pass`，`issues=[]`；远端 `.deploy-sha=bebcf57043197ff45dfff1185e071a1cf2d7d808`，`medical_audit_app` 与 `medical_audit_pg` healthy，`ai_video_nginx nginx -t` 通过，`/var/www/audit` 只读 bind mount 存在，active search backend 为 `matching_embedding_count=49051`。
- 生产前端验收：`tmp/outputs/production-frontend-acceptance-after-auth-rbac-phase-a-deploy-20260615.json`，状态 `pass`，覆盖 `21` 个路由、`42` 个检查，`p0_count=0`、`p1_count=0`。
- 专项 RBAC smoke：`tmp/outputs/production-auth-rbac-phase-a-smoke-20260615.json`，状态 `pass`；旧 `it-admin` 兼容、新 `system-admin`、未授权审计日志拒绝、index/agent/project-member 写入拒绝及拒绝审计 payload 均已验证。
- 证据边界：本轮只证明 legacy header 权限上下文兼容层和关键写接口拒绝审计链路，不等于完成真实登录会话、组织/科室级授权、会话态前端切换或全站细粒度 RBAC。

### 2026-06-16 部署脚本 SSH stdin 修复生产部署

- PR #95 `codex/deploy-tooling-debt-fix` 修复了部署巡检脚本和备份调用的第一层问题，但生产部署验证仍在 DB 备份完成后挂起；该 PR 不能作为有效生产部署完成态。
- PR #96 `codex/deploy-pgdump-stdin-fix` 将 DB 备份改为 plain `docker exec medical_audit_pg ... pg_dump`，但生产部署验证仍在 DB 备份完成后挂起；该 PR 不能作为有效生产部署完成态。
- PR #97 `codex/deploy-ssh-stdin-fix` 将远端脚本式 `_ssh` 调用改为 `ssh -n`，保留 `rsync` 原传输方式，已完成生产部署。
- 部署提交：`4901d6705a60494542f42b98aa0e6766e3224114`。
- 部署戳：`ssh-stdin-fix-20260616`。
- 写入前 DB 备份：`/opt/medical-audit/backups/db/pre-deploy-ssh-stdin-fix-20260616.sql.gz`，`gzip -t` 通过，大小约 `979M`。
- 应用备份：`/opt/medical-audit/backups/app/pre-deploy-ssh-stdin-fix-20260616.tar.gz`，大小约 `176M`。
- Web 静态资产备份：`/opt/medical-audit/backups/web/audit-web-pre-deploy-ssh-stdin-fix-20260616.tar.gz`，大小约 `430K`。
- 部署后基础 smoke：`tmp/outputs/production-e2e-smoke-after-ssh-stdin-fix-deploy-20260616.json`，状态 `pass`。
- 部署状态巡检：`tmp/outputs/tencent-cloud-deployment-state-after-ssh-stdin-fix-deploy-20260616.json`，状态 `pass`，`issues=[]`；远端 `.deploy-sha=4901d6705a60494542f42b98aa0e6766e3224114`，`medical_audit_app` 与 `medical_audit_pg` healthy，`ai_video_nginx nginx -t` 通过，active search backend 为 `matching_embedding_count=49051`。
- 生产前端验收：`tmp/outputs/production-frontend-acceptance-after-ssh-stdin-fix-deploy-20260616.json`，状态 `pass`，覆盖 `21` 个路由、`42` 个检查，`p0=[]`、`p1=[]`。
- 证据边界：本轮是部署工具链脆弱点修复，不等于新增产品功能、权限模型、生成模型、schema 或生产配置能力。

## 10. 回滚方案

回滚前置门禁：

```bash
uv run python scripts/audit-tencent-cloud-deployment-state.py \
  --ssh-key ./ai_video.pem \
  --expected-deploy-sha <当前生产 .deploy-sha> \
  --required-backup-stamp <待回滚部署的备份戳>
```

只有在巡检报告能定位当前 SHA、容器状态、Nginx 状态和备份路径时，才进入回滚执行。

应用回滚：

```bash
cd /opt/medical-audit/app/configs/deploy/tencent-cloud
docker compose -f docker-compose.prod.yaml --env-file medical-audit.env stop app
```

nginx 回滚：

1. 恢复部署前备份的 `/opt/ai-video/deploy/lighthouse/nginx.conf`。
2. `docker exec ai_video_nginx nginx -t`
3. `docker exec ai_video_nginx nginx -s reload`

数据库保留：

- 默认保留 `medical_audit_pgdata` 以便排障。
- 如需彻底清理，必须先确认用户同意，再删除 volume。

## 11. 不允许事项

- 不复用其它项目数据库。
- 不把 `KIMI_API_KEY` 写入 git。
- 不把任何 chat provider key 写入 git、PR 评论、报告正文、前端静态文件或客户端可见配置。
- 不在 `answer-provider-smoke` 未通过时写入 `MEDICAL_AUDIT_KB_ANSWER_*` 并声称 no-fallback 已启用。
- 不把 `data/` 打进镜像。
- 不直接覆盖 nginx 配置而不备份。
- 不在证书 SAN 未包含 `audit` 时声称 HTTPS 已完成。
- 不以 HTTP `200` 作为唯一验收标准，必须检查页面内容、后端 ready 和引用链。
- 不允许在 COS bootstrap 只读 preflight 通过前把 `MEDICAL_AUDIT_DOCUMENT_STORAGE_PROVIDER` 切到 `tencent-cos` 并重启生产 app。
- 不允许把 COS secret 真实值写入 git、PR 正文、验收报告或终端摘要。

---
title: 腾讯云 AuditScope 知识库网站部署工作流
doc_type: workflow
module: deployment
topic: tencent-cloud-audit-lute-tlz-dddd
status: stable
created: 2026-06-03
updated: 2026-06-11
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

### 2026-06-11 当前事实

- 当前生产部署 SHA：`e8e04f11 fix: 让生产外部 AI 开关尊重环境配置`。
- `medical_audit_app` 容器 healthy，宿主机仅暴露 `127.0.0.1:18080->8000`。
- `medical_audit_pg` 容器 healthy，继续使用独立 volume `medical_audit_pgdata`。
- 公网 `https://audit.lute-tlz-dddd.top/` 返回 `200`，`/api/v1/index/search-backend` 返回 `backend=postgres`、`ready=true`、`matching_embedding_count=48985`。
- 生产认证桥接已采用 Nginx 内部注入 `X-API-Key`，secret 只保存在远端 Nginx 配置与 env 中，未进入 Git、镜像或本地文档。
- `MEDICAL_AUDIT_KB_ALLOW_EXTERNAL_AI` 已改为由远端 `medical-audit.env` 控制；当前生产 env 显式为 `1`，用于支持 query embedding，出站前 PII 扫描仍由 `egress_policy` 执行。
- `ai_video_nginx` 仍为共享公网入口；本次只修改 `audit.lute-tlz-dddd.top` 对应 server block，没有重启或改动 `ai_video_frontend`、`voc_superset`、`promptforge_app` 等其它业务容器。

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
- `scripts/run-audit-log-archive-audit.py`
- `.dockerignore`

密钥策略：

- `ai_video.pem` 只用于本地 SSH，不进入镜像。
- `KIMI_API_KEY` 只允许写入远端 `medical-audit.env`，权限必须为 `600`。
- `MEDICAL_AUDIT_AUDIT_LOG_SIGNING_SECRET` 只允许写入远端 `medical-audit.env`，用于审计日志归档 HMAC 验签；不得写入 git、报告或签名 manifest。
- 任何 `*.env`、`*.pem`、`*.key` 不允许进入 git。

## 5. 已执行上线记录

### 5.1 数据导入结果

远端 pgvector 已完成导入和激活：

- active `source_documents = 486`
- active `document_chunks = 48985`
- active `chunk_embeddings = 48985`
- total `source_documents = 972`
- total `document_chunks = 97970`
- total `chunk_embeddings = 97970`
- `failed_files = 0`
- `pending_files = 13`
- `index_version_status = active`
- `active_index_version_key = full-rebuild-20260603085815`

说明：

- `pending_files = 13` 表示索引构建时仍有待处理源文件记录，不阻断当前 active index 使用。
- 本次远端只同步 active index 实际引用的 486 个源文件，避免长中文文件名导致 rsync 失败。
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
- `matching_embedding_count = 48985`

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

## 6. 后续维护流程

### 6.1 代码与资产同步

1. 在本地完成全量验证。
2. 执行 `pnpm web:build:static`，确认 `web/out/` 已生成。
3. 将当前工作树同步到 `/opt/medical-audit/app/`。
4. 排除 `.git/`、`.venv/`、`tmp/debug/`、缓存、密钥和本地临时文件。
5. 将 `web/out/` 同步到 `/var/www/audit/`，供 `audit.lute-tlz-dddd.top` 的 Nginx 静态根目录使用。
6. 同步 `data/医保审核前期资料`，用于原文预览。
7. 同步 `tmp/knowledge-query-indexes/real-data-kimi-20260531`，用于一次性导入 pgvector。

### 6.2 数据库导入

1. 确认 `medical_audit_pg` healthy。
2. 执行 `pgvector-import-plan`，确认 artifact 完整。
3. 执行 `pgvector-import --execute` 写入 `candidate`。
4. 执行 `medical-audit-kb index-activate` 激活目标版本。
5. 查询数据库计数：
   - `source_documents = 486`
   - `document_chunks = 48985`
   - `chunk_embeddings = 48985`
   - `failed_files = 0`
   - `pending_files = 13`

### 6.3 应用启动

1. 在 `/opt/medical-audit/app/configs/deploy/tencent-cloud/medical-audit.env` 写入运行环境变量。
2. `docker compose -f docker-compose.prod.yaml --env-file medical-audit.env build app`
3. `docker compose -f docker-compose.prod.yaml --env-file medical-audit.env up -d app`
4. 应用容器启动后必须自动加载 PostgreSQL search backend。
5. 后端 ready 门槛：
   - `backend = postgres`
   - `ready = true`
   - `matching_embedding_count = 48985`

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

## 8. 验收标准

当前已通过的验收：

- `https://audit.lute-tlz-dddd.top/health` 返回 `200`。
- TLS 证书 SAN 包含 `audit.lute-tlz-dddd.top`。
- `/index/search-backend` 返回 `ready=true`。
- `matching_embedding_count=48985`。
- `/pages/chat` 页面可访问，并能渲染带引用的查询结果。
- `/pages/query`、`/pages/review-tasks`、`/pages/index-admin` 均返回 `200`。
- `/query` 公网调用返回 `confidence=high`、`citation_count=3`、`basis_group_count=2`。
- `/pages/preview/{chunk_id}` 可打开首条引用原文预览。
- `/pages/chat/export?format=markdown` 可导出带引用的审计底稿。
- `scripts/run-production-e2e-smoke.py` 默认只读生产 E2E 已通过；默认流程不创建复核任务。
- 复核任务创建、状态更新与导出只在显式传入 `--include-review-write` 时执行。
- 视觉基线脚本通过 desktop/mobile 检查，未发现横向溢出或关键文案缺失。
- 增量更新 dry-run 已通过，486 个 active source files 全部 `unchanged`，新增/修改/删除/失败均为 `0`。
- 初始索引回滚就绪审计已执行，旧状态下生产库 `active=1`、`inactive=0`、`rollback_target=0`，真实 rollback 被安全阻止且数据库计数未变化。
- candidate 发布就绪审计已执行：active-key artifact 被 `candidate-index-version-key-matches-active` 阻断，旧 candidate `full-rebuild-20260603081846` 被 48,985 个 active chunk id 跨 source package 碰撞阻断，数据库计数均未变化。
- package-aware chunk id 修复已部署到生产镜像，新 fixed candidate `full-rebuild-20260603085815` 构建完成，`embedding_reused_count=48985`，`embedding_created_count=0`，pending/failed 均为 `0`。
- fixed candidate 的 `pgvector-import-plan` 和 `pgvector-import` dry-run 通过，发布就绪审计返回 `status=pass`、`safe_to_execute_candidate_write=true`、`chunk_collision_check.collision_count=0`。
- 受控 candidate 写入已执行，生产库曾包含 active `full-rebuild-20260531142344` 和 candidate `full-rebuild-20260603085815`；总计 `source_documents=972`、`document_chunks=97970`、`chunk_embeddings=97970`。
- 受控 `index-activate` 已执行，当前 active 为 `full-rebuild-20260603085815`，旧 active `full-rebuild-20260531142344` 已变为 inactive。
- 线上 PostgreSQL search backend 已重载，`/index/search-backend` 返回 `matching_embedding_count=48985`，查询引用版本为 `full-rebuild-20260603085815`。
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
- 生产认证桥接与前后端联调已部署到生产，最终 `.deploy-sha=e8e04f11`。
- 生产只读 E2E `production-e2e-smoke-after-deploy-20260611-external-ai` 通过；TLS、health、PostgreSQL 检索后端、页面渲染、查询引用、原文预览、底稿导出和边缘域名回归均为 `pass`。
- 生产视觉基线 `knowledge-query-chat-visual-baseline-prod-after-deploy-20260611` 通过；desktop/mobile 均无横向溢出，关键文案无缺失。
- 生产写入型 E2E `production-e2e-smoke-with-review-write-after-deploy-20260611` 通过；创建、关闭并导出 `review-task-0003`，数据库 `review_tasks/review_actions` 计数均按预期增加 1。
- 回归抽查 `kg`、`video`、`voc`、`lute-tlz-dddd.top` 均返回正常状态。

部署验收必须同时满足：

- `https://audit.lute-tlz-dddd.top/health` 返回 `200`。
- TLS 证书 SAN 包含 `audit.lute-tlz-dddd.top`。
- `/index/search-backend` 返回 `ready=true`。
- `matching_embedding_count=48985`。
- `/pages/chat`、`/pages/query`、`/pages/review-tasks`、`/pages/index-admin` 均返回 `200`。
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
- 审计日志 archive root 巡检已接入 cron，webhook 告警能力已具备；真实外部告警端点尚未配置时，只能通过 cron 退出码和 `/opt/medical-audit/audit-reports/` 报告排查。
- nginx 仍由共享 `ai_video_nginx` 承载公网入口；新增域名必须继续走备份、`nginx -t`、reload、回归抽查四步。

## 10. 回滚方案

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
- 不把 `data/` 打进镜像。
- 不直接覆盖 nginx 配置而不备份。
- 不在证书 SAN 未包含 `audit` 时声称 HTTPS 已完成。
- 不以 HTTP `200` 作为唯一验收标准，必须检查页面内容、后端 ready 和引用链。

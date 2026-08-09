---
title: "Sprint-6 上线加固预检报告"
doc_type: precheck
module: project-governance
status: active
created: 2026-08-09
updated: 2026-08-09
owner: self
source: human+ai
---

# Sprint-6 上线加固预检报告

## 概述

本文档基于 2026-08-09 本地脚本只读探测结果，对 Sprint-6「上线加固」所需的四个前提条件进行预检。所有结论均为本地只读证据，生产执行须单独授权。

---

## 1. SSO 认证可信代理（P0）

**预检命令**：`uv run python scripts/audit-auth-sso-contract-readiness.py`

**当前状态**：`status=blocked`

**阻断项**（9 个 env 均为 UNSET）：

| 环境变量 | 说明 | 状态 |
|---|---|---|
| `MEDICAL_AUDIT_SSO_PROVIDER_URL` | SSO provider 地址 | UNSET |
| `MEDICAL_AUDIT_SSO_TRUSTED_HEADER` | 可信代理 header 名称 | UNSET |
| `MEDICAL_AUDIT_SSO_TRUSTED_PROXY_IPS` | 可信代理 IP 白名单 | UNSET |
| `MEDICAL_AUDIT_SSO_TENANT_ID` | 租户 ID | UNSET |
| `MEDICAL_AUDIT_SESSION_SIGNING_SECRET` | session 签名密钥 | UNSET |
| `MEDICAL_AUDIT_SESSION_COOKIE_DOMAIN` | cookie 域 | UNSET |
| `MEDICAL_AUDIT_SSO_USER_CLAIM` | 用户标识 claim | UNSET |
| `MEDICAL_AUDIT_SSO_ROLE_CLAIM` | 角色 claim | UNSET |
| `MEDICAL_AUDIT_SSO_DEPT_CLAIM` | 科室 claim | UNSET |

**当前风险**：`auth_mode=header_transition_layer`，X-Role header 可自行构造，生产写入型权限 E2E 不安全。

**解决路径**：

选项 A（推荐）：Nginx 可信代理模式
- 院方 Nginx 在内网边界注入 `X-Authenticated-User` 和 `X-Authenticated-Role`
- 应用层只信任来自内网代理 IP 的 header，拒绝外部直接访问
- 配置量最小，无需第三方 SSO SDK

选项 B：SAML/OAuth2 标准集成
- 需院方提供 IdP 元数据 URL 或 client_id/secret
- 需集成 python-saml 或 authlib
- 实施周期 1–2 周

**下一步**：与院方确认 SSO 方案（A/B），院方提供配置参数后方可实施。

---

## 2. 数据备份 pg_restore 恢复演练（P1）

**当前状态**：备份脚本已实现（`scripts/deploy-tencent-cloud-production.py`），每次部署前自动执行全量 pg_dump + gzip，存储在 `/opt/medical-audit/backups/transactions/`。

**尚未完成**：
- 从生产备份文件到干净 PostgreSQL 实例的完整 `pg_restore` 恢复演练
- gzip 完整性检查已通过，DDL 可解析，但**未验证实际数据行能否完整恢复**

**恢复演练步骤（待执行）**：

```bash
# 1. 从生产复制最新备份（只读）
scp -i /path/to/key.pem user@prod:/opt/medical-audit/backups/transactions/<stamp>/*.sql.gz /tmp/restore-test/

# 2. 启动干净测试 PostgreSQL（与生产版本一致）
docker run -d --name pg-restore-test \
  -e POSTGRES_PASSWORD=test \
  -p 5434:5432 \
  pgvector/pgvector:pg16

# 3. 解压并 restore
gunzip < /tmp/restore-test/<backup>.sql.gz | \
  docker exec -i pg-restore-test psql -U postgres

# 4. 验证关键表行数
docker exec pg-restore-test psql -U postgres -c "
  SELECT 'audit_findings' AS t, COUNT(*) FROM audit_findings
  UNION SELECT 'review_tasks', COUNT(*) FROM review_tasks
  UNION SELECT 'remediation_items', COUNT(*) FROM remediation_items;
"

# 5. 清理
docker stop pg-restore-test && docker rm pg-restore-test
```

**验收标准**：关键表行数与生产快照一致，无 error 输出。

**预计耗时**：30 分钟（含备份下载时间）。

---

## 3. 告警 Webhook 配置（P1）

**当前状态**：

```
# configs/deploy/tencent-cloud/medical-audit.env.example
MEDICAL_AUDIT_AUDIT_LOG_ALERT_WEBHOOK_URL=
```

审计日志巡检 cron 已启用（`scripts/run-audit-log-archive-audit.py`），但 webhook 为空，巡检失败时无外部通知。

**配置方法**：

```bash
# 钉钉 webhook（推荐）
MEDICAL_AUDIT_AUDIT_LOG_ALERT_WEBHOOK_URL=https://oapi.dingtalk.com/robot/send?access_token=<TOKEN>

# 企业微信 webhook
MEDICAL_AUDIT_AUDIT_LOG_ALERT_WEBHOOK_URL=https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=<KEY>
```

**验收测试**：
```bash
# 触发测试告警（模拟归档失败）
uv run python scripts/run-audit-log-archive-audit.py \
  --archive-root /tmp/nonexistent \
  --webhook-url $MEDICAL_AUDIT_AUDIT_LOG_ALERT_WEBHOOK_URL
# 期望：webhook 收到告警消息
```

**下一步**：院方/团队提供钉钉 webhook URL，填入生产 env 后重启 app 容器。

---

## 4. 压测覆盖（P2）

**当前状态**：无压测脚本，无 baseline 数据。

**关键路径**（按风险排序）：

| 路径 | 预期 QPS | 瓶颈风险 | 优先级 |
|---|---|---|---|
| `POST /api/v1/query` | 5–10 | pgvector 相似搜索 + provider call | P0 |
| `GET /api/v1/audit-findings` | 20–50 | 全表聚合 + 权限过滤 | P1 |
| `GET /api/v1/remediation/workbench` | 10–20 | 多表 JOIN | P1 |
| `POST /api/v1/reports/drafts/{id}/signoff` | 1–5 | DB 写入 + docx 生成 | P2 |

**推荐工具**：k6（已在 pnpm 生态中可用）

**最小可用压测脚本骨架**：

```javascript
// scripts/k6-query-baseline.js
import http from "k6/http";
import { check, sleep } from "k6";

export const options = {
  vus: 5,
  duration: "30s",
  thresholds: { http_req_duration: ["p(95)<3000"] }
};

export default function () {
  const res = http.post(
    "https://audit.lute-tlz-dddd.top/api/v1/query",
    JSON.stringify({ question: "分解住院的判定标准是什么？", top_k: 3 }),
    { headers: { "Content-Type": "application/json", "X-Role": "auditor" } }
  );
  check(res, { "status 200": (r) => r.status === 200 });
  sleep(1);
}
```

**验收标准**：p95 < 3s，无 5xx 错误，知识查询不因并发触发 pgvector 超时。

---

## 5. UAT 脚本和培训材料（P2）

**当前状态**：无面向院方的验收脚本和操作手册。

**需要准备**：

1. **院方 UAT 验收脚本**（Excel/问卷格式）：
   - 知识查询：输入 3 个典型问题，验证答案有引用来源
   - 疑点查看：按项目筛选，查看详情，创建复核任务
   - 报告签发：从草稿到签发的完整流程
   - 整改跟踪：创建整改、上传附件、更新状态

2. **操作手册**（PDF，面向医院审计科）：
   - 登录方式
   - 主要功能模块截图说明
   - 常见问题 Q&A

**建议负责人**：产品/业务同学主导，AI 辅助生成初稿。

---

## 总结：Sprint-6 上线加固 GO/NO-GO 矩阵

| 项目 | 当前状态 | 是否阻塞上线 | 负责方 | 预计解决时间 |
|---|---|---|---|---|
| SSO 认证 | `blocked`，外部依赖 | **是** | 院方 + 开发 | 院方确认协议后 1 周 |
| pg_restore 演练 | 未执行 | 建议上线前完成 | 开发 | 0.5 天 |
| 告警 webhook | URL 未配置 | 否（功能可用，通知缺失） | 院方/团队 | 0.5 小时 |
| 压测覆盖 | 无 baseline | 建议上线前完成 | 开发 | 1–2 天 |
| UAT 脚本 | 未编写 | 是（院方签字需要） | 产品/业务 | 1 周 |

**当前 Sprint-6 状态**：`blocked`（SSO + UAT 脚本是外部依赖）

**可立即执行的非阻塞项**：pg_restore 演练 + 告警 webhook 配置 + 压测 baseline 脚本编写

---
title: "Sprint-5 执行完成交付文档（含生产部署）"
doc_type: delivery
module: project-governance
status: superseded
created: 2026-08-09
updated: 2026-08-13
owner: self
source: human+ai
target_agent: codex
---

# Sprint-5 执行完成交付文档

> 本文是 2026-08-09 的历史部署收据，当前生产身份仍需以新鲜 L3 只读证据为准。当前权威入口见 [文档索引](../../docs/README.md)。

## 一、本次执行范围

本文档覆盖 2026-08-09 基于交接文档 `handoff-to-codex-sprint5-20260809.md` 所完成的 Task 1–6 全部执行结果，含生产部署和 L4 前端验收。

---

## 二、各 Task 自证交付

### Task 1（P0）✅ — 整改状态操作按钮 UI

**commit**：`6d1d291d feat(remediation): implement StatusActionButtons with status-machine flow and fix attachment itemId`

**变更文件**：
- `web/src/components/replica/replica-remediation-workbench.tsx`
- `web/src/components/replica/replica-remediation-workbench.test.tsx`
- `web/src/lib/api-types.ts`

**实现内容**：

```
STATUS_TRANSITIONS 状态机：
  pending-rectification → 开始整改 (in-rectification)
  in-rectification      → 提交验收 (pending-acceptance)
  pending-acceptance    → 验收通过 (accepted) | 退回整改 (rejected)
  rejected              → 重新整改 (in-rectification)
  accepted              → 关闭事项 (closed)
  closed                → 无操作按钮
```

交互流：点击操作 → 展开 note 输入（可选）→ 确认 → `POST /api/v1/remediation/items/{id}/status` → 成功后自动刷新工作台。

**证据**：
- vitest `410/410` 通过（含 4 个新增测试）
- typecheck 无错误
- ruff 全绿

---

### Task 2（P0）✅ — push + 生产部署 + L3/L4 验收

**push**：本地 5 commits → `origin/main`（`d31a1b1d` → `970a8dc4`）

**生产部署**：

```
deploy_sha: 25e1654e0c44ca5cbb2bb42e82debdb40fa6f224
医院域名:   https://audit.lute-tlz-dddd.top
部署时间:   2026-08-09T01:35Z
```

**容器状态（SSH 直接验证）**：

```
medical_audit_app:    Up ~2 min (healthy)
medical_audit_pg:     Up 3 days (healthy)
medical_audit_clamav: Up 2 weeks (healthy)
```

**L3 只读验收**：
- `status=pass`，`issues=[]`
- `evidence_grade=L3-production-read-only`
- `deploy_sha=25e1654e0c44ca5cbb2bb42e82debdb40fa6f224` ✅
- 报告：`tmp/outputs/deploy-state-sprint5-20260809.json`

**内置 E2E smoke**（部署脚本自动执行）：

```json
{
  "status": "pass",
  "evidence_grade": "L3-production-read-only",
  "steps": {
    "tls-certificate-san": "passed",
    "health": "passed",
    "search-backend": "passed (49051 embeddings)",
    "page-rendering": "passed (/ 200, /login 200)"
  }
}
```

**L4 前端验收**（`run-production-frontend-acceptance.mjs`）：

```
acceptance_run_id: fa-20260809t100000z-25e1654e
status: pass
p0_count: 0
p1_count: 0
routes: 20 independent + 3 aliases × 2 viewports (desktop/mobile) = 46 checks
```

**验收过程修复**（同步提交）：
- commit `970a8dc4`：`/workspace` alias `expectedPath` 从 `/chat` 更新为 `/workspace`；`/audit-cockpit` 文本合同从 `进入项目管理` 更新为 `项目管理`（匹配 Sprint-5 实际组件）

---

### Task 3（P0）✅ — 整改附件映射真实 UUID

**同 Task 1 commit `6d1d291d`**

`evidence_requests` 区域附件上传已改为直接使用 `item.id`（真实 UUID），移除了 `linkedCaseId ?? item.id` fallback。后端 `POST /api/v1/remediation/items/{item_id}/attachments` 接受 UUID 路径参数，两端对齐。

---

### Task 4（P1）✅ — workspace 待复核 API 端点验证

**结论**：后端完全支持，无需新增代码。

`GET /api/v1/audit-findings?review_status=pending-review`（`routes_query.py:1329`）返回 `{ items: AuditFinding[], stats: {...} }`，包含 `finding_key`、`severity`，与 `workspace/page.tsx` 消费格式完全一致。

---

### Task 5（P2）✅ — CSS 完整性验证

`StatusActionButtons` 所用全部 CSS 类均已在 `globals.css` 中存在：

| CSS 类 | 行号 | 状态 |
|---|---|---|
| `.remediation-item-actions` | 5204 | ✅ |
| `.remediation-status-actions` | 5211 | ✅ |
| `.remediation-status-action-group` | 5218 | ✅ |
| `.remediation-note-input` | 5224 | ✅ |
| `.remediation-status-done` | ~5240 | ✅ |

---

### Task 6（P2）✅ — Sprint-6 上线加固预检文档

**commit**：`c656ebb6 docs: add sprint-6 on-site hardening precheck report`

**文件**：`drafts/analysis/sprint6-precheck-20260809.md`

| 项目 | 状态 | 阻塞上线 |
|---|---|---|
| SSO 认证 | `blocked`（9 个 env UNSET） | **是**（外部依赖院方） |
| pg_restore 演练 | 未执行，有步骤文档 | 建议完成 |
| 告警 webhook | URL 为空，有配置说明 | 否 |
| 压测 | 无 baseline，有骨架脚本 | 建议完成 |
| UAT 脚本 | 未编写，有需求清单 | **是**（院方签字需要） |

---

## 三、最终 git 状态

```
origin/main: 970a8dc4（本地与远端同步）
生产 deploy_sha: 25e1654e0c44ca5cbb2bb42e82debdb40fa6f224
测试: vitest 410/410，ruff 全绿，typecheck 无错误
工作树: clean
```

**本次新增 commits**：

```
970a8dc4  fix(acceptance): update workspace alias and audit-cockpit text contracts for sprint-5
25e1654e  docs: sprint-5 task execution delivery report
c656ebb6  docs: add sprint-6 on-site hardening precheck report
6d1d291d  feat(remediation): implement StatusActionButtons with status-machine flow and fix attachment itemId
6b5110ad  docs: update state register + add sprint-5 baseline + codex handoff
226d3d0d  fix(replica): localize collection labels and update acceptance text contracts
```

---

## 四、下一步执行优先级（给 Codex）

### 立即可执行（无外部依赖）

**[1] pg_restore 恢复演练**（详见 `sprint6-precheck-20260809.md` 第 2 节）

```bash
# 从生产复制最新备份
scp -i DDDD.pem ubuntu@101.34.52.232:/opt/medical-audit/backups/transactions/<stamp>/*.sql.gz /tmp/restore-test/
# 启动测试 PG，restore，验证行数
```

**[2] 告警 webhook 配置**

```bash
# 在生产 .env 中填入：
MEDICAL_AUDIT_AUDIT_LOG_ALERT_WEBHOOK_URL=https://oapi.dingtalk.com/robot/send?access_token=<TOKEN>
# 重启 app 容器
docker-compose -f docker-compose.prod.yaml restart app
```

**[3] 压测 baseline**：创建 `scripts/k6-query-baseline.js`，在 staging 环境运行 p95 < 3s 测试

### 依赖外部输入（等待院方）

**[4] SSO 方案确认**：选 A（Nginx 可信代理）或 B（SAML/OAuth2），院方确认后 1 周实施

**[5] UAT 脚本**：产品/业务同学主导，基于 `sprint6-precheck-20260809.md` 第 5 节需求清单

---

## 五、不可逾越边界

1. `git push --force` 禁止
2. 生产部署须显式 `--execute`
3. provider call 须单独授权
4. `auth_mode=header_transition_layer`：不得声称 SSO 完成
5. 生产 5 条疑点为脱敏样本：不可作为真实 HIS 规则引擎结论

---

*交付时间：2026-08-09 | 交付方：Sisyphus | 接收方：Codex*

## 历史正文说明

2026-08-13 复盘时移除了本文件误追加的第二份“部署前”正文。原始内容仍可通过 Git 历史追溯；当前状态请以 [文档索引](../../docs/README.md) 和 [项目复盘与差异审计](project-reanalysis-and-gap-audit-20260813.md) 为准。

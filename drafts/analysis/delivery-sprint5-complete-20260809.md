---
title: "Sprint-5 执行完成交付文档"
doc_type: delivery
module: project-governance
status: active
created: 2026-08-09
updated: 2026-08-09
owner: self
source: human+ai
target_agent: codex
---

# Sprint-5 执行完成交付文档

## 一、本次执行范围

本文档覆盖 2026-08-09 基于交接文档 `handoff-to-codex-sprint5-20260809.md` 所完成的 Task 1–6 全部执行结果。

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

交互流：点击操作 → 展开 note 输入（可选） → 确认 → `POST /api/v1/remediation/items/{id}/status` → 成功后自动刷新工作台。

**证据**：
- vitest `410/410` 通过（含 4 个新增测试）
- typecheck 无错误
- ruff 全绿

---

### Task 2（P0）⚠️ — push 并部署 Sprint-5 到生产

**状态**：**待执行**，需要 SSH key 路径。

**当前本地状态**：

```
本地 main:  c656ebb6（领先 origin/main 4 commits）
origin/main: d31a1b1d（Sprint-5 Batch-B，领先生产 3 commits）
生产:        484c348f（Sprint-4）
```

**执行命令（需替换 key 路径）**：

```bash
# Step 1: push 所有本地 commit
git push origin main

# Step 2: 运行生产部署
uv run python scripts/deploy-tencent-cloud-production.py \
  --ssh-key /path/to/key.pem \
  --execute

# Step 3: L3 只读验收（替换 expected_sha 为部署后实际 SHA）
uv run python scripts/audit-tencent-cloud-deployment-state.py \
  --ssh-key /path/to/key.pem \
  --expected-deploy-sha <post_deploy_sha> \
  --json-output tmp/outputs/deploy-state-sprint5-20260809.json

# Step 4: 生产前端验收
node scripts/run-production-frontend-acceptance.mjs
```

**验收标准**：
- `deploy_sha` = `c656ebb6`（或以 push 后最终 SHA 为准）
- 23/23 路由 200
- `/workspace` 和 `/remediation` 验收文本通过
- app/PostgreSQL/ClamAV 全部 healthy

---

### Task 3（P0）✅ — 整改附件映射真实 UUID

**同 Task 1 commit `6d1d291d`**

**具体变更**：

```diff
// evidence_requests 区域
- itemId={item.linkedCaseId ?? item.id}
+ itemId={item.id}

// 移除 linkedCaseId 展示
- <small>{item.linkedCaseId} · 截止 {item.dueDate}</small>
+ <small>截止 {item.dueDate}</small>
```

后端 `routes_workbench.py` 已确认 `id` 字段为 `str(it.id)`（真实 UUID），`POST /api/v1/remediation/items/{item_id}/attachments` 接受 UUID 路径参数。

---

### Task 4（P1）✅ — workspace 待复核 API 端点验证

**结论**：后端已完整支持，无需新增代码。

**验证路径**：
- `fetchAuditFindings("pending-review")` → `GET /api/v1/audit-findings?review_status=pending-review`
- `routes_query.py:1329` 接受 `review_status: str | None` Query 参数
- 返回 `{ items: AuditFinding[], stats: {...} }`
- `AuditFinding` 包含 `finding_key`、`severity`——与 `workspace/page.tsx` 消费格式完全一致

---

### Task 5（P2）✅ — CSS 完整性验证

**结论**：`StatusActionButtons` 所用全部 CSS 类均已在 `globals.css` 中存在（Sprint-5 Batch-A 已写入）。

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

**预检结论**：

| 项目 | 状态 | 阻塞上线 |
|---|---|---|
| SSO 认证 | `blocked`（9 个 env UNSET） | **是**（外部依赖院方） |
| pg_restore 演练 | 未执行，有步骤文档 | 建议完成 |
| 告警 webhook | URL 为空，已有配置说明 | 否 |
| 压测 | 无 baseline，已有骨架脚本 | 建议完成 |
| UAT 脚本 | 未编写，有需求清单 | **是**（院方签字需要） |

---

## 三、当前 git 状态

```
本地 main: c656ebb6（领先 origin/main 4 commits）
测试:      vitest 410/410，ruff 全绿，typecheck 无错误
工作树:    clean（nothing to commit）
```

**本次新增 commits（相对 origin/main）**：

```
c656ebb6  docs: add sprint-6 on-site hardening precheck report
6d1d291d  feat(remediation): implement StatusActionButtons with status-machine flow and fix attachment itemId
6b5110ad  docs: update state register + add sprint-5 baseline + codex handoff
226d3d0d  fix(replica): localize collection labels and update acceptance text contracts
```

---

## 四、下一步给 Codex 的执行优先级

### 立即可执行（无外部依赖）

**[1] push + 生产部署（Task 2）**

```bash
git push origin main
uv run python scripts/deploy-tencent-cloud-production.py \
  --ssh-key /path/to/key.pem --execute
```

**[2] pg_restore 恢复演练**（详见 `drafts/analysis/sprint6-precheck-20260809.md` 第 2 节）

**[3] 压测 baseline 脚本**：在 `scripts/k6-query-baseline.js` 创建 k6 脚本，执行 `p95 < 3s` baseline 测试

**[4] 告警 webhook 配置**：填入 `MEDICAL_AUDIT_AUDIT_LOG_ALERT_WEBHOOK_URL`，重启 app 容器验证

### 依赖外部输入（等待院方）

**[5] SSO 方案确认**：选 A（Nginx 可信代理）或选 B（SAML/OAuth2），院方提供配置参数

**[6] UAT 脚本编写**：待产品/业务同学主导，基于 `sprint6-precheck-20260809.md` 第 5 节需求清单

---

## 五、关键文件索引（最新）

| 文件 | 变更内容 |
|---|---|
| `web/src/components/replica/replica-remediation-workbench.tsx` | StatusActionButtons 组件 + 刷新回调 + evidence_requests UUID 修复 |
| `web/src/components/replica/replica-remediation-workbench.test.tsx` | 新增 4 个测试（操作按钮显示/调用/关闭态/附件UUID） |
| `web/src/lib/api-types.ts` | `RemediationCaseApiItem` 新增 `status_key: string` |
| `drafts/analysis/sprint6-precheck-20260809.md` | Sprint-6 四项加固预检报告 |
| `docs/workflows/workflow-project-state-and-debt-register-stable.md` | Sprint-5 基线节点（2026-08-09） |
| `docs/product/product-development-plan-medical-audit-stable.md` | 1.3 节 Sprint-5 完成状态 |

---

## 六、不可逾越边界（与前次相同）

1. `git push --force` 禁止
2. 生产部署须显式 `--execute`
3. provider call 须单独授权
4. `auth_mode=header_transition_layer`：不得将当前权限体系声称为 SSO 完成
5. 生产 5 条疑点为脱敏样本：不可作为真实 HIS 规则引擎结论

---

*交付时间：2026-08-09 | 交付方：Sisyphus | 接收方：Codex*

---
title: "Sprint-5 交接文档：本地完成状态与下一步执行方案"
doc_type: handoff
module: project-governance
status: active
created: 2026-08-09
updated: 2026-08-09
owner: self
source: human+ai
target_agent: codex
---

# Sprint-5 交接文档

## 一、当前状态速览

### 代码版本

| 层级 | SHA | 说明 |
|---|---|---|
| 本地 main | `226d3d0d` | 最新，领先 origin/main 1 commit |
| origin/main | `d31a1b1d` | Sprint-5 Batch-B（未 push 本地最新） |
| 生产 deploy_sha | `484c348f` | Sprint-4，Sprint-5 **尚未部署** |

**结论：本地有 1 个 commit 未 push；生产停留在 Sprint-4；sprint-5 全部前端变更均未在生产上线。**

### 测试套件状态

```
vitest  : 406/406 通过
ruff    : 全绿
mypy    : 全绿（src/）
```

---

## 二、Sprint-5 已完成事项（精确）

### Batch-A：整改工作台后端数据补齐（已完成）

文件：`src/medical_audit_kb/api/routes_workbench.py`

- `remediation_workbench()` 返回的 `db_items` 列表中每条记录补齐了以下前端字段：
  - `department`（科室）
  - `nextAction`（下一步操作提示，来自 `_remediation_next_action()`）
  - `evidenceStatus`（证据状态）
  - `reportNo`（报告编号）
  - `dueDate`（截止日期）
  - `status`（中文标签，来自 `_remediation_status_label()`）
  - `status_key`（英文 key，供门禁计算和 metrics）
- 新增辅助函数：`_remediation_status_label()` / `_remediation_next_action()`
- 新增映射字典：`_REMEDIATION_STATUS_LABELS` / `_REMEDIATION_NEXT_ACTIONS`

文件：`web/src/lib/api-client.ts`

- 新增 `updateRemediationItemStatus(itemId, status, note)` → `POST /api/v1/remediation/items/{id}/status`
- 新增 `fetchRemediationItems()` → `GET /api/v1/remediation/items`

文件：`web/src/components/replica/replica-remediation-workbench.tsx`

- ⚠️ **已 import `updateRemediationItemStatus`，但 `StatusActionButtons` 组件体尚未落地**
- 当前只有悬空 import，前端操作按钮 UI 是下一步待完成项（见第三节 Task 1）

### Batch-B：报告签发持久化与 UI（已完成）

文件：`src/medical_audit_kb/api/routes_pages.py`

- `_review_task_report_entry()` 新增暴露 5 个签发字段：`signed`/`signed_by`/`signed_at`/`signoff_note`/`report_id`
- 新增 `POST /api/v1/reports/drafts/{task_id}/signoff` 接口（JSON，非 HTML form）
  - 复用 `_build_review_task_signed_report` + `_update_review_task`
  - 已签发返回 409；task 不存在返回 404
  - 权限：`CREATE_REVIEW_TASK`（member 及以上）
  - `ReportSignoffRequest.signoff_note` max_length=2000

文件：`web/src/components/replica/replica-report-workbench.tsx`

- 新增 `SignoffButton` 组件：
  - 草稿状态：显示「签发报告」按钮 → 点击展开说明输入框
  - 已签发：显示绿色「✓ signed_by · signed_at」标签
  - 门禁阻断状态：不显示签发按钮
  - 签发成功后自动刷新工作台

文件：`web/src/lib/api-client.ts` / `api-types.ts`

- 新增 `signReportDraft(taskId, note)` 函数
- `ReportWorkbenchEntry` 加可选 signoff 字段

### Batch-C：workspace 今日待复核预览（已完成）

文件：`web/src/app/(workspace)/workspace/page.tsx`

- 加载 pending-review 疑点列表（最多 5 条）
- 每条显示：风险等级 badge + 疑点名称 + 「进入复核」快捷链接
- 无待复核时显示绿色「审计进度良好 ✓」

### 知识库来源标签本地化（已完成）

文件：`web/src/components/replica/replica-rules-workbench.tsx`

- 新增 `SOURCE_COLLECTION_LABELS` 映射（26 个 collection key → 中文标签）
- 新增 `sourceCollectionLabel()` 辅助函数
- `RuleCard` 来源字段改用中文标签
- `SourceCard` 头部修复重复展示 raw key 的 bug（原来 `<span>{item.sourceCollection}</span>` + `<h3>{item.name}</h3>` 重复）

### 验收文本合同更新（已完成）

文件：`scripts/run-production-frontend-acceptance.mjs`

- `/workspace` 路由：`/AI，让审计更智能/` → `[/工作台/, /待复核疑点|常用功能/]`
- `/remediation` 路由：`/医保审计/, /智能审计 - 规则导航/` → `[/整改工作台/, /整改事项|整改数据加载中/]`

---

## 三、Codex 下一步执行计划

按优先级排序，每个 Task 是独立原子单元。

---

### Task 1（P0）：补全整改状态操作按钮 UI

**背景**：Sprint-5 Batch-A 只完成了后端字段补齐和前端 import，`StatusActionButtons` 组件体未落地。`updateRemediationItemStatus` 在 `replica-remediation-workbench.tsx` 中是悬空 import。

**需要做**：

在 `web/src/components/replica/replica-remediation-workbench.tsx` 中实现 `StatusActionButtons` 组件：

```
status_key → 可用操作 映射：
  "pending"            → ["开始整改"]
  "in-progress"        → ["提交验收"]
  "pending-acceptance" → ["验收通过", "退回"]
  "rejected"           → ["重新整改"]
  "accepted"           → ["关闭"]
  "closed"             → （无操作，只读）
```

交互模式：
- 点击操作按钮 → 展开 textarea（note 输入，可选）
- 确认按钮 → 调用 `updateRemediationItemStatus(item.id, nextStatus, note)`
- 成功 → 刷新工作台（复用现有 `fetchData()` 模式）
- 失败 → 展示错误提示

**后端路由已存在**：`POST /api/v1/remediation/items/{item_id}/status`（`routes_remediation.py:183`）

**验收**：
- 整改工作台 `db_items` 列表中每条带 `status_key` 的 item 显示对应操作按钮
- 点击操作后状态更新，页面自动刷新
- `closed` 状态下无操作按钮
- 新增对应测试用例到 `replica-remediation-workbench.test.tsx`
- vitest 全绿，ruff/mypy 全绿

---

### Task 2（P0）：push 本地 commit 并部署 Sprint-5

**背景**：本地 main `226d3d0d` 领先 origin/main 1 commit；origin/main 领先生产 3 commits。

**需要做**：

1. push 本地 commit：
   ```bash
   git push origin main
   ```

2. 运行生产部署（标准流程）：
   ```bash
   uv run python scripts/deploy-tencent-cloud-production.py \
     --ssh-key /path/to/key.pem \
     --execute
   ```

3. 部署后运行 L3 只读验收：
   ```bash
   uv run python scripts/audit-tencent-cloud-deployment-state.py \
     --ssh-key /path/to/key.pem \
     --expected-deploy-sha <new_sha> \
     --json-output tmp/outputs/deploy-state-sprint5-20260809.json
   ```

4. 运行生产前端验收（更新后的文本合同）：
   ```bash
   node scripts/run-production-frontend-acceptance.mjs
   ```

**验收**：
- `deploy_sha` 更新为 Sprint-5 最新 commit SHA
- 23/23 路由返回 200
- `/workspace` 和 `/remediation` 验收文本合同通过

---

### Task 3（P1）：整改附件上传映射真实 case ID

**背景**：前端 `UploadButton` 在 `SourceCard` 区域使用 `itemId={item.linkedCaseId ?? item.id}`，其中 `linkedCaseId` 来自 workbench 响应，后端当前填的是静态 case id（字符串），不是 `remediation_items.uuid`。

**问题位置**：
- `web/src/components/replica/replica-remediation-workbench.tsx` line ~224
- `src/medical_audit_kb/api/routes_workbench.py` `remediation_workbench()` 中 db_items 的 `linkedCaseId` 字段

**需要做**：

在 `routes_workbench.py` 的 `db_items` 构造中，确认每个 `db_item` 的 `id` 字段是 `str(it.id)`（UUID），并移除或正确填充 `linkedCaseId`：

```python
# 期望行为：
{
  "id": str(it.id),        # 这是真实 UUID，供附件上传和状态更新使用
  "linkedCaseId": None,    # 或移除此字段，让前端直接用 item.id
  ...
}
```

前端对应改为直接使用 `item.id`：
```tsx
// replica-remediation-workbench.tsx
itemId={item.id}  // 不再 fallback linkedCaseId
```

**验收**：
- 附件上传请求中 `itemId` 是真实 UUID，而非静态字符串
- `POST /api/v1/remediation/items/{item_id}/attachments` 在生产中返回 201
- `attachment_count` 字段在成功上传后递增

---

### Task 4（P1）：workspace 待复核列表 API 后端支持

**背景**：`workspace/page.tsx` 的 `fetchPendingReview()` 需要一个返回 pending-review 疑点的 API 端点。需确认当前实现的 API 路径和格式是否已落地。

**需要检查**：

```bash
grep -n "pending.review\|pending_review\|status.*pending" \
  src/medical_audit_kb/api/routes_pages.py \
  src/medical_audit_kb/api/routes_query.py | head -20
```

如果端点不存在，需要新增：
- `GET /api/v1/audit-findings?status=needs_review&limit=5`（或类似路径）
- 返回格式与 workspace 前端消费格式对齐

**验收**：
- workspace 页面加载后，待复核疑点区域显示真实数据（或「审计进度良好 ✓」）
- 不返回 500/404

---

### Task 5（P2）：整改状态 CSS 完整性

**背景**：Sprint-5 Batch-A 在 `globals.css` 中新增了 `remediation-item-actions`/`status-actions`/`note-input` 等样式，但 Task 1 的 `StatusActionButtons` 组件落地后需确认 CSS 类名一致。

**需要做**：

Task 1 实现 `StatusActionButtons` 时，确认以下 CSS 类已在 `globals.css` 中存在：
- `.remediation-item-actions`
- `.status-actions`
- `.note-input`
- `.status-action-btn`（或类似命名）

如有缺失，在 `globals.css` 中补充。

**验收**：整改状态操作区域视觉正常，无 unstyled 裸按钮。

---

### Task 6（P2）：Sprint-6 上线加固预检

**背景**：以下项目是 Sprint-6 的前提条件，需要提前排查状态。

**排查清单**：

| 项目 | 排查命令 | 期望状态 |
|---|---|---|
| SSO 协议确认 | 与院方沟通 | 选 A（nginx 代理）或选 B（SAML/OAuth2） |
| 告警 webhook | `grep WEBHOOK configs/deploy/*/medical-audit.env.example` | 有占位符说明 |
| 备份恢复演练 | `pg_restore` dry-run 文档 | 有步骤文档 |
| 压测 baseline | 检查是否有 k6/locust 脚本 | 无则新建 |

---

## 四、已知约束与不可逾越边界

1. **不得 push force**：`git push --force` 在任何情况下禁止。
2. **生产部署需显式 `--execute`**：deploy 脚本默认 dry-run，必须加 `--execute` 才执行。
3. **provider call 需独立授权**：知识查询 live UAT、真实 provider smoke 每次须单独明确授权。
4. **auth_mode 仍是 header_transition_layer**：X-Role header 可自行构造，不得把生产写入型权限 E2E 当作已有 SSO 完成的证据。
5. **生产数据库仅有 5 条脱敏样本**：不得将样本数据当作真实 HIS 规则引擎的输出结论。

---

## 五、关键文件索引

| 文件 | 用途 |
|---|---|
| `docs/workflows/workflow-project-state-and-debt-register-stable.md` | 项目状态与技术债台账（含 2026-08-09 Sprint-5 基线） |
| `docs/product/product-development-plan-medical-audit-stable.md` | 开发计划（含 1.3 节 Sprint-5 基线） |
| `src/medical_audit_kb/api/routes_workbench.py` | 整改工作台 API（Batch-A 已补字段） |
| `src/medical_audit_kb/api/routes_remediation.py` | 整改状态更新、附件上传路由 |
| `src/medical_audit_kb/api/routes_pages.py` | 报告签发接口（`/reports/drafts/{id}/signoff`） |
| `web/src/components/replica/replica-remediation-workbench.tsx` | 整改工作台前端（Task 1 待补全） |
| `web/src/components/replica/replica-report-workbench.tsx` | 报告工作台前端（SignoffButton 已完成） |
| `web/src/components/replica/replica-rules-workbench.tsx` | 知识库规则工作台（来源标签已本地化） |
| `web/src/app/(workspace)/workspace/page.tsx` | 工作台首页（待复核预览已完成） |
| `web/src/lib/api-client.ts` | 前端 API 客户端（updateRemediationItemStatus 已注册） |
| `scripts/run-production-frontend-acceptance.mjs` | 生产前端验收脚本（文本合同已更新） |
| `scripts/deploy-tencent-cloud-production.py` | 生产部署脚本 |
| `scripts/audit-tencent-cloud-deployment-state.py` | 生产状态 L3 只读审计 |

---

## 六、本次交接 commit 范围

```
origin/main..local HEAD:
  226d3d0d  fix(replica): localize collection labels and update acceptance text contracts

需补 push 至 origin/main，Sprint-5 完整内容（origin/main 领先生产）：
  226d3d0d  fix(replica): localize collection labels and update acceptance text contracts
  d31a1b1d  feat(sprint-5 batch-B): report signoff persistence + UI
  3245ad37  feat(sprint-5 batch-A+C): remediation actionable + workspace pending list
```

生产目标 SHA（push 后）：`226d3d0d`（部署前需先 push，deploy_sha 由部署脚本写入）

---

*交接时间：2026-08-09 | 交接方：Sisyphus | 接收方：Codex*

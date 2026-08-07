---
title: Sprint 5 执行计划（2026-08-08）
doc_type: analysis
module: project-governance
status: active
created: 2026-08-07
updated: 2026-08-07
owner: self
source: human+ai
---

# Sprint 5 执行计划

> 基准 SHA：`484c348f`（生产 + 本地已同步）
> 目标：整改闭环可操作、报告签发持久化、workspace 待复核预览

---

## 任务清单

### Batch A — 整改工作台真实数据绑定（上午，约 3.5h）

#### A1 整改工作台加载真实 item 列表
- **后端**：`routes_workbench.py` 的 `remediation_workbench` 响应中，将 `remediation_cases` 从静态种子改为读取真实 `remediation_items`，并在每条 case 中暴露真实 UUID（字段 `item_id`）
- **前端**：`replica-remediation-workbench.tsx` 优先使用 `item.item_id` 作为 `uploadRemediationAttachment` 的 itemId 参数
- **测试**：更新 `replica-remediation-workbench.test.tsx` 合同

#### A2 整改状态更新 UI
- **前端**：每个整改事项加「状态操作」区，根据当前 status 展示可操作的下一步：
  - `pending-rectification` → 「开始整改」
  - `in-rectification` → 「提交验收」
  - `pending-acceptance` → 「验收通过」/「退回」
  - `accepted` → 「关闭」
- **前端**：新增 `updateRemediationStatus(itemId, status, note)` 到 `api-client.ts`
- **测试**：4 个状态流转测试

---

### Batch B — 报告签发持久化（下午，约 4h）

#### B1 Schema migration：report_signoffs 表
```sql
CREATE TABLE report_signoffs (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  report_key TEXT NOT NULL UNIQUE,
  signed_by TEXT NOT NULL,
  signed_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  signoff_note TEXT DEFAULT '',
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
```
- **文件**：`sql/report-signoffs-schema-v1.sql`
- **后端**：`src/medical_audit_kb/db/models.py` 新增 `ReportSignoff` model

#### B2 签发路由
- `POST /api/v1/reports/drafts/{report_key}/signoff` → 写入 `report_signoffs`
- `GET /api/v1/reports/drafts/{report_key}/signoff` → 查询签发状态
- **文件**：`src/medical_audit_kb/api/routes_workbench.py` 或新建 `routes_reports.py`

#### B3 报告工作台签发 UI
- 已有草稿的报告卡片底部加「签发报告」按钮
- 点击弹出签发对话框（签发人 + 签发说明输入框）
- 签发后卡片显示：✓ 已签发 · {signer} · {date}
- **文件**：`web/src/components/replica/replica-report-workbench.tsx`

---

### Batch C — workspace 待复核预览（可并行，约 1.5h）

#### C1 workspace 加「今日待复核」section
- 加载 `fetchAuditFindings({ reviewStatus: 'pending-review' })` 结果
- 展示前 5 条，每条显示：疑点名 + 风险等级 + 「进入复核」按钮（链接到 `/medical-audit`）
- 无待复核时显示「暂无待复核疑点，审计进度良好 ✓」
- **文件**：`web/src/app/(workspace)/workspace/page.tsx`

---

### Batch D — 快速修复（可随时插入，各约 30min）

#### D1 规则库中文标签补全
- `ReplicaRulesWorkbench` 中 source_collection 英文 key → 中文标签映射
- 25 个 collection 全部覆盖

#### D2 生产验收脚本路由更新
- `tests/knowledge_query/test_production_frontend_acceptance_workflow.py`
- 确保 `/workspace`（新内容）纳入路由验收

#### D3 告警 webhook 配置（待用户提供 URL）
```bash
# 用户提供 URL 后执行：
ssh ubuntu@audit.lute-tlz-dddd.top \
  "sed -i 's|MEDICAL_AUDIT_AUDIT_LOG_ALERT_WEBHOOK_URL=|MEDICAL_AUDIT_AUDIT_LOG_ALERT_WEBHOOK_URL=https://...|' \
  /opt/medical-audit/app/configs/deploy/tencent-cloud/medical-audit.env"
# 重启容器
```

---

## 验收标准

每个 Batch 完成后：
1. `pnpm web:typecheck` 通过
2. `pnpm web:test` 406/406（或更多）通过
3. `uv run ruff check` + `uv run mypy src` 通过
4. 生产部署：`python scripts/deploy-tencent-cloud-production.py --execute`
5. 生产 smoke：`curl https://audit.lute-tlz-dddd.top/api/v1/health` + 关键 API 验证

---

## 明日部署计划

| 时段 | Batch | 部署时机 |
|---|---|---|
| 上午完成 | A1 + A2 | 上午结束后部署一次 |
| 下午完成 | B1 + B2 + B3 + C1 | 下午结束后部署一次 |
| 随时 | D1 + D2 | 与相邻 Batch 合并部署 |
| 待触发 | D3 | 用户提供 URL 后立即配置 |

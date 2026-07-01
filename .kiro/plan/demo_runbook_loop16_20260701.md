---
title: "medical_audit Loop 16 demo runbook"
project: "medical_audit"
created_at: "2026-07-01T00:45:00+08:00"
status: "demo-ready"
evidence_grade: "production-read-only-plus-authorized-deploy-history"
---

# Loop 16 Demo Runbook

## Demo Claim

The current production site is ready for a focused demo of the医保基金使用合规专题.

Evidence:

- Production deployed SHA: `b7c1f4b622a8cb837972dc5b63ed09baa1121530`.
- Deployment state audit: `status=pass`, app/postgres/clamav healthy, issues `0`, warnings `0`.
- Frontend acceptance: `23` routes, `46` checks, `P0=0`, `P1=0`.
- Demo browser rehearsal: `12` desktop/mobile screenshots, no P0/P1 findings, no horizontal overflow.

## Route Order

| Step | Route | Purpose | Primary Screenshot |
| --- | --- | --- | --- |
| 1 | `/workspace` | Start from the current project cockpit and show the product is scoped to one医保基金 audit scenario. | `/Users/pray/project/medical_audit/output/playwright/loop15-demo-rehearsal-20260701T003433/desktop-workspace.png` |
| 2 | `/fund-compliance` | Show the independent专题入口: overview, rule groups, metrics, and entry into the workbench. | `/Users/pray/project/medical_audit/output/playwright/loop15-demo-rehearsal-20260701T003433/desktop-fund-compliance-topic.png` |
| 3 | `/fund-compliance/review` | Show the疑点审查 workbench and待处理清单. | `/Users/pray/project/medical_audit/output/playwright/loop15-demo-rehearsal-20260701T003433/desktop-fund-compliance-review-list.png` |
| 4 | `/fund-compliance/review` -> `费用表单` -> `新建表单` | Show the three Excel-derived template idea plus future custom form creation. | `/Users/pray/project/medical_audit/output/playwright/loop15-demo-rehearsal-20260701T003433/desktop-fund-compliance-review-form-open.png` |
| 5 | `/chat` | Show AI审证对话 as a citation-first assistant entry, not an uncontrolled provider demo. | `/Users/pray/project/medical_audit/output/playwright/loop15-demo-rehearsal-20260701T003433/desktop-chat.png` |
| 6 | `/agent-market` | Show智能体广场 as prompt-agent templates with short user-facing names. | `/Users/pray/project/medical_audit/output/playwright/loop15-demo-rehearsal-20260701T003433/desktop-agent-market.png` |

## Presenter Script

### 1. Open with the product boundary

Say:

> 这不是通用后台，而是面向医院医保基金使用合规的内审专题工作台。今天演示围绕一个专题闭环：规则、疑点、表单、审证对话和智能体模板。

Action:

- Open `https://audit.lute-tlz-dddd.top/workspace`.
- Point to `医保基金使用合规专项自查`, project status, and audit chain.

Avoid:

- Do not describe this as a finished all-domain audit platform.
- Do not imply every module has the same depth as the医保基金专题.

### 2. Enter the医保基金专题入口

Say:

> 专题入口把管理者需要看的东西先聚合：本月疑点、涉及金额、DIP/DRG异常、整改率，以及当前可用审计口径。

Action:

- Navigate to `/fund-compliance`.
- Click or point to `进入专题工作台`.
- Mention that this is intentionally a different page from the general workspace.

### 3. Show疑点审查

Say:

> 工作台第一层是待处理疑点清单。演示数据保留了患者脱敏、科室、问题、金额和风险等级，便于审计人员先分拣再复核。

Action:

- Navigate to `/fund-compliance/review`.
- Stay on `单据审查`.
- Point to `待处理清单`, risk tags, and amount column.

### 4. Show费用表单 capability

Say:

> 第二层是表单。这里不是一个单一上传框，而是围绕三类医保费用模板组织：汇总表、分类汇总表、就诊明细表，并预留自建表单。

Action:

- Click `费用表单`.
- Click `新建表单`.
- Point to `表单名称`, `字段列表`, and the three template tabs.

Boundary:

- This proves the UI model and template structure are in place.
- It does not claim live Excel ingestion or production write-path completion.

### 5. Show AI审证对话

Say:

> AI对话不是自由聊天，它先限定智能体和知识来源，再把回答约束到引用依据和证据边界。

Action:

- Navigate to `/chat`.
- Point to `当前智能体`, `知识来源`, and quick questions.
- Prefer showing the UI and evidence boundary rather than submitting a fresh provider-dependent question during the main demo.

Fallback:

- If asked for live answer generation, state that provider calls and final answer quality belong to a separate provider gate; this demo focuses on product workflow and citation-first UI.

### 6. Show智能体广场

Say:

> 智能体广场沉淀的是可复用审计提示词模板。名称已经压缩到更适合业务用户识别的短名称，卡片可以进入对应助手。

Action:

- Navigate to `/agent-market`.
- Show category filters and a few agent cards.

Note:

- Desktop card density is acceptable for an audit template library, but later polish should reduce first-viewport chip density.

## Mobile Demo Guidance

Use mobile screenshots as backup evidence, not as the primary live path.

Recommended screenshots:

- `/Users/pray/project/medical_audit/output/playwright/loop15-demo-rehearsal-20260701T003433/mobile-fund-compliance-topic.png`
- `/Users/pray/project/medical_audit/output/playwright/loop15-demo-rehearsal-20260701T003433/mobile-fund-compliance-review-form-open.png`
- `/Users/pray/project/medical_audit/output/playwright/loop15-demo-rehearsal-20260701T003433/mobile-chat.png`

Mobile caveat:

- The mobile top navigation is usable and does not overflow, but it remains visually crowded. Treat this as P2 polish, not as a demo blocker.

## Evidence Boundaries

Supported claims:

- Production deployment is currently aligned to `b7c1f4b622a8cb837972dc5b63ed09baa1121530`.
- Core frontend routes are reachable and passed production acceptance.
- The医保基金专题 has separate topic and review pages.
- The费用表单 UI supports three template views and a custom-form entry.
- The demo screenshots are production read-only browser evidence.

Do not claim:

- Live provider answer quality has been fully accepted in this demo loop.
- Excel ingestion and production write-path governance are complete.
- P2 mobile navigation polish is complete.
- All audit domains have the same workflow depth as医保基金使用合规.

## If Something Goes Wrong

If the network is unstable:

- Use the screenshot folder `output/playwright/loop15-demo-rehearsal-20260701T003433/`.
- Continue the story from screenshots in the same route order.

If a page reload is slow:

- Refresh once.
- If it still stalls, switch to the corresponding screenshot and keep the narrative moving.

If asked why the UI still has dense navigation:

- Answer: `当前版本已通过演示路径和生产前端验收；移动端顶部导航和智能体广场密度已记录为 P2 polish，会作为下一批视觉优化处理。`

If asked about production proof:

- Cite:
  - `/Users/pray/project/medical_audit_minimal_pr/tmp/outputs/tencent-cloud-deployment-state-loop15-demo-rehearsal-20260701T003433.json`
  - `/Users/pray/project/medical_audit_minimal_pr/tmp/outputs/production-frontend-acceptance-loop15-demo-rehearsal-20260701T003433.json`
  - `/Users/pray/project/medical_audit/output/playwright/loop15-demo-rehearsal-20260701T003433/report.json`

## Next Batch Options

Recommended next action after demo prep:

1. Keep production frozen for the demo unless a P0/P1 issue appears.
2. After the demo, run a narrow P2 polish batch:
   - collapse mobile top navigation labels;
   - reduce first-viewport chip density in `/agent-market`;
   - keep acceptance route checks and screenshot metrics as the verification gate.

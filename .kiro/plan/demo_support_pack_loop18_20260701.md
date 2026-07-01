---
title: "medical_audit Loop 18 demo support pack"
project: "medical_audit"
created_at: "2026-07-01T01:52:44+08:00"
status: "demo-support-ready"
evidence_grade: "production-read-only-plus-screenshot-fallback"
---

# Loop 18 Demo Support Pack

## Purpose

Use this pack during the live presentation to keep the demo stable and bounded.

Core decision:

- Primary path: open the production site and follow the verified route order.
- Backup path: if live network, projector resolution, or page load is unstable, switch to the matching screenshots.
- Freeze rule: do not deploy, merge, change environment, call providers, write object storage, apply schema changes, or run write-path smoke before the demo unless a P0/P1 issue appears.

## One-Minute Opening

Say:

> 今天演示的是医院医保基金使用合规专项内审工作台。当前版本已经完成生产部署和只读验收，演示重点是一个专题闭环：工作台、专题页、疑点审查、费用表单、AI审证对话和智能体模板。

Do not say:

- 不说这是全审计域完整上线。
- 不说 Excel 生产写入链路已经验收。
- 不说 provider answer quality 已完成终验。
- 不说移动端导航密度已经完成视觉 polish。

## Live Route Checklist

| Step | Route | Action | Point To |
| --- | --- | --- | --- |
| 1 | `https://audit.lute-tlz-dddd.top/workspace` | 打开生产工作台 | 当前专题、项目状态、审计链路 |
| 2 | `/fund-compliance` | 进入医保基金专题 | 专题概览、指标、规则组、进入工作台 |
| 3 | `/fund-compliance/review` | 展示单据审查 | 待处理清单、风险标签、金额、状态 |
| 4 | `/fund-compliance/review` | 点 `费用表单` -> `新建表单` | 三类模板、自建表单、字段列表 |
| 5 | `/chat` | 展示 AI 审证对话 | 当前智能体、知识来源、证据边界 |
| 6 | `/agent-market` | 展示智能体广场 | 短名称卡片、分类筛选、进入助手 |

## Screenshot Fallback

Use these when the live site or projector view is unstable.

| Step | Screenshot |
| --- | --- |
| 工作台 | `/Users/pray/project/medical_audit/output/playwright/loop17-spot-check-20260701T013243/desktop-workspace.png` |
| 医保基金专题 | `/Users/pray/project/medical_audit/output/playwright/loop17-spot-check-20260701T013243/desktop-fund-compliance-topic.png` |
| 单据审查 | `/Users/pray/project/medical_audit/output/playwright/loop17-spot-check-20260701T013243/desktop-review-list.png` |
| 费用表单 | `/Users/pray/project/medical_audit/output/playwright/loop17-spot-check-20260701T013243/desktop-review-form.png` |
| AI 对话 | `/Users/pray/project/medical_audit/output/playwright/loop17-spot-check-20260701T013243/desktop-chat.png` |
| 智能体广场 | `/Users/pray/project/medical_audit/output/playwright/loop17-spot-check-20260701T013243/desktop-agent-market.png` |
| 移动端费用表单 | `/Users/pray/project/medical_audit/output/playwright/loop17-spot-check-20260701T013243/mobile-mobile-review-form.png` |

Older full-route rehearsal screenshots remain available under:

- `/Users/pray/project/medical_audit/output/playwright/loop15-demo-rehearsal-20260701T003433/`

## Evidence Chain

| Layer | Artifact | Result |
| --- | --- | --- |
| Deployment state | `/Users/pray/project/medical_audit_minimal_pr/tmp/outputs/tencent-cloud-deployment-state-loop17-spot-check-20260701T013243.json` | `status=pass`, issues `0`, warnings `0` |
| Frontend acceptance | `/Users/pray/project/medical_audit_minimal_pr/tmp/outputs/production-frontend-acceptance-loop17-spot-check-20260701T013243.json` | `23` routes, `46` checks, `P0=0`, `P1=0` |
| Browser spot check | `/Users/pray/project/medical_audit/output/playwright/loop17-spot-check-20260701T013243/report.json` | `7` checks, `hard_issue_count=0`, overflow `0` |
| Demo runbook | `/Users/pray/project/medical_audit/.kiro/plan/demo_runbook_loop16_20260701.md` | route order and presenter script ready |

## If Asked About Dense UI

Say:

> 当前生产版本已通过演示路径和前端验收。移动端顶部导航和智能体广场首屏标签密度已经归为 P2 polish；演示后会做一次窄范围视觉减法，不在演示前继续改生产以避免引入新风险。

Post-demo P2 polish should stay narrow:

- collapse or simplify mobile top navigation labels;
- reduce first-viewport chip density in `/agent-market`;
- keep route acceptance and screenshot metrics as the verification gate;
- do not combine this polish batch with provider calls, data ingestion, or schema work.

## If Asked For Live AI Generation

Say:

> 本次演示重点是产品工作流和引用优先的交互边界。现场可以展示入口、知识来源和证据边界；如果要验证 provider answer quality，需要进入单独的 provider gate。

Avoid submitting provider-dependent prompts during the main route unless the demo owner explicitly chooses that risk.

## Close

Say:

> 这版已经能支撑医保基金使用合规专题的演示：从专题入口到疑点审查、费用表单、AI审证和智能体模板是连贯的。下一批不是扩大范围，而是做视觉减法和写入链路治理。

---
title: 前端边界冻结：Jinja 深页 vs Next 门户（E2）
doc_type: architecture
module: frontend
topic: jinja-next-boundary
status: stable
created: 2026-06-23
updated: 2026-06-23
owner: self
source: human+ai
---

# 前端边界冻结：Jinja 深页 vs Next 门户（E2）

## 1. 背景

项目存在两套前端渲染体系并存（技术债 T-01）：

- FastAPI Jinja 深页（`routes_pages.py`，约 120KB），承载写入型审计业务闭环，已过生产写入型验收。
- Next.js 门户（`web/`，18 路由 + 登录），承载导航、仪表盘和读/轻交互页。

无明确边界会导致同一能力双入口、双测试、双文案，维护成本翻倍。本文件冻结边界，作为后续所有 UI 工作的方向基线。

## 2. 现状清单（实测，基于 origin/main）

### 2.1 Jinja 深页与端点（routes_pages.py）

| 路由 | 类型 | 职责 | 是否有 Next 对应 |
| --- | --- | --- | --- |
| `/` | 页面 | 根落地 | 否（Next 用 `/workspace`） |
| `/pages/query` | 页面 | 知识查询深页 | Next `/knowledge-query`（孤儿） |
| `/pages/chat` | 页面 | AI 审证对话深页（引用生成、底稿导出） | Next `/chat`（入口壳） |
| `/pages/chat/export` | 导出 | 对话底稿导出 | — |
| `/pages/review-tasks` | 页面 | 复核任务台（核心写入业务） | 无 |
| `/pages/review-tasks/create` | 写 POST | 创建复核任务 | 无 |
| `/pages/review-tasks/{id}/status` | 写 POST | 状态流转 | 无 |
| `/pages/review-tasks/{id}/attachments` | 写 POST | 附件登记/归档 | 无 |
| `/pages/review-tasks/{id}/report-signoff` | 写 POST | 正式报告签发冻结 | 无 |
| `/pages/review-tasks/{id}/rectification` | 写 POST | 整改事项 | 无 |
| `/review-tasks/{id}/export|report-draft|signed-report|rectification/export` | 导出 | 各类下载 | 无 |
| `/pages/audit-findings` | 页面 | 疑点清单 | Next `/findings`（孤儿） |
| `/pages/audit-findings/{key}/review-task` | 写 POST | 从疑点建复核任务 | 无 |
| `/audit-findings/{key}/export` | 导出 | 疑点导出 | 无 |
| `/pages/audit-logs` | 页面 | 审计日志台 | 无 |
| `/pages/index-admin` | 页面 | 索引发布/回滚/重载运维台 | 无 |
| `/pages/preview/{chunk_id}` | 页面 | 原文预览 | 被两侧引用 |
| `/reports/workbench`、`/reports/workpaper-templates` | API | 报告聚合数据 | 被 Next `/reports` 消费 |

### 2.2 Next 门户路由

导航内：`workspace, chat, agents, agent-market, knowledge-base, documents, analytics, graph, reports, projects, guided-check, rules, remediation, archive`（+ 系统管理 `index-admin`、`audit-logs` 指向 Jinja）。
导航外（孤儿）：`findings`、`knowledge-query`。

## 3. 边界决策（冻结）

### 3.1 长期由 Jinja 承载（写入型业务闭环，已过生产验收，短期不迁移）

- 复核任务台全生命周期：`/pages/review-tasks` 及其 create/status/attachments/report-signoff/rectification 写端点与全部导出。
- 疑点清单与从疑点建任务：`/pages/audit-findings`、`/pages/audit-findings/{key}/review-task`、疑点导出。
- 审计日志台：`/pages/audit-logs`。
- 索引运维台：`/pages/index-admin`（受控运维，刻意保留服务端）。
- 原文预览：`/pages/preview/{chunk_id}`（双侧共用，稳定）。
- 引用生成与底稿导出：`/pages/chat`、`/pages/chat/export`、`/pages/query`（真实引用/导出在深页执行）。

理由：这些是产品的合规核心闭环，已有生产写入型 E2E 与审计日志门禁；用 Jinja form-POST + 服务端渲染最稳，迁移收益低、回归风险高。

### 3.2 Next 为唯一门户壳（导航/仪表盘/读与轻交互）

- 全部 workspace 导航页继续在 Next 实现与演进。
- Next `/chat`、`/reports` 作为"入口壳/聚合视图"，通过 `/api/v1/*` 或跳转深页对接 Jinja 能力，不在 Next 重复实现写入逻辑。

### 3.3 孤儿路由处置（承接 E1）

- `/knowledge-query`、`/findings`：不在导航、与 `/pages/query`、`/pages/audit-findings` 重复 → 标记下线候选；下线前先在导航与文档中不再引用，保留一个发布周期后移除或改为重定向。

### 3.4 演进规则（强制）

1. 新的写入型业务流一律在 **Next + `/api/v1/*`** 实现，不再新增 Jinja 页面。
2. Jinja 深页进入"维护冻结"：可修 bug、可加审计字段，不扩功能面。
3. Jinja→Next 迁移按"先读后写"顺序，优先迁移只读展示页（`audit-logs`、`audit-findings` 展示）后再考虑写入型（`review-tasks`），且每次迁移必须保留生产写入型 E2E 等价覆盖。
4. 任一迁移完成后立即删除被取代的 Jinja 路由，避免双入口长期并存。

## 4. 完成判据

- 路由地图无未决归属；每个路由标注"Jinja 维护 / Next 主线 / 下线候选"。
- 后续 PR 不新增 Jinja 页面（评审项）。
- 孤儿路由有明确下线计划。

## 5. 状态

E2 边界冻结完成（文档级）。后续 Phase E 代码切片（E3 已铺数据来源徽标、E4 起逐页接 API）均在本边界内推进：只读展示页优先在 Next 接真实 API，写入型闭环暂留 Jinja。

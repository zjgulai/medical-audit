---
title: 前端重构第二阶段实施计划：自查项目模型与今日工作台
doc_type: workflow
module: frontend
topic: self-check-os-projects-dashboard
status: stable
created: 2026-06-07
updated: 2026-06-11
owner: self
source: human+ai
---

# Self-Check OS Projects Dashboard Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development` (recommended) or `superpowers:executing-plans` to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build Plan 02: a project-driven Today Workspace that makes `self_check_project` the visible root object for the new医保审计自查 OS.

**Architecture:** Keep the Next.js App Router frontend introduced in Plan 01. Add a typed project domain model, dashboard components, browser-only backend health status, and route-level tests without deleting or replacing existing FastAPI/Jinja fallback pages. This is a frontend product slice with deterministic demo project data and live read-only backend status; it does not implement project persistence yet.

**Tech Stack:** Next.js 15 App Router, React 19, TypeScript strict mode, Tailwind CSS v4, Vitest, Testing Library, Playwright, existing FastAPI health/search-backend proxy client.

---

## Scope Check

Plan 02 implements only:

- Current self-check project model.
- Today workspace dashboard.
- Project context bar sourced from the project model.
- Read-only backend/index health panel through the existing browser proxy client.
- Unit/E2E tests and gate evidence.

Plan 02 does **not** implement:

- Project create/update/archive API.
- Server-side persistence for projects.
- Multi-round chat, materials upload, finding generation, remediation, reports, analytics, graph, or archive real data.
- Any migration or deletion of legacy Jinja pages.

## File Structure

Create:

- `web/src/lib/projects.ts`: typed `self_check_project` demo model and selectors.
- `web/src/lib/projects.test.ts`: model invariants and dashboard selector tests.
- `web/src/components/dashboard/project-metric-card.tsx`: compact metric card.
- `web/src/components/dashboard/project-status-card.tsx`: current project overview card.
- `web/src/components/dashboard/project-queue-card.tsx`: pending work queue card.
- `web/src/components/dashboard/project-activity-list.tsx`: recent activity card.
- `web/src/components/dashboard/workflow-progress-card.tsx`: current workflow progress card.
- `web/src/components/dashboard/backend-status-card.tsx`: client component for `/health` and `/index/search-backend`.
- `web/src/components/dashboard/project-dashboard.tsx`: composed dashboard section.
- `web/src/components/dashboard/project-dashboard.test.tsx`: dashboard rendering and health states.
- `tmp/outputs/frontend-plan-02-projects-dashboard-gate-20260607.txt`: final gate evidence.

Modify:

- `web/src/components/shell/project-context-bar.tsx`: source project name/topic/status from `projects.ts`.
- `web/src/components/shell/workspace-shell.test.tsx`: update context bar assertions.
- `web/src/app/(workspace)/workspace/page.tsx`: replace Plan 01 foundation overview with project dashboard.
- `web/src/app/(workspace)/workspace-pages.test.tsx`: keep route coverage and assert project dashboard content.
- `web/tests/e2e/foundation.spec.ts`: update workspace smoke to Plan 02 dashboard content while retaining `/guided-check` smoke.
- `drafts/docs/product-frontend-refactor-plan-02-projects-dashboard-draft-20260607.md`: update status to `review` after gate passes.

Do not modify:

- `src/medical_audit_kb/api/templates/*.html`
- `src/medical_audit_kb/api/static/app.css`
- `src/medical_audit_kb/api/routes_pages.py`

---

### Task 1: Add Self-Check Project Domain Model

**Files:**

- Create: `web/src/lib/projects.ts`
- Create: `web/src/lib/projects.test.ts`

- [ ] **Step 1: Write failing project model tests**

Create `web/src/lib/projects.test.ts`:

```ts
import { describe, expect, it } from "vitest";

import {
  currentSelfCheckProject,
  getOpenProjectQueueItems,
  getProjectMetricByKey,
  getProjectStageProgress
} from "./projects";

describe("self-check project model", () => {
  it("anchors the workspace to a fund usage self-check project", () => {
    expect(currentSelfCheckProject.id).toBe("SELF-CHECK-FUND-20260607");
    expect(currentSelfCheckProject.name).toBe("医保基金使用合规专项自查");
    expect(currentSelfCheckProject.auditTopic).toBe("医保基金使用合规");
    expect(currentSelfCheckProject.status).toBe("active");
    expect(currentSelfCheckProject.stage).toBe("analyze");
  });

  it("calculates workflow progress from the current project stage", () => {
    expect(getProjectStageProgress(currentSelfCheckProject)).toEqual({
      currentIndex: 3,
      total: 7,
      percent: 43
    });
  });

  it("keeps actionable queue items separate from closed items", () => {
    const openItems = getOpenProjectQueueItems(currentSelfCheckProject);

    expect(openItems).toHaveLength(3);
    expect(openItems.map((item) => item.status)).not.toContain("closed");
  });

  it("returns metrics by stable key", () => {
    expect(getProjectMetricByKey(currentSelfCheckProject, "open_findings")?.value).toBe("12");
    expect(getProjectMetricByKey(currentSelfCheckProject, "missing_evidence")?.tone).toBe("warning");
  });
});
```

- [ ] **Step 2: Run failing project model test**

Run:

```bash
pnpm --filter medical-audit-web test -- src/lib/projects.test.ts
```

Expected:

```text
FAIL  src/lib/projects.test.ts
Error: Failed to resolve import "./projects"
```

- [ ] **Step 3: Create project model**

Create `web/src/lib/projects.ts`:

```ts
export type ProjectStatus = "active" | "paused" | "closed";
export type ProjectStage = "intake" | "retrieve" | "analyze" | "clarify" | "finding" | "remediation" | "report";
export type ProjectTone = "neutral" | "info" | "warning" | "danger" | "success";
export type QueueItemStatus = "open" | "blocked" | "closed";

export type ProjectMetric = {
  readonly key: "open_findings" | "missing_evidence" | "rule_cards" | "backend_status";
  readonly label: string;
  readonly value: string;
  readonly helper: string;
  readonly tone: ProjectTone;
};

export type ProjectQueueItem = {
  readonly id: string;
  readonly title: string;
  readonly owner: string;
  readonly dueLabel: string;
  readonly status: QueueItemStatus;
  readonly risk: "high" | "medium" | "low";
};

export type ProjectActivity = {
  readonly id: string;
  readonly title: string;
  readonly description: string;
  readonly timeLabel: string;
};

export type SelfCheckProject = {
  readonly id: string;
  readonly name: string;
  readonly organizationName: string;
  readonly auditTopic: string;
  readonly status: ProjectStatus;
  readonly stage: ProjectStage;
  readonly dateRange: string;
  readonly evidencePolicy: string;
  readonly metrics: readonly ProjectMetric[];
  readonly queue: readonly ProjectQueueItem[];
  readonly activities: readonly ProjectActivity[];
};

export const projectStageLabels: Record<ProjectStage, string> = {
  intake: "收集条件",
  retrieve: "检索证据",
  analyze: "形成判断",
  clarify: "缺证追问",
  finding: "生成疑点",
  remediation: "补证整改",
  report: "汇总输出"
};

const projectStageOrder: readonly ProjectStage[] = [
  "intake",
  "retrieve",
  "analyze",
  "clarify",
  "finding",
  "remediation",
  "report"
];

export const currentSelfCheckProject: SelfCheckProject = {
  id: "SELF-CHECK-FUND-20260607",
  name: "医保基金使用合规专项自查",
  organizationName: "单院医保内审试运行",
  auditTopic: "医保基金使用合规",
  status: "active",
  stage: "analyze",
  dateRange: "2026-01 至 2026-03",
  evidencePolicy: "仅展示资料内明确国家/地区政策，不做外推结论。",
  metrics: [
    {
      key: "open_findings",
      label: "待处理疑点",
      value: "12",
      helper: "均需人工确认后进入底稿",
      tone: "danger"
    },
    {
      key: "missing_evidence",
      label: "待补证据",
      value: "5",
      helper: "缺结算明细或目录限制字段",
      tone: "warning"
    },
    {
      key: "rule_cards",
      label: "专题规则卡",
      value: "18",
      helper: "Markdown / JSON 双形态",
      tone: "info"
    },
    {
      key: "backend_status",
      label: "索引联通",
      value: "待检测",
      helper: "由前端只读健康检查刷新",
      tone: "neutral"
    }
  ],
  queue: [
    {
      id: "QUEUE-001",
      title: "核对非目录项目发生基金支付的结算明细",
      owner: "审计员",
      dueLabel: "今日",
      status: "open",
      risk: "high"
    },
    {
      id: "QUEUE-002",
      title: "补充身份骗保相关就诊和参保身份字段",
      owner: "信息科",
      dueLabel: "2 天内",
      status: "blocked",
      risk: "medium"
    },
    {
      id: "QUEUE-003",
      title: "复核限定科室规则卡跨专题归类",
      owner: "业务专家",
      dueLabel: "本周",
      status: "open",
      risk: "medium"
    },
    {
      id: "QUEUE-004",
      title: "归档已确认规则卡评审记录",
      owner: "系统",
      dueLabel: "已完成",
      status: "closed",
      risk: "low"
    }
  ],
  activities: [
    {
      id: "ACT-001",
      title: "规则卡映射已激活",
      description: "医保基金使用合规专题已进入独立逻辑专题入口。",
      timeLabel: "今天 09:20"
    },
    {
      id: "ACT-002",
      title: "候选疑点等待人工确认",
      description: "高风险疑点仍保持 AI 草稿，不进入正式底稿。",
      timeLabel: "今天 08:45"
    },
    {
      id: "ACT-003",
      title: "索引健康等待前端联通检测",
      description: "Plan 02 只做只读健康展示，不执行索引变更。",
      timeLabel: "昨天 18:10"
    }
  ]
};

export function getProjectStageProgress(project: SelfCheckProject) {
  const currentIndex = projectStageOrder.indexOf(project.stage) + 1;
  return {
    currentIndex,
    total: projectStageOrder.length,
    percent: Math.round((currentIndex / projectStageOrder.length) * 100)
  };
}

export function getOpenProjectQueueItems(project: SelfCheckProject): readonly ProjectQueueItem[] {
  return project.queue.filter((item) => item.status !== "closed");
}

export function getProjectMetricByKey(project: SelfCheckProject, key: ProjectMetric["key"]): ProjectMetric | undefined {
  return project.metrics.find((metric) => metric.key === key);
}
```

- [ ] **Step 4: Run project model test**

Run:

```bash
pnpm --filter medical-audit-web test -- src/lib/projects.test.ts
```

Expected:

```text
PASS  src/lib/projects.test.ts
```

- [ ] **Step 5: Commit project model**

Run:

```bash
git add web/src/lib/projects.ts web/src/lib/projects.test.ts
git commit -m "定义自查项目前端模型"
```

---

### Task 2: Add Project Dashboard Components

**Files:**

- Create: `web/src/components/dashboard/project-metric-card.tsx`
- Create: `web/src/components/dashboard/project-status-card.tsx`
- Create: `web/src/components/dashboard/project-queue-card.tsx`
- Create: `web/src/components/dashboard/project-activity-list.tsx`
- Create: `web/src/components/dashboard/workflow-progress-card.tsx`
- Create: `web/src/components/dashboard/project-dashboard.tsx`
- Create: `web/src/components/dashboard/project-dashboard.test.tsx`

- [ ] **Step 1: Write failing dashboard rendering test**

Create `web/src/components/dashboard/project-dashboard.test.tsx`:

```tsx
import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { currentSelfCheckProject } from "@/lib/projects";

import { ProjectDashboard } from "./project-dashboard";

describe("ProjectDashboard", () => {
  it("renders current project, metrics, queue, workflow progress and recent activity", () => {
    render(<ProjectDashboard project={currentSelfCheckProject} />);

    expect(screen.getByRole("heading", { name: "医保基金使用合规专项自查" })).toBeInTheDocument();
    expect(screen.getByText("单院医保内审试运行")).toBeInTheDocument();
    expect(screen.getByText("2026-01 至 2026-03")).toBeInTheDocument();
    expect(screen.getByText("待处理疑点")).toBeInTheDocument();
    expect(screen.getByText("12")).toBeInTheDocument();
    expect(screen.getByText("核对非目录项目发生基金支付的结算明细")).toBeInTheDocument();
    expect(screen.getByText("形成判断")).toBeInTheDocument();
    expect(screen.getByText("规则卡映射已激活")).toBeInTheDocument();
  });
});
```

- [ ] **Step 2: Run failing dashboard test**

Run:

```bash
pnpm --filter medical-audit-web test -- src/components/dashboard/project-dashboard.test.tsx
```

Expected:

```text
FAIL  src/components/dashboard/project-dashboard.test.tsx
Error: Failed to resolve import "./project-dashboard"
```

- [ ] **Step 3: Create dashboard components**

Create the six component files using these public interfaces:

```tsx
// web/src/components/dashboard/project-dashboard.tsx
import { ProjectActivityList } from "./project-activity-list";
import { ProjectMetricCard } from "./project-metric-card";
import { ProjectQueueCard } from "./project-queue-card";
import { ProjectStatusCard } from "./project-status-card";
import { WorkflowProgressCard } from "./workflow-progress-card";
import type { SelfCheckProject } from "@/lib/projects";

type ProjectDashboardProps = {
  readonly project: SelfCheckProject;
};

export function ProjectDashboard({ project }: ProjectDashboardProps) {
  return (
    <main className="space-y-6">
      <ProjectStatusCard project={project} />
      <section className="grid gap-4 md:grid-cols-2 xl:grid-cols-4" aria-label="项目关键指标">
        {project.metrics.map((metric) => (
          <ProjectMetricCard key={metric.key} metric={metric} />
        ))}
      </section>
      <section className="grid gap-6 xl:grid-cols-[1.05fr_0.95fr]">
        <WorkflowProgressCard project={project} />
        <ProjectQueueCard project={project} />
      </section>
      <ProjectActivityList activities={project.activities} />
    </main>
  );
}
```

Each card must use existing CSS variables and `StatusPill`; use sober blue/slate/amber/red accents only. Do not add decorative illustrations or consumer-style gradients.

- [ ] **Step 4: Run dashboard test**

Run:

```bash
pnpm --filter medical-audit-web test -- src/components/dashboard/project-dashboard.test.tsx
```

Expected:

```text
PASS  src/components/dashboard/project-dashboard.test.tsx
```

- [ ] **Step 5: Commit dashboard components**

Run:

```bash
git add web/src/components/dashboard
git commit -m "搭建自查项目工作台组件"
```

---

### Task 3: Wire Project Context and Workspace Page

**Files:**

- Modify: `web/src/components/shell/project-context-bar.tsx`
- Modify: `web/src/components/shell/workspace-shell.test.tsx`
- Modify: `web/src/app/(workspace)/workspace/page.tsx`
- Modify: `web/src/app/(workspace)/workspace-pages.test.tsx`

- [ ] **Step 1: Update shell test expectation**

In `web/src/components/shell/workspace-shell.test.tsx`, replace the context assertions:

```tsx
expect(screen.getByText("默认自查项目")).toBeInTheDocument();
expect(screen.getByText("索引状态待接入")).toBeInTheDocument();
```

with:

```tsx
expect(screen.getByText("医保基金使用合规专项自查")).toBeInTheDocument();
expect(screen.getByText("单院医保内审试运行")).toBeInTheDocument();
expect(screen.getByText("医保基金使用合规")).toBeInTheDocument();
```

- [ ] **Step 2: Run failing shell test**

Run:

```bash
pnpm --filter medical-audit-web test -- src/components/shell/workspace-shell.test.tsx
```

Expected:

```text
FAIL
Unable to find an element with the text: 医保基金使用合规专项自查
```

- [ ] **Step 3: Update project context bar**

Modify `web/src/components/shell/project-context-bar.tsx` to import `currentSelfCheckProject` and render:

```tsx
import { StatusPill } from "@/components/ui/status-pill";
import { currentSelfCheckProject } from "@/lib/projects";

export function ProjectContextBar() {
  const project = currentSelfCheckProject;

  return (
    <header className="sticky top-0 z-20 border-b border-slate-200/80 bg-white/82 px-4 py-4 backdrop-blur-xl sm:px-6 md:px-8">
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div>
          <p className="text-xs font-medium uppercase tracking-[0.18em] text-slate-500">当前自查项目</p>
          <div className="mt-1 text-xl font-semibold tracking-tight text-slate-950">{project.name}</div>
          <p className="mt-1 text-xs text-slate-500">{project.organizationName}</p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <StatusPill tone="info">{project.auditTopic}</StatusPill>
          <StatusPill tone="success">项目进行中</StatusPill>
          <StatusPill tone="warning">AI 结论需人工确认</StatusPill>
        </div>
      </div>
    </header>
  );
}
```

- [ ] **Step 4: Update workspace page**

Replace `web/src/app/(workspace)/workspace/page.tsx` with:

```tsx
import { ProjectDashboard } from "@/components/dashboard/project-dashboard";
import { currentSelfCheckProject } from "@/lib/projects";

export default function WorkspacePage() {
  return <ProjectDashboard project={currentSelfCheckProject} />;
}
```

- [ ] **Step 5: Update route page test**

In `web/src/app/(workspace)/workspace-pages.test.tsx`, keep existing route coverage and add:

```tsx
it("renders the current self-check project dashboard", () => {
  render(<WorkspacePage />);

  expect(screen.getByRole("heading", { name: "医保基金使用合规专项自查" })).toBeInTheDocument();
  expect(screen.getByText("待处理疑点")).toBeInTheDocument();
  expect(screen.getByText("待补证据")).toBeInTheDocument();
});
```

- [ ] **Step 6: Run workspace tests**

Run:

```bash
pnpm --filter medical-audit-web test -- src/components/shell/workspace-shell.test.tsx src/app/'(workspace)'/workspace-pages.test.tsx
```

Expected:

```text
PASS
```

- [ ] **Step 7: Commit workspace wiring**

Run:

```bash
git add web/src/components/shell/project-context-bar.tsx web/src/components/shell/workspace-shell.test.tsx web/src/app/'(workspace)'/workspace/page.tsx web/src/app/'(workspace)'/workspace-pages.test.tsx
git commit -m "接入自查项目工作台页面"
```

---

### Task 4: Add Browser Backend Status Card

**Files:**

- Create: `web/src/components/dashboard/backend-status-card.tsx`
- Create: `web/src/components/dashboard/backend-status-card.test.tsx`
- Modify: `web/src/components/dashboard/project-dashboard.tsx`

- [ ] **Step 1: Write failing backend status test**

Create `web/src/components/dashboard/backend-status-card.test.tsx`:

```tsx
import { render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { BackendStatusCard } from "./backend-status-card";

describe("BackendStatusCard", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
    vi.restoreAllMocks();
  });

  it("shows backend and search backend readiness", async () => {
    vi.stubGlobal(
      "fetch",
      vi
        .fn()
        .mockResolvedValueOnce({
          ok: true,
          json: async () => ({ status: "ok", version: "0.1.0", data_root: "/data" })
        })
        .mockResolvedValueOnce({
          ok: true,
          json: async () => ({
            backend: "postgres",
            ready: true,
            details: { matching_embedding_count: 48985 }
          })
        })
    );

    render(<BackendStatusCard />);

    await waitFor(() => {
      expect(screen.getByText("FastAPI 正常")).toBeInTheDocument();
    });
    expect(screen.getByText("postgres 已就绪")).toBeInTheDocument();
    expect(screen.getByText("48985 vectors")).toBeInTheDocument();
  });

  it("shows a conservative failure state", async () => {
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new Error("network failed")));

    render(<BackendStatusCard />);

    await waitFor(() => {
      expect(screen.getByText("后端状态无法确认")).toBeInTheDocument();
    });
  });
});
```

- [ ] **Step 2: Run failing backend status test**

Run:

```bash
pnpm --filter medical-audit-web test -- src/components/dashboard/backend-status-card.test.tsx
```

Expected:

```text
FAIL  src/components/dashboard/backend-status-card.test.tsx
Error: Failed to resolve import "./backend-status-card"
```

- [ ] **Step 3: Create backend status card**

Create `web/src/components/dashboard/backend-status-card.tsx`:

```tsx
"use client";

import { useEffect, useState } from "react";

import { StatusPill } from "@/components/ui/status-pill";
import { fetchBackendHealth, fetchSearchBackendStatus } from "@/lib/api-client";

type StatusState =
  | { readonly status: "loading" }
  | {
      readonly status: "ready";
      readonly backendVersion: string;
      readonly searchBackend: string;
      readonly searchReady: boolean;
      readonly matchingEmbeddingCount?: number;
    }
  | { readonly status: "error" };

export function BackendStatusCard() {
  const [state, setState] = useState<StatusState>({ status: "loading" });

  useEffect(() => {
    let active = true;

    async function loadStatus() {
      try {
        const [health, search] = await Promise.all([fetchBackendHealth(), fetchSearchBackendStatus()]);
        if (!active) {
          return;
        }
        setState({
          status: "ready",
          backendVersion: health.version,
          searchBackend: search.backend,
          searchReady: search.ready,
          matchingEmbeddingCount: search.details?.matching_embedding_count
        });
      } catch {
        if (active) {
          setState({ status: "error" });
        }
      }
    }

    void loadStatus();
    return () => {
      active = false;
    };
  }, []);

  return (
    <section className="rounded-[28px] border border-slate-200 bg-white p-6 shadow-[var(--audit-shadow-card)]" aria-label="系统健康">
      <div className="flex items-start justify-between gap-4">
        <div>
          <p className="text-sm font-medium text-blue-700">系统健康</p>
          <h2 className="mt-2 text-xl font-semibold tracking-tight text-slate-950">后端与索引联通</h2>
        </div>
        {state.status === "ready" && <StatusPill tone={state.searchReady ? "success" : "warning"}>{state.searchReady ? "可检索" : "待初始化"}</StatusPill>}
        {state.status === "loading" && <StatusPill tone="neutral">检测中</StatusPill>}
        {state.status === "error" && <StatusPill tone="warning">只读失败</StatusPill>}
      </div>

      {state.status === "loading" && <p className="mt-5 text-sm text-slate-600">正在通过 Next.js 代理检查 FastAPI 和搜索后端。</p>}
      {state.status === "error" && <p className="mt-5 text-sm text-slate-600">后端状态无法确认。当前页面不会生成疑点或正式底稿。</p>}
      {state.status === "ready" && (
        <div className="mt-5 grid gap-3 sm:grid-cols-3">
          <div className="rounded-2xl bg-slate-50 p-4">
            <p className="text-xs text-slate-500">API</p>
            <p className="mt-1 text-sm font-semibold text-slate-950">FastAPI 正常</p>
            <p className="mt-1 text-xs text-slate-500">v{state.backendVersion}</p>
          </div>
          <div className="rounded-2xl bg-slate-50 p-4">
            <p className="text-xs text-slate-500">Search</p>
            <p className="mt-1 text-sm font-semibold text-slate-950">{state.searchBackend} {state.searchReady ? "已就绪" : "未就绪"}</p>
          </div>
          <div className="rounded-2xl bg-slate-50 p-4">
            <p className="text-xs text-slate-500">Embeddings</p>
            <p className="mt-1 text-sm font-semibold text-slate-950">{state.matchingEmbeddingCount ?? 0} vectors</p>
          </div>
        </div>
      )}
    </section>
  );
}
```

- [ ] **Step 4: Add status card to dashboard**

In `web/src/components/dashboard/project-dashboard.tsx`, import `BackendStatusCard` and render it after `ProjectStatusCard`:

```tsx
import { BackendStatusCard } from "./backend-status-card";
```

```tsx
<ProjectStatusCard project={project} />
<BackendStatusCard />
```

- [ ] **Step 5: Run backend status tests**

Run:

```bash
pnpm --filter medical-audit-web test -- src/components/dashboard/backend-status-card.test.tsx src/components/dashboard/project-dashboard.test.tsx
```

Expected:

```text
PASS
```

- [ ] **Step 6: Commit backend status card**

Run:

```bash
git add web/src/components/dashboard/backend-status-card.tsx web/src/components/dashboard/backend-status-card.test.tsx web/src/components/dashboard/project-dashboard.tsx
git commit -m "接入工作台后端健康状态"
```

---

### Task 5: Update E2E Smoke for Project Dashboard

**Files:**

- Modify: `web/tests/e2e/foundation.spec.ts`

- [ ] **Step 1: Update workspace E2E assertions**

In `web/tests/e2e/foundation.spec.ts`, update the first test to assert Plan 02 dashboard content:

```ts
await expect(page.getByRole("heading", { name: "医保基金使用合规专项自查" })).toBeVisible();
await expect(page.getByText("待处理疑点")).toBeVisible();
await expect(page.getByText("待补证据")).toBeVisible();
await expect(page.getByRole("heading", { name: "后端与索引联通" })).toBeVisible();
await expect(page.getByRole("heading", { name: "AI 自查状态机" })).toBeVisible();
```

Keep the guided-check route test unchanged.

- [ ] **Step 2: Run E2E**

Run:

```bash
pnpm web:e2e
```

Expected:

```text
2 passed
```

- [ ] **Step 3: Commit E2E update**

Run:

```bash
git add web/tests/e2e/foundation.spec.ts
git commit -m "更新项目工作台端到端冒烟"
```

---

### Task 6: Run Full Plan 02 Gate and Record Evidence

**Files:**

- Create: `tmp/outputs/frontend-plan-02-projects-dashboard-gate-20260607.txt`
- Modify: `drafts/docs/product-frontend-refactor-plan-02-projects-dashboard-draft-20260607.md`

- [ ] **Step 1: Run full frontend gate**

Run:

```bash
{
  echo "## pnpm web:typecheck"
  pnpm web:typecheck
  echo
  echo "## pnpm web:test"
  pnpm web:test
  echo
  echo "## pnpm web:build"
  pnpm web:build
  echo
  echo "## pnpm web:e2e"
  pnpm web:e2e
} | sed 's/[[:space:]]*$//' | tee tmp/outputs/frontend-plan-02-projects-dashboard-gate-20260607.txt
```

All four sections must exit successfully.

- [ ] **Step 2: Verify legacy FastAPI pages were not changed**

Run:

```bash
test -f src/medical_audit_kb/api/templates/chat.html
test -f src/medical_audit_kb/api/templates/query.html
test -f src/medical_audit_kb/api/templates/index_admin.html
git diff --name-only -- src/medical_audit_kb/api/templates src/medical_audit_kb/api/static/app.css src/medical_audit_kb/api/routes_pages.py
```

Expected output:

```text
```

- [ ] **Step 3: Update this plan status**

Change frontmatter:

```yaml
status: draft
```

to:

```yaml
status: review
```

Do not mark `stable` until the user accepts Plan 02.

- [ ] **Step 4: Commit final gate evidence**

Run:

```bash
git add drafts/docs/product-frontend-refactor-plan-02-projects-dashboard-draft-20260607.md
git add -f tmp/outputs/frontend-plan-02-projects-dashboard-gate-20260607.txt
git commit -m "记录项目工作台验收证据"
```

---

## Self-Review

Spec coverage:

- Covers design spec section 4.1 今日工作台 and section 5 core object requirement.
- Keeps every visible action under a current self-check project.
- Adds live read-only health status without claiming project persistence.
- Preserves legacy Jinja fallback.

Current product integration correction:

- As of 2026-06-11, the primary workspace navigation must not expose Plan 03-11 placeholder modules as first-level actions.
- `今日工作台` remains the Next.js-owned `/workspace` dashboard.
- `查询工作台` is now a Next.js-owned API-first route at `/knowledge-query`, backed by `POST /api/v1/query`; `/pages/query` remains the FastAPI/Jinja compatibility page.
- `疑点清单` is now a Next.js-owned API-first route at `/findings`, backed by `GET /api/v1/audit-findings`; `/pages/audit-findings` remains the FastAPI/Jinja compatibility page and owns the existing review-task creation POST flow.
- Other live product actions remain integrated through existing FastAPI/Jinja backend pages: `/pages/chat`, `/pages/review-tasks`, `/pages/audit-logs`, and `/pages/index-admin`.
- The legacy Next.js routes `/guided-check`, `/rules`, `/documents`, `/remediation`, `/reports`, `/analytics`, `/graph`, and `/archive` remain only as compatibility bridge pages. They must point users to the nearest live backend, Next-native, or workspace function and must not show `Plan 03` through `Plan 11` placeholder content.

Known deferred work:

- Project CRUD and persistence move to a later backend API plan.
- Next-native AI guided chat, rule library, remediation, reports, analytics, graph, and archive modules remain deferred until they are backed by real API/domain capabilities.

Execution:

- Execute via `superpowers:subagent-driven-development`.
- After every task, run spec review first, then code quality review.

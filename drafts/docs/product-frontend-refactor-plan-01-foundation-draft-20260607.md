---
title: 前端重构第一阶段实施计划：Next.js 基座与设计系统
doc_type: workflow
module: frontend
topic: self-check-os-foundation
status: draft
created: 2026-06-07
updated: 2026-06-07
owner: self
source: human+ai
---

# Self-Check OS Frontend Foundation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development` (recommended) or `superpowers:executing-plans` to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the first working slice of the medical audit self-check OS frontend: a Next.js 15 application, strict TypeScript toolchain, sober audit-grade design system, workflow shell, backend proxy, and smoke tests.

**Architecture:** Add a new `web/` frontend workspace without deleting or replacing the existing FastAPI/Jinja pages. The Next.js app owns the new self-check OS UI; FastAPI remains the backend API and legacy fallback. The first slice must be independently runnable, testable, and safe to deploy beside the old site.

**Tech Stack:** pnpm workspace, Next.js 15 App Router, React 19, TypeScript strict mode, Tailwind CSS v4, Vitest, Testing Library, Playwright, FastAPI backend proxy through Next.js rewrites.

---

## Scope Check

The approved spec covers multiple independent subsystems: projects, conversations, materials, findings, remediation, reports, analytics, graph, and archives. This plan intentionally covers only **Plan 01: foundation**.

Do not implement business persistence, multi-round chat storage, finding generation, remediation workflow, report export, analytics, or graph rendering in this plan. Those require separate plans after the foundation is accepted.

## Downstream Plan Sequence

1. `plan-01-foundation`: Next.js base, design system, route shell, API proxy, tests.
2. `plan-02-projects-dashboard`: self-check project model and today dashboard.
3. `plan-03-guided-chat`: guided multi-round chat and evidence side panel.
4. `plan-04-rule-library`: topic rule cards and rule-card-aware retrieval views.
5. `plan-05-document-search`: source materials, uploaded materials, preview, and citation locating.
6. `plan-06-findings`: structured finding list, evidence quality, and human confirmation state.
7. `plan-07-remediation`: evidence supplement and rectification tasks.
8. `plan-08-reports`: working papers, rectification records, and report export.
9. `plan-09-analytics`: risk distribution and remediation progress analytics.
10. `plan-10-knowledge-graph`: project-level entity and evidence relationship graph.
11. `plan-11-archive-audit-log`: project archive and operation log closure.

## File Structure

Create:

- `package.json`: root pnpm workspace commands for frontend tasks.
- `pnpm-workspace.yaml`: workspace membership.
- `web/package.json`: Next.js app dependencies and scripts.
- `web/next.config.ts`: Next.js config and backend rewrite proxy.
- `web/tsconfig.json`: strict frontend TypeScript configuration.
- `web/postcss.config.mjs`: Tailwind CSS v4 PostCSS plugin.
- `web/vitest.config.ts`: unit test configuration.
- `web/playwright.config.ts`: browser E2E configuration.
- `web/src/test/setup.ts`: Testing Library matcher setup.
- `web/src/app/globals.css`: design tokens and global CSS.
- `web/src/app/layout.tsx`: root App Router layout.
- `web/src/app/page.tsx`: redirect-style landing page for the new workspace.
- `web/src/app/(workspace)/layout.tsx`: self-check OS shell layout.
- `web/src/app/(workspace)/workspace/page.tsx`: today workspace page.
- `web/src/app/(workspace)/guided-check/page.tsx`: AI guided self-check foundation preview page.
- `web/src/app/(workspace)/rules/page.tsx`: rule library foundation preview page.
- `web/src/app/(workspace)/documents/page.tsx`: materials and document search foundation preview page.
- `web/src/app/(workspace)/findings/page.tsx`: findings foundation preview page.
- `web/src/app/(workspace)/remediation/page.tsx`: remediation foundation preview page.
- `web/src/app/(workspace)/reports/page.tsx`: reports foundation preview page.
- `web/src/app/(workspace)/analytics/page.tsx`: analytics foundation preview page.
- `web/src/app/(workspace)/graph/page.tsx`: knowledge graph foundation preview page.
- `web/src/app/(workspace)/archive/page.tsx`: project archive foundation preview page.
- `web/src/components/shell/app-sidebar.tsx`: left workflow navigation.
- `web/src/components/shell/project-context-bar.tsx`: top project context bar.
- `web/src/components/shell/workspace-shell.tsx`: shared app shell.
- `web/src/components/ui/status-pill.tsx`: audit status label component.
- `web/src/components/ui/module-card.tsx`: module entry card component.
- `web/src/lib/navigation.ts`: navigation model and module metadata.
- `web/src/lib/api-client.ts`: backend proxy client.
- `web/src/lib/api-types.ts`: minimal backend response types.
- `web/src/lib/workflow.ts`: workflow states and copy.
- `web/src/components/shell/workspace-shell.test.tsx`: shell unit test.
- `web/src/lib/api-client.test.ts`: API client unit test.
- `web/tests/e2e/foundation.spec.ts`: Playwright foundation smoke test.

Modify:

- `.gitignore`: add `.next/`, `web/.next/`, `web/test-results/`, `web/playwright-report/`, and `.superpowers/` only if the existing `.gitignore` diff can be safely isolated. If unrelated user changes are present, stage this change separately or defer it.

Do not modify:

- `src/medical_audit_kb/api/templates/*.html`
- `src/medical_audit_kb/api/static/app.css`
- `src/medical_audit_kb/api/routes_pages.py`

Existing Jinja pages must remain the production fallback during Plan 01.

---

### Task 1: Create pnpm Workspace Skeleton

**Files:**

- Create: `package.json`
- Create: `pnpm-workspace.yaml`
- Create: `web/package.json`

- [ ] **Step 1: Verify no frontend workspace currently exists**

Run:

```bash
find . -maxdepth 2 -type f \( -name 'package.json' -o -name 'pnpm-workspace.yaml' \) | sort
```

Expected current output before implementation:

```text
```

If any frontend config appears, stop and inspect it before creating new files.

- [ ] **Step 2: Create root package manifest**

Create `package.json`:

```json
{
  "name": "medical-audit",
  "private": true,
  "packageManager": "pnpm@9.15.0",
  "scripts": {
    "web:dev": "pnpm --filter medical-audit-web dev",
    "web:build": "pnpm --filter medical-audit-web build",
    "web:start": "pnpm --filter medical-audit-web start",
    "web:lint": "pnpm --filter medical-audit-web lint",
    "web:typecheck": "pnpm --filter medical-audit-web typecheck",
    "web:test": "pnpm --filter medical-audit-web test",
    "web:e2e": "pnpm --filter medical-audit-web e2e"
  }
}
```

- [ ] **Step 3: Create pnpm workspace file**

Create `pnpm-workspace.yaml`:

```yaml
packages:
  - "web"
```

- [ ] **Step 4: Create web package manifest**

Create `web/package.json`:

```json
{
  "name": "medical-audit-web",
  "version": "0.1.0",
  "private": true,
  "type": "module",
  "scripts": {
    "dev": "next dev --port 3030",
    "build": "next build",
    "start": "next start --port 3030",
    "lint": "next lint",
    "typecheck": "tsc --noEmit",
    "test": "vitest run",
    "test:watch": "vitest",
    "e2e": "playwright test"
  },
  "dependencies": {
    "@tailwindcss/postcss": "^4.0.0",
    "next": "^15.1.11",
    "react": "^19.0.0",
    "react-dom": "^19.0.0",
    "tailwindcss": "^4.0.0",
    "zod": "^3.24.0"
  },
  "devDependencies": {
    "@playwright/test": "^1.49.0",
    "@testing-library/jest-dom": "^6.6.0",
    "@testing-library/react": "^16.1.0",
    "@types/node": "^22.10.0",
    "@types/react": "^19.0.0",
    "@types/react-dom": "^19.0.0",
    "@vitejs/plugin-react": "^4.3.0",
    "eslint": "^9.17.0",
    "eslint-config-next": "^15.1.11",
    "jsdom": "^25.0.0",
    "typescript": "^5.7.0",
    "vitest": "^2.1.0"
  }
}
```

- [ ] **Step 5: Install dependencies**

Run:

```bash
pnpm install
```

Expected:

```text
Done in
```

The exact duration may differ. `pnpm-lock.yaml` must be created.

- [ ] **Step 6: Commit workspace skeleton**

Run:

```bash
git add package.json pnpm-workspace.yaml web/package.json pnpm-lock.yaml
git commit -m "初始化前端工作区"
```

Expected:

```text
[codex/opendesign-ui-polish <hash>] 初始化前端工作区
```

---

### Task 2: Add Next.js, TypeScript, Tailwind, and Test Config

**Files:**

- Create: `web/next.config.ts`
- Create: `web/tsconfig.json`
- Create: `web/next-env.d.ts`
- Create: `web/postcss.config.mjs`
- Create: `web/eslint.config.mjs`
- Create: `web/vitest.config.ts`
- Create: `web/playwright.config.ts`
- Create: `web/src/test/setup.ts`
- Create: `web/src/app/globals.css`
- Modify: `web/package.json`

- [ ] **Step 1: Create Next.js config with backend proxy**

Create `web/next.config.ts`:

```ts
import type { NextConfig } from "next";

const DEFAULT_BACKEND_BASE_URL = "http://127.0.0.1:8021";

const resolveBackendBaseUrl = (value: string | undefined): string => {
  const candidate = (value?.trim() || DEFAULT_BACKEND_BASE_URL).replace(/\/+$/, "");
  let parsed: URL;

  try {
    parsed = new URL(candidate);
  } catch (error) {
    throw new Error("MEDICAL_AUDIT_API_BASE_URL must be a valid URL.", { cause: error });
  }

  if (parsed.protocol !== "http:" && parsed.protocol !== "https:") {
    throw new Error("MEDICAL_AUDIT_API_BASE_URL must use http or https.");
  }

  return candidate;
};

const backendBaseUrl = resolveBackendBaseUrl(process.env.MEDICAL_AUDIT_API_BASE_URL);

const nextConfig: NextConfig = {
  reactStrictMode: true,
  typescript: {
    ignoreBuildErrors: false,
    tsconfigPath: "tsconfig.json"
  },
  async rewrites() {
    return [
      {
        source: "/api/backend/:path*",
        destination: `${backendBaseUrl}/:path*`
      }
    ];
  }
};

export default nextConfig;
```

- [ ] **Step 2: Create strict TypeScript config**

Create `web/tsconfig.json`:

```json
{
  "compilerOptions": {
    "target": "ES2022",
    "lib": ["dom", "dom.iterable", "es2022"],
    "allowJs": false,
    "skipLibCheck": true,
    "strict": true,
    "noEmit": true,
    "esModuleInterop": true,
    "module": "esnext",
    "moduleResolution": "bundler",
    "resolveJsonModule": true,
    "isolatedModules": true,
    "jsx": "preserve",
    "incremental": true,
    "types": ["vitest/globals", "@testing-library/jest-dom"],
    "baseUrl": ".",
    "paths": {
      "@/*": ["./src/*"]
    },
    "plugins": [
      {
        "name": "next"
      }
    ]
  },
  "include": ["next-env.d.ts", "src/**/*.ts", "src/**/*.tsx", ".next/types/**/*.ts"],
  "exclude": ["node_modules"]
}
```

- [ ] **Step 3: Create Next.js TypeScript env declaration**

Create `web/next-env.d.ts`:

```ts
/// <reference types="next" />
/// <reference types="next/image-types/global" />
/// <reference path="./.next/types/routes.d.ts" />

// NOTE: This file should not be edited
// see https://nextjs.org/docs/app/api-reference/config/typescript for more information.
```

- [ ] **Step 4: Create PostCSS config for Tailwind CSS v4**

Create `web/postcss.config.mjs`:

```js
const config = {
  plugins: {
    "@tailwindcss/postcss": {}
  }
};

export default config;
```

- [ ] **Step 5: Create ESLint flat config and update lint script**

Create `web/eslint.config.mjs`:

```js
import { FlatCompat } from "@eslint/eslintrc";
import { defineConfig, globalIgnores } from "eslint/config";
import nextVitalsConfig from "eslint-config-next/core-web-vitals.js";
import nextTypescriptConfig from "eslint-config-next/typescript.js";

const compat = new FlatCompat({
  baseDirectory: import.meta.dirname
});

const eslintConfig = defineConfig([
  ...compat.config(nextVitalsConfig),
  ...compat.config(nextTypescriptConfig),
  globalIgnores([
    ".next/**",
    "out/**",
    "build/**",
    "next-env.d.ts",
    "test-results/**",
    "playwright-report/**"
  ])
]);

export default eslintConfig;
```

Update `web/package.json`:

```json
"lint": "eslint ."
```

- [ ] **Step 6: Create Vitest config**

Create `web/vitest.config.ts`:

```ts
import { fileURLToPath } from "node:url";

import react from "@vitejs/plugin-react";
import { defineConfig } from "vitest/config";

export default defineConfig({
  plugins: [react()],
  test: {
    environment: "jsdom",
    globals: true,
    setupFiles: ["./src/test/setup.ts"],
    include: ["src/**/*.test.ts", "src/**/*.test.tsx"]
  },
  resolve: {
    alias: {
      "@": fileURLToPath(new URL("./src", import.meta.url))
    }
  }
});
```

- [ ] **Step 7: Create Playwright config**

Create `web/playwright.config.ts`:

```ts
import { defineConfig, devices } from "@playwright/test";

export default defineConfig({
  testDir: "./tests/e2e",
  timeout: 30_000,
  expect: {
    timeout: 5_000
  },
  use: {
    baseURL: "http://127.0.0.1:3030",
    trace: "retain-on-failure"
  },
  webServer: {
    command: "pnpm dev",
    url: "http://127.0.0.1:3030",
    reuseExistingServer: !process.env.CI,
    timeout: 120_000
  },
  projects: [
    {
      name: "chromium",
      use: { ...devices["Desktop Chrome"] }
    }
  ]
});
```

- [ ] **Step 8: Create Testing Library setup**

Create `web/src/test/setup.ts`:

```ts
import "@testing-library/jest-dom/vitest";
```

- [ ] **Step 9: Create global design tokens**

Create `web/src/app/globals.css`:

```css
@import "tailwindcss";

:root {
  color-scheme: light;
  --audit-bg: #f5f7fb;
  --audit-surface: #ffffff;
  --audit-surface-subtle: #f8fafc;
  --audit-ink: #101828;
  --audit-ink-muted: #667085;
  --audit-line: #d9e2ef;
  --audit-blue: #155eef;
  --audit-blue-deep: #173b7a;
  --audit-cyan: #0e9384;
  --audit-amber: #b54708;
  --audit-red: #b42318;
  --audit-green: #067647;
  --audit-radius-lg: 18px;
  --audit-radius-md: 12px;
  --audit-shadow-card: 0 18px 45px rgb(16 24 40 / 0.08);
  --audit-font-sans: "SF Pro Text", "SF Pro Display", "PingFang SC", "Hiragino Sans GB", "Noto Sans CJK SC", "Microsoft YaHei", sans-serif;
  --audit-font-mono: "SF Mono", "JetBrains Mono", "Fira Code", monospace;
}

* {
  box-sizing: border-box;
}

html {
  min-height: 100%;
  background: var(--audit-bg);
}

body {
  min-height: 100%;
  margin: 0;
  background:
    radial-gradient(circle at top left, rgb(21 94 239 / 0.08), transparent 34rem),
    linear-gradient(180deg, #f8fbff 0%, var(--audit-bg) 42%);
  color: var(--audit-ink);
  font-family: var(--audit-font-sans);
  text-rendering: optimizeLegibility;
  -webkit-font-smoothing: antialiased;
}

a {
  color: inherit;
  text-decoration: none;
}

button,
input,
textarea,
select {
  font: inherit;
}

.audit-focus-ring:focus-visible {
  outline: 3px solid rgb(21 94 239 / 0.28);
  outline-offset: 2px;
}
```

- [ ] **Step 10: Run lint and typecheck to verify config baseline**

Run:

```bash
pnpm web:lint
pnpm web:typecheck
```

Expected:

```text
Done in
```

- [ ] **Step 11: Commit configuration**

Run:

```bash
git add web/package.json web/eslint.config.mjs web/next.config.ts web/tsconfig.json web/next-env.d.ts web/postcss.config.mjs web/vitest.config.ts web/playwright.config.ts web/src/test/setup.ts web/src/app/globals.css
git commit -m "配置前端构建与测试基线"
```

---

### Task 3: Implement Navigation Model and Workflow Copy

**Files:**

- Create: `web/src/lib/navigation.ts`
- Create: `web/src/lib/workflow.ts`
- Test: `web/src/lib/navigation.test.ts`

- [ ] **Step 1: Write failing navigation test**

Create `web/src/lib/navigation.test.ts`:

```ts
import { describe, expect, it } from "vitest";

import { primaryNavigation } from "./navigation";
import { workflowStages } from "./workflow";

describe("primaryNavigation", () => {
  it("keeps the self-check workflow order stable", () => {
    expect(primaryNavigation.map((item) => item.href)).toEqual([
      "/workspace",
      "/guided-check",
      "/rules",
      "/documents",
      "/findings",
      "/remediation",
      "/reports",
      "/analytics",
      "/graph",
      "/archive"
    ]);
  });

  it("marks AI guided self-check as the core module", () => {
    const guidedCheck = primaryNavigation.find((item) => item.href === "/guided-check");

    expect(guidedCheck).toMatchObject({
      label: "AI 引导自查",
      emphasis: "primary"
    });
  });
});

describe("workflowStages", () => {
  it("keeps the self-check stage order stable", () => {
    expect(workflowStages.map((stage) => stage.stage)).toEqual([
      "intake",
      "retrieve",
      "analyze",
      "clarify",
      "finding",
      "remediation",
      "report"
    ]);
  });

  it("keeps every workflow stage readable", () => {
    for (const stage of workflowStages) {
      expect(stage.label.trim()).not.toBe("");
      expect(stage.description.trim()).not.toBe("");
    }
  });
});
```

- [ ] **Step 2: Run failing test**

Run:

```bash
pnpm --filter medical-audit-web test -- src/lib/navigation.test.ts
```

Expected:

```text
FAIL  src/lib/navigation.test.ts
Error: Failed to resolve import "./navigation"
```

- [ ] **Step 3: Create navigation model**

Create `web/src/lib/navigation.ts`:

```ts
export type NavigationEmphasis = "primary" | "standard";

export type NavigationItem = {
  readonly label: string;
  readonly href: string;
  readonly description: string;
  readonly emphasis: NavigationEmphasis;
};

export const primaryNavigation: readonly NavigationItem[] = [
  {
    label: "今日工作台",
    href: "/workspace",
    description: "查看项目状态、待办疑点、补证任务和索引健康。",
    emphasis: "standard"
  },
  {
    label: "AI 引导自查",
    href: "/guided-check",
    description: "通过自查向导、多轮对话和证据侧栏完成政策问答与材料自查。",
    emphasis: "primary"
  },
  {
    label: "专题规则库",
    href: "/rules",
    description: "查看医保基金使用合规、身份骗保等专题规则卡。",
    emphasis: "standard"
  },
  {
    label: "材料与文档检索",
    href: "/documents",
    description: "检索源文档、上传材料、定位引用原文。",
    emphasis: "standard"
  },
  {
    label: "疑点清单",
    href: "/findings",
    description: "管理风险等级、证据强度、待补条件和人工确认状态。",
    emphasis: "standard"
  },
  {
    label: "补证整改",
    href: "/remediation",
    description: "跟踪补证任务、整改建议、处理记录和关闭原因。",
    emphasis: "standard"
  },
  {
    label: "底稿/报告",
    href: "/reports",
    description: "生成自查底稿、整改记录和专题报告。",
    emphasis: "standard"
  },
  {
    label: "AI 数据分析",
    href: "/analytics",
    description: "查看风险分布、规则命中热区和整改进度。",
    emphasis: "standard"
  },
  {
    label: "知识图谱",
    href: "/graph",
    description: "展示项目内人员、材料、规则、疑点和整改关系。",
    emphasis: "standard"
  },
  {
    label: "项目档案",
    href: "/archive",
    description: "归档项目画像、会话、材料、疑点、报告和操作日志。",
    emphasis: "standard"
  }
];
```

- [ ] **Step 4: Create workflow state copy**

Create `web/src/lib/workflow.ts`:

```ts
export type SelfCheckWorkflowStage =
  | "intake"
  | "retrieve"
  | "analyze"
  | "clarify"
  | "finding"
  | "remediation"
  | "report";

export type WorkflowStageMeta = {
  readonly stage: SelfCheckWorkflowStage;
  readonly label: string;
  readonly description: string;
};

export const workflowStages: readonly WorkflowStageMeta[] = [
  {
    stage: "intake",
    label: "收集条件",
    description: "确认地区、机构类型、时间范围、材料类型和基金支付事实。"
  },
  {
    stage: "retrieve",
    label: "检索证据",
    description: "按专题规则卡筛选并排序证据。"
  },
  {
    stage: "analyze",
    label: "形成判断",
    description: "基于引用和规则卡输出政策解释或风险提示。"
  },
  {
    stage: "clarify",
    label: "缺证追问",
    description: "当证据不足时，要求用户补充材料或事实。"
  },
  {
    stage: "finding",
    label: "生成疑点",
    description: "把高风险结果转为待人工确认疑点。"
  },
  {
    stage: "remediation",
    label: "补证整改",
    description: "生成补证任务、整改建议和处理记录。"
  },
  {
    stage: "report",
    label: "汇总输出",
    description: "生成自查底稿、整改记录和专题报告。"
  }
];
```

- [ ] **Step 5: Run navigation tests**

Run:

```bash
pnpm --filter medical-audit-web test -- src/lib/navigation.test.ts
```

Expected:

```text
PASS  src/lib/navigation.test.ts
```

- [ ] **Step 6: Commit navigation model**

Run:

```bash
git add web/src/lib/navigation.ts web/src/lib/navigation.test.ts web/src/lib/workflow.ts
git commit -m "定义前端自查流程导航"
```

---

### Task 4: Implement Root Layout and Workspace Shell

**Files:**

- Create: `web/src/app/layout.tsx`
- Create: `web/src/app/page.tsx`
- Create: `web/src/app/(workspace)/layout.tsx`
- Create: `web/src/components/shell/app-sidebar.tsx`
- Create: `web/src/components/shell/project-context-bar.tsx`
- Create: `web/src/components/shell/workspace-shell.tsx`
- Create: `web/src/components/ui/status-pill.tsx`
- Test: `web/src/components/shell/workspace-shell.test.tsx`

- [ ] **Step 1: Write failing shell test**

Create `web/src/components/shell/workspace-shell.test.tsx`:

```tsx
import { render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { WorkspaceShell } from "./workspace-shell";

const { usePathnameMock } = vi.hoisted(() => ({
  usePathnameMock: vi.fn()
}));

vi.mock("next/navigation", () => ({
  usePathname: usePathnameMock
}));

describe("WorkspaceShell", () => {
  beforeEach(() => {
    usePathnameMock.mockReturnValue("/workspace");
  });

  it("renders route-aware navigation and project context without owning the page h1", () => {
    render(
      <WorkspaceShell>
        <main>页面内容</main>
      </WorkspaceShell>
    );

    expect(screen.getByRole("navigation", { name: "主导航" })).toBeInTheDocument();
    expect(screen.getByText("医保自查 OS")).toBeInTheDocument();
    expect(screen.getByText("AI 引导自查")).toBeInTheDocument();
    expect(screen.getByText("默认自查项目")).toBeInTheDocument();
    expect(screen.getByText("索引状态待接入")).toBeInTheDocument();
    expect(screen.getByText("页面内容")).toBeInTheDocument();

    expect(screen.getByRole("link", { name: /今日工作台/ })).toHaveAttribute("aria-current", "page");
    expect(screen.getByRole("link", { name: /AI 引导自查/ })).not.toHaveAttribute("aria-current");
    expect(screen.queryByRole("heading", { level: 1 })).not.toBeInTheDocument();
  });
});
```

- [ ] **Step 2: Run failing shell test**

Run:

```bash
pnpm --filter medical-audit-web test -- src/components/shell/workspace-shell.test.tsx
```

Expected:

```text
FAIL  src/components/shell/workspace-shell.test.tsx
Error: Failed to resolve import "./workspace-shell"
```

- [ ] **Step 3: Create status pill component**

Create `web/src/components/ui/status-pill.tsx`:

```tsx
type StatusTone = "neutral" | "info" | "warning" | "danger" | "success";

type StatusPillProps = {
  readonly children: React.ReactNode;
  readonly tone?: StatusTone;
};

const toneClassName: Record<StatusTone, string> = {
  neutral: "border-slate-200 bg-slate-50 text-slate-700",
  info: "border-blue-200 bg-blue-50 text-blue-700",
  warning: "border-amber-200 bg-amber-50 text-amber-800",
  danger: "border-red-200 bg-red-50 text-red-700",
  success: "border-emerald-200 bg-emerald-50 text-emerald-700"
};

export function StatusPill({ children, tone = "neutral" }: StatusPillProps) {
  return (
    <span className={`inline-flex items-center rounded-full border px-2.5 py-1 text-xs font-medium ${toneClassName[tone]}`}>
      {children}
    </span>
  );
}
```

- [ ] **Step 4: Create sidebar component**

Create `web/src/components/shell/app-sidebar.tsx`:

```tsx
"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

import { primaryNavigation } from "@/lib/navigation";

function isActivePath(pathname: string, href: string) {
  return pathname === href || pathname.startsWith(`${href}/`);
}

export function AppSidebar() {
  const pathname = usePathname();

  return (
    <aside className="flex w-full flex-col border-b border-slate-200/80 bg-white/92 px-4 py-4 shadow-[0_12px_40px_rgb(16_24_40/0.04)] sm:px-5 md:min-h-screen md:w-72 md:border-r md:border-b-0 md:py-6 md:shadow-[12px_0_40px_rgb(16_24_40/0.04)]">
      <Link href="/workspace" className="audit-focus-ring rounded-2xl">
        <div className="flex items-center gap-3">
          <div className="grid size-10 place-items-center rounded-2xl bg-blue-600 text-sm font-semibold text-white shadow-lg shadow-blue-600/20">
            AI
          </div>
          <div>
            <p className="text-base font-semibold tracking-tight text-slate-950">医保自查 OS</p>
            <p className="text-xs text-slate-500">Medical Audit Self-Check</p>
          </div>
        </div>
      </Link>

      <nav className="mt-8 flex flex-1 flex-col gap-1.5" aria-label="主导航">
        {primaryNavigation.map((item) => {
          const isActive = isActivePath(pathname, item.href);

          return (
            <Link
              key={item.href}
              href={item.href}
              aria-current={isActive ? "page" : undefined}
              className={`audit-focus-ring rounded-2xl px-3 py-3 text-sm transition ${
                isActive
                  ? "bg-blue-50 text-blue-700 shadow-sm ring-1 ring-blue-100"
                  : "text-slate-700 hover:bg-slate-50 hover:text-slate-950"
              }`}
            >
              <span className="block font-medium">{item.label}</span>
              <span className="mt-0.5 block truncate text-xs text-slate-500">{item.description}</span>
            </Link>
          );
        })}
      </nav>
    </aside>
  );
}
```

- [ ] **Step 5: Create project context bar**

Create `web/src/components/shell/project-context-bar.tsx`:

```tsx
import { StatusPill } from "@/components/ui/status-pill";

export function ProjectContextBar() {
  return (
    <header className="sticky top-0 z-20 border-b border-slate-200/80 bg-white/82 px-4 py-4 backdrop-blur-xl sm:px-6 md:px-8">
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div>
          <p className="text-xs font-medium uppercase tracking-[0.18em] text-slate-500">当前自查项目</p>
          <div className="mt-1 text-xl font-semibold tracking-tight text-slate-950">默认自查项目</div>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <StatusPill tone="info">医保基金使用合规</StatusPill>
          <StatusPill tone="warning">证据待补充</StatusPill>
          <StatusPill tone="neutral">索引状态待接入</StatusPill>
        </div>
      </div>
    </header>
  );
}
```

- [ ] **Step 6: Create workspace shell**

Create `web/src/components/shell/workspace-shell.tsx`:

```tsx
import { AppSidebar } from "./app-sidebar";
import { ProjectContextBar } from "./project-context-bar";

type WorkspaceShellProps = {
  readonly children: React.ReactNode;
};

export function WorkspaceShell({ children }: WorkspaceShellProps) {
  return (
    <div className="min-h-screen bg-[var(--audit-bg)]">
      <div className="flex min-h-screen flex-col md:flex-row">
        <AppSidebar />
        <div className="min-w-0 flex-1">
          <ProjectContextBar />
          <div className="px-4 py-5 sm:px-6 md:px-8 md:py-8">{children}</div>
        </div>
      </div>
    </div>
  );
}
```

- [ ] **Step 7: Create root layout**

Create `web/src/app/layout.tsx`:

```tsx
import type { Metadata } from "next";

import "./globals.css";

export const metadata: Metadata = {
  title: "医保审计自查工作台",
  description: "面向医院和机构自查人员的医保审计知识库与自查工作台"
};

export default function RootLayout({
  children
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="zh-CN">
      <body>{children}</body>
    </html>
  );
}
```

- [ ] **Step 8: Create root page**

Create `web/src/app/page.tsx`:

```tsx
import { redirect } from "next/navigation";

export default function HomePage() {
  redirect("/workspace");
}
```

- [ ] **Step 9: Create workspace route group layout**

Create `web/src/app/(workspace)/layout.tsx`:

```tsx
import { WorkspaceShell } from "@/components/shell/workspace-shell";

export default function WorkspaceLayout({
  children
}: Readonly<{
  children: React.ReactNode;
}>) {
  return <WorkspaceShell>{children}</WorkspaceShell>;
}
```

- [ ] **Step 10: Run shell test**

Run:

```bash
pnpm --filter medical-audit-web test -- src/components/shell/workspace-shell.test.tsx
```

Expected:

```text
PASS  src/components/shell/workspace-shell.test.tsx
```

- [ ] **Step 11: Commit shell**

Run:

```bash
git add web/src/app/layout.tsx web/src/app/page.tsx web/src/app/'(workspace)'/layout.tsx web/src/components/shell web/src/components/ui
git commit -m "搭建自查工作台页面壳层"
```

---

### Task 5: Add Foundation Pages for All Planned Modules

**Files:**

- Create: `web/src/components/ui/module-card.tsx`
- Create: `web/src/app/(workspace)/workspace/page.tsx`
- Create: `web/src/app/(workspace)/guided-check/page.tsx`
- Create: `web/src/app/(workspace)/rules/page.tsx`
- Create: `web/src/app/(workspace)/documents/page.tsx`
- Create: `web/src/app/(workspace)/findings/page.tsx`
- Create: `web/src/app/(workspace)/remediation/page.tsx`
- Create: `web/src/app/(workspace)/reports/page.tsx`
- Create: `web/src/app/(workspace)/analytics/page.tsx`
- Create: `web/src/app/(workspace)/graph/page.tsx`
- Create: `web/src/app/(workspace)/archive/page.tsx`

- [ ] **Step 1: Create module card component**

Create `web/src/components/ui/module-card.tsx`:

```tsx
import Link from "next/link";

type ModuleCardProps = {
  readonly title: string;
  readonly description: string;
  readonly href: string;
  readonly badge: string;
};

export function ModuleCard({ title, description, href, badge }: ModuleCardProps) {
  return (
    <Link
      href={href}
      className="audit-focus-ring block rounded-[var(--audit-radius-lg)] border border-slate-200 bg-white p-5 shadow-[var(--audit-shadow-card)] transition hover:-translate-y-0.5 hover:border-blue-200"
    >
      <span className="inline-flex rounded-full border border-blue-100 bg-blue-50 px-2.5 py-1 text-xs font-medium text-blue-700">
        {badge}
      </span>
      <h2 className="mt-4 text-lg font-semibold tracking-tight text-slate-950">{title}</h2>
      <p className="mt-2 text-sm leading-6 text-slate-600">{description}</p>
    </Link>
  );
}
```

- [ ] **Step 2: Create today workspace page**

Create `web/src/app/(workspace)/workspace/page.tsx`:

```tsx
import { ModuleCard } from "@/components/ui/module-card";
import { primaryNavigation } from "@/lib/navigation";
import { workflowStages } from "@/lib/workflow";

export default function WorkspacePage() {
  return (
    <main>
      <section className="rounded-[28px] border border-slate-200 bg-white p-7 shadow-[var(--audit-shadow-card)]">
        <p className="text-sm font-medium text-blue-700">今日工作台</p>
        <h1 className="mt-2 text-3xl font-semibold tracking-tight text-slate-950">机构自查闭环总览</h1>
        <p className="mt-3 max-w-3xl text-sm leading-6 text-slate-600">
          当前阶段先提供前端基座和模块入口。后续计划会把项目、材料、疑点、补证和报告逐步接入真实 API。
        </p>
      </section>

      <section className="mt-6 grid gap-4 lg:grid-cols-2">
        {primaryNavigation.slice(1).map((item) => (
          <ModuleCard
            key={item.href}
            title={item.label}
            description={item.description}
            href={item.href}
            badge={item.emphasis === "primary" ? "核心流程" : "流程模块"}
          />
        ))}
      </section>

      <section className="mt-6 rounded-[28px] border border-slate-200 bg-white p-7 shadow-[var(--audit-shadow-card)]">
        <h2 className="text-lg font-semibold text-slate-950">AI 自查状态机</h2>
        <div className="mt-4 grid gap-3 md:grid-cols-2 xl:grid-cols-4">
          {workflowStages.map((stage) => (
            <div key={stage.stage} className="rounded-2xl border border-slate-200 bg-slate-50 p-4">
              <p className="text-sm font-semibold text-slate-950">{stage.label}</p>
              <p className="mt-1 text-xs leading-5 text-slate-600">{stage.description}</p>
            </div>
          ))}
        </div>
      </section>
    </main>
  );
}
```

- [ ] **Step 3: Create module page template content**

For each module route below, create a `page.tsx` file with exact content.

Create `web/src/app/(workspace)/guided-check/page.tsx`:

```tsx
export default function GuidedCheckPage() {
  return <ModulePreview title="AI 引导自查" stage="自查向导 + 多轮对话 + 证据侧栏" />;
}

function ModulePreview({ title, stage }: { readonly title: string; readonly stage: string }) {
  return (
    <main className="rounded-[28px] border border-slate-200 bg-white p-7 shadow-[var(--audit-shadow-card)]">
      <p className="text-sm font-medium text-blue-700">Plan 03 接入真实功能</p>
      <h1 className="mt-2 text-3xl font-semibold tracking-tight text-slate-950">{title}</h1>
      <p className="mt-3 text-sm leading-6 text-slate-600">{stage}</p>
    </main>
  );
}
```

Create `web/src/app/(workspace)/rules/page.tsx`:

```tsx
export default function RulesPage() {
  return <ModulePreview title="专题规则库" stage="规则卡 Markdown / JSON、适用地区、证据状态和生命周期" />;
}

function ModulePreview({ title, stage }: { readonly title: string; readonly stage: string }) {
  return (
    <main className="rounded-[28px] border border-slate-200 bg-white p-7 shadow-[var(--audit-shadow-card)]">
      <p className="text-sm font-medium text-blue-700">Plan 04 接入真实功能</p>
      <h1 className="mt-2 text-3xl font-semibold tracking-tight text-slate-950">{title}</h1>
      <p className="mt-3 text-sm leading-6 text-slate-600">{stage}</p>
    </main>
  );
}
```

Create `web/src/app/(workspace)/documents/page.tsx`:

```tsx
export default function DocumentsPage() {
  return <ModulePreview title="材料与文档检索" stage="源文档、上传材料、全文检索、向量检索和引用定位" />;
}

function ModulePreview({ title, stage }: { readonly title: string; readonly stage: string }) {
  return (
    <main className="rounded-[28px] border border-slate-200 bg-white p-7 shadow-[var(--audit-shadow-card)]">
      <p className="text-sm font-medium text-blue-700">Plan 05 接入真实功能</p>
      <h1 className="mt-2 text-3xl font-semibold tracking-tight text-slate-950">{title}</h1>
      <p className="mt-3 text-sm leading-6 text-slate-600">{stage}</p>
    </main>
  );
}
```

Create `web/src/app/(workspace)/findings/page.tsx`:

```tsx
export default function FindingsPage() {
  return <ModulePreview title="疑点清单" stage="风险等级、规则依据、证据强度、待补条件和人工确认状态" />;
}

function ModulePreview({ title, stage }: { readonly title: string; readonly stage: string }) {
  return (
    <main className="rounded-[28px] border border-slate-200 bg-white p-7 shadow-[var(--audit-shadow-card)]">
      <p className="text-sm font-medium text-blue-700">Plan 06 接入真实功能</p>
      <h1 className="mt-2 text-3xl font-semibold tracking-tight text-slate-950">{title}</h1>
      <p className="mt-3 text-sm leading-6 text-slate-600">{stage}</p>
    </main>
  );
}
```

Create `web/src/app/(workspace)/remediation/page.tsx`:

```tsx
export default function RemediationPage() {
  return <ModulePreview title="补证整改" stage="补证任务、整改建议、处理记录、复核意见和关闭原因" />;
}

function ModulePreview({ title, stage }: { readonly title: string; readonly stage: string }) {
  return (
    <main className="rounded-[28px] border border-slate-200 bg-white p-7 shadow-[var(--audit-shadow-card)]">
      <p className="text-sm font-medium text-blue-700">Plan 07 接入真实功能</p>
      <h1 className="mt-2 text-3xl font-semibold tracking-tight text-slate-950">{title}</h1>
      <p className="mt-3 text-sm leading-6 text-slate-600">{stage}</p>
    </main>
  );
}
```

Create `web/src/app/(workspace)/reports/page.tsx`:

```tsx
export default function ReportsPage() {
  return <ModulePreview title="底稿/报告" stage="自查底稿、整改记录、专题报告和引用链校验" />;
}

function ModulePreview({ title, stage }: { readonly title: string; readonly stage: string }) {
  return (
    <main className="rounded-[28px] border border-slate-200 bg-white p-7 shadow-[var(--audit-shadow-card)]">
      <p className="text-sm font-medium text-blue-700">Plan 08 接入真实功能</p>
      <h1 className="mt-2 text-3xl font-semibold tracking-tight text-slate-950">{title}</h1>
      <p className="mt-3 text-sm leading-6 text-slate-600">{stage}</p>
    </main>
  );
}
```

Create `web/src/app/(workspace)/analytics/page.tsx`:

```tsx
export default function AnalyticsPage() {
  return <ModulePreview title="AI 数据分析" stage="风险分布、规则命中热区、材料覆盖度和整改进度" />;
}

function ModulePreview({ title, stage }: { readonly title: string; readonly stage: string }) {
  return (
    <main className="rounded-[28px] border border-slate-200 bg-white p-7 shadow-[var(--audit-shadow-card)]">
      <p className="text-sm font-medium text-blue-700">Plan 09 接入真实功能</p>
      <h1 className="mt-2 text-3xl font-semibold tracking-tight text-slate-950">{title}</h1>
      <p className="mt-3 text-sm leading-6 text-slate-600">{stage}</p>
    </main>
  );
}
```

Create `web/src/app/(workspace)/graph/page.tsx`:

```tsx
export default function GraphPage() {
  return <ModulePreview title="知识图谱" stage="机构、人员身份、医保基金支付、规则卡、材料、疑点和整改关系" />;
}

function ModulePreview({ title, stage }: { readonly title: string; readonly stage: string }) {
  return (
    <main className="rounded-[28px] border border-slate-200 bg-white p-7 shadow-[var(--audit-shadow-card)]">
      <p className="text-sm font-medium text-blue-700">Plan 10 接入真实功能</p>
      <h1 className="mt-2 text-3xl font-semibold tracking-tight text-slate-950">{title}</h1>
      <p className="mt-3 text-sm leading-6 text-slate-600">{stage}</p>
    </main>
  );
}
```

Create `web/src/app/(workspace)/archive/page.tsx`:

```tsx
export default function ArchivePage() {
  return <ModulePreview title="项目档案" stage="项目画像、会话、材料、疑点、任务、报告和操作日志" />;
}

function ModulePreview({ title, stage }: { readonly title: string; readonly stage: string }) {
  return (
    <main className="rounded-[28px] border border-slate-200 bg-white p-7 shadow-[var(--audit-shadow-card)]">
      <p className="text-sm font-medium text-blue-700">Plan 11 接入真实功能</p>
      <h1 className="mt-2 text-3xl font-semibold tracking-tight text-slate-950">{title}</h1>
      <p className="mt-3 text-sm leading-6 text-slate-600">{stage}</p>
    </main>
  );
}
```

- [ ] **Step 4: Run typecheck**

Run:

```bash
pnpm web:typecheck
```

Expected:

```text
Done in
```

- [ ] **Step 5: Commit module pages**

Run:

```bash
git add web/src/app/'(workspace)' web/src/components/ui/module-card.tsx
git commit -m "补齐自查工作台模块入口"
```

---

### Task 6: Add Backend API Client for Existing FastAPI Capabilities

**Files:**

- Create: `web/src/lib/api-types.ts`
- Create: `web/src/lib/api-client.ts`
- Test: `web/src/lib/api-client.test.ts`

- [ ] **Step 1: Write failing API client test**

Create `web/src/lib/api-client.test.ts`:

```ts
import { afterEach, describe, expect, it, vi } from "vitest";

import { fetchBackendHealth, fetchSearchBackendStatus } from "./api-client";

describe("api-client", () => {
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("fetches backend health through the Next proxy", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => ({
        ok: true,
        json: async () => ({
          status: "ok",
          version: "0.1.0",
          data_root: "/tmp/data"
        })
      }))
    );

    const health = await fetchBackendHealth();

    expect(fetch).toHaveBeenCalledWith("/api/backend/health", {
      headers: { Accept: "application/json" },
      cache: "no-store"
    });
    expect(health.status).toBe("ok");
  });

  it("raises a clear error when the search backend check fails", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => ({
        ok: false,
        status: 409,
        text: async () => "search engine is not initialized"
      }))
    );

    await expect(fetchSearchBackendStatus()).rejects.toThrow(
      "Backend request failed: GET /api/backend/index/search-backend returned 409"
    );
  });
});
```

- [ ] **Step 2: Run failing API client test**

Run:

```bash
pnpm --filter medical-audit-web test -- src/lib/api-client.test.ts
```

Expected:

```text
FAIL  src/lib/api-client.test.ts
Error: Failed to resolve import "./api-client"
```

- [ ] **Step 3: Create API types**

Create `web/src/lib/api-types.ts`:

```ts
export type BackendHealthResponse = {
  readonly status: "ok";
  readonly version: string;
  readonly data_root: string;
};

export type SearchBackendStatusResponse = {
  readonly backend: string;
  readonly ready: boolean;
  readonly details?: Record<string, unknown>;
  readonly matching_embedding_count?: number;
};
```

- [ ] **Step 4: Create API client**

Create `web/src/lib/api-client.ts`:

```ts
import type { BackendHealthResponse, SearchBackendStatusResponse } from "./api-types";

async function getJson<T>(path: string): Promise<T> {
  const response = await fetch(path, {
    headers: { Accept: "application/json" },
    cache: "no-store"
  });

  if (!response.ok) {
    throw new Error(`Backend request failed: GET ${path} returned ${response.status}`);
  }

  return (await response.json()) as T;
}

export function fetchBackendHealth(): Promise<BackendHealthResponse> {
  return getJson<BackendHealthResponse>("/api/backend/health");
}

export function fetchSearchBackendStatus(): Promise<SearchBackendStatusResponse> {
  return getJson<SearchBackendStatusResponse>("/api/backend/index/search-backend");
}
```

- [ ] **Step 5: Run API client test**

Run:

```bash
pnpm --filter medical-audit-web test -- src/lib/api-client.test.ts
```

Expected:

```text
PASS  src/lib/api-client.test.ts
```

- [ ] **Step 6: Commit API client**

Run:

```bash
git add web/src/lib/api-types.ts web/src/lib/api-client.ts web/src/lib/api-client.test.ts
git commit -m "接入前端后端代理客户端"
```

---

### Task 7: Add Foundation E2E Smoke Test

**Files:**

- Create: `web/tests/e2e/foundation.spec.ts`

- [ ] **Step 1: Write E2E test**

Create `web/tests/e2e/foundation.spec.ts`:

```ts
import { expect, test } from "@playwright/test";

test("self-check OS foundation renders navigation and core modules", async ({ page }) => {
  await page.goto("/workspace");

  await expect(page.getByRole("heading", { name: "机构自查闭环总览" })).toBeVisible();
  await expect(page.getByRole("link", { name: /AI 引导自查/ })).toBeVisible();
  await expect(page.getByRole("link", { name: /专题规则库/ })).toBeVisible();
  await expect(page.getByText("AI 自查状态机")).toBeVisible();
});

test("guided check route is reachable", async ({ page }) => {
  await page.goto("/guided-check");

  await expect(page.getByRole("heading", { name: "AI 引导自查" })).toBeVisible();
  await expect(page.getByText("自查向导 + 多轮对话 + 证据侧栏")).toBeVisible();
});
```

- [ ] **Step 2: Install Playwright browser if missing**

Run:

```bash
pnpm --filter medical-audit-web exec playwright install chromium
```

Expected:

```text
Chromium
```

The command may print that Chromium is already installed.

- [ ] **Step 3: Run E2E test**

Run:

```bash
pnpm web:e2e
```

Expected:

```text
2 passed
```

- [ ] **Step 4: Commit E2E test**

Run:

```bash
git add web/tests/e2e/foundation.spec.ts
git commit -m "增加前端基座端到端冒烟"
```

---

### Task 8: Run Full Foundation Gate and Record Evidence

**Files:**

- Create: `tmp/outputs/frontend-foundation-gate-20260607.txt`
- Modify: `drafts/docs/product-frontend-refactor-plan-01-foundation-draft-20260607.md`

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
} | tee tmp/outputs/frontend-foundation-gate-20260607.txt
```

Expected:

```text
## pnpm web:typecheck

## pnpm web:test

## pnpm web:build

## pnpm web:e2e
```

All four sections must exit successfully. If a command fails, stop and fix the failing task before continuing.

- [ ] **Step 2: Verify legacy FastAPI pages were not removed**

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

If files appear in the diff, inspect them. Plan 01 must not alter legacy Jinja pages.

- [ ] **Step 3: Update this plan status**

In this file, change frontmatter:

```yaml
status: draft
```

to:

```yaml
status: review
```

Do not mark `stable` until the user accepts the foundation implementation.

- [ ] **Step 4: Commit final gate evidence**

Run:

```bash
git add drafts/docs/product-frontend-refactor-plan-01-foundation-draft-20260607.md tmp/outputs/frontend-foundation-gate-20260607.txt
git commit -m "记录前端基座验收证据"
```

---

## Self-Review

Spec coverage:

- Covers Next.js base, design system, route shell, module entry pages, API proxy client, tests, and old-page fallback.
- Does not implement project persistence, multi-round chat, materials, findings, remediation, reports, analytics, graph, or archive. Those are intentionally downstream plans.

Foundation preview scan:

- No unfinished markers or vague implementation instructions.
- Foundation preview pages are explicit route-entry deliverables for Plan 01, not a substitute for downstream module implementation.

Type consistency:

- `NavigationItem`, `SelfCheckWorkflowStage`, `BackendHealthResponse`, and `SearchBackendStatusResponse` are introduced before use.
- Test names and import paths match the files created in earlier steps.

Execution choice after this plan is approved:

1. **Subagent-Driven recommended**: implement each task in a fresh context, then review and gate.
2. **Inline Execution**: execute this plan in the current session with checkpoints after each task.

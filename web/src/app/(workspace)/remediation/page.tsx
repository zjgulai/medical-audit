"use client";

import { useEffect, useState } from "react";

import { DataSourceBadge } from "@/components/ui/data-source-badge";
import { StatusPill } from "@/components/ui/status-pill";
import { fetchRemediationWorkbench } from "@/lib/api-client";
import type {
  RemediationCaseApiItem,
  RemediationClosureGateApiItem,
  RemediationEvidenceRequestApiItem,
  RemediationTimelineApiItem,
  RemediationWorkbenchResponse
} from "@/lib/api-types";
import {
  remediationCases,
  remediationClosureGates,
  remediationEvidenceRequests,
  remediationTimeline
} from "@/lib/portal-data";

const staticRemediationWorkbench: RemediationWorkbenchResponse = {
  format: "remediation-workbench-v1",
  generated_at: "static-fallback",
  workbench_id: "FUND-USAGE-REMEDIATION",
  workbench_title: "整改事项与补证闭环",
  workbench_scope: "把报告整改事项、补证请求、责任科室和验收门禁组织成可追踪的整改工作台。",
  remediation_cases: remediationCases,
  evidence_requests: remediationEvidenceRequests,
  closure_gates: remediationClosureGates,
  timeline: remediationTimeline,
  metrics: buildRemediationMetrics(
    remediationCases,
    remediationEvidenceRequests,
    remediationClosureGates,
    remediationTimeline
  ),
  evidence_grade: "static-fallback",
  production_side_effect: "none",
  store: { ready: false, backend: "portal-data-static-fallback" }
};

export default function RemediationPage() {
  const [workbench, setWorkbench] = useState<RemediationWorkbenchResponse>(staticRemediationWorkbench);
  const [backendStatus, setBackendStatus] = useState<"loading" | "ready" | "fallback">("loading");

  useEffect(() => {
    let active = true;

    fetchRemediationWorkbench()
      .then((response) => {
        if (!active) {
          return;
        }
        setWorkbench(response);
        setBackendStatus("ready");
      })
      .catch(() => {
        if (!active) {
          return;
        }
        setWorkbench(staticRemediationWorkbench);
        setBackendStatus("fallback");
      });

    return () => {
      active = false;
    };
  }, []);

  const statusTone = backendStatus === "ready" ? "success" : backendStatus === "loading" ? "info" : "warning";
  const statusLabel =
    backendStatus === "ready" ? "后端已连接" : backendStatus === "loading" ? "连接中" : "本地样例兜底";

  return (
    <main className="grid min-w-0 items-start gap-4 xl:grid-cols-[17rem_minmax(0,1fr)_18rem]">
      <aside className="audit-panel-rail min-w-0 p-5">
        <h2 className="audit-section-title">整改事项</h2>
        <p className="audit-copy mt-2">按责任科室和验收状态跟踪报告后的整改闭环。</p>
        <div className="mt-3">
          <StatusPill tone={statusTone}>{statusLabel}</StatusPill>
        </div>
        <div className="mt-5 space-y-3">
          {workbench.remediation_cases.map((item) => (
            <RemediationIndexCard key={item.id} item={item} />
          ))}
        </div>
      </aside>

      <section className="audit-panel min-w-0 p-6">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div>
            <p className="audit-kicker">补证整改</p>
            <h1 className="audit-page-title">{workbench.workbench_title}</h1>
            <p className="audit-copy mt-2 max-w-3xl">
              {workbench.workbench_scope}
            </p>
          </div>
          <div className="flex flex-col items-end gap-2">
            <StatusPill tone="warning">验收门禁</StatusPill>
            <DataSourceBadge source="hybrid" />
          </div>
        </div>

        <div className="mt-6 grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
          <RemediationMetric label="未关闭事项" value={`${workbench.metrics.active_case_count} 项`} />
          <RemediationMetric label="待补证材料" value={`${workbench.metrics.pending_evidence_count} 份`} />
          <RemediationMetric label="阻断门禁" value={`${workbench.metrics.blocked_gate_count} 项`} />
          <RemediationMetric label="平均进度" value={`${workbench.metrics.average_progress}%`} />
        </div>

        <section className="mt-6" aria-labelledby="remediation-ledger-title">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <h2 id="remediation-ledger-title" className="audit-section-title">
              整改台账
            </h2>
            <a className="audit-focus-ring audit-btn audit-btn-secondary" href="/reports">
              查看报告来源
            </a>
          </div>

          <div className="mt-4 grid gap-3">
            {workbench.remediation_cases.map((item) => (
              <RemediationCard key={item.id} item={item} />
            ))}
          </div>
        </section>

        <section className="mt-6 grid gap-5" aria-labelledby="evidence-requests-title">
          <div>
            <h2 id="evidence-requests-title" className="audit-section-title">
              补证请求
            </h2>
            <div className="mt-4 grid gap-3">
              {workbench.evidence_requests.map((request) => (
                <EvidenceRequestCard key={request.id} request={request} />
              ))}
            </div>
          </div>

          <aside className="audit-callout p-5">
            <p className="audit-kicker">关闭规则</p>
            <h3 className="audit-section-title mt-2">验收前不得结案</h3>
            <p className="audit-copy mt-2">
              整改说明、补证材料和负责人确认全部通过后，才能进入项目归档检查。
            </p>
          </aside>
        </section>
      </section>

      <aside className="min-w-0 space-y-4">
        <section className="audit-panel-rail p-5">
          <h2 className="audit-section-title">关闭门禁</h2>
          <div className="mt-4 space-y-3">
            {workbench.closure_gates.map((gate) => (
              <ClosureGateCard key={gate.id} gate={gate} />
            ))}
          </div>
        </section>

        <section className="audit-panel-rail p-5">
          <h2 className="audit-section-title">整改动态</h2>
          <div className="mt-4 space-y-3">
            {workbench.timeline.map((item) => (
              <TimelineCard key={item.id} item={item} />
            ))}
          </div>
        </section>

        <a className="audit-focus-ring audit-action-card p-5" href="/graph">
          <p className="audit-kicker">知识图谱</p>
          <h2 className="audit-section-title mt-2">查看整改证据链</h2>
          <p className="audit-copy mt-2">整改事项已经和报告、复核、疑点、项目归档关系连通。</p>
        </a>
      </aside>
    </main>
  );
}

function buildRemediationMetrics(
  cases: readonly RemediationCaseApiItem[],
  evidenceRequests: readonly RemediationEvidenceRequestApiItem[],
  closureGates: readonly RemediationClosureGateApiItem[],
  timeline: readonly RemediationTimelineApiItem[]
): RemediationWorkbenchResponse["metrics"] {
  return {
    case_count: cases.length,
    active_case_count: cases.filter((item) => item.status !== "已关闭").length,
    closed_case_count: cases.filter((item) => item.status === "已关闭").length,
    pending_evidence_count: evidenceRequests.filter(
      (item) => item.status === "待上传" || item.status === "需退回"
    ).length,
    blocked_gate_count: closureGates.filter((gate) => gate.status === "阻断").length,
    average_progress: cases.length
      ? Math.round(cases.reduce((sum, item) => sum + item.progress, 0) / cases.length)
      : 0,
    timeline_count: timeline.length
  };
}

function RemediationIndexCard({ item }: { readonly item: RemediationCaseApiItem }) {
  return (
    <a className="audit-focus-ring block rounded-[var(--audit-radius-md)] border border-[var(--audit-line)] bg-white p-3 hover:bg-[var(--audit-primary-soft)]" href={item.href}>
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <h3 className="truncate text-sm font-semibold text-[var(--audit-ink)]">{item.title}</h3>
          <p className="audit-meta mt-1">{item.department} / {item.dueDate}</p>
        </div>
        <StatusPill tone={getRemediationStatusTone(item.status)}>{item.status}</StatusPill>
      </div>
      <div className="mt-3">
        <ProgressBar value={item.progress} />
      </div>
    </a>
  );
}

function RemediationMetric({ label, value }: { readonly label: string; readonly value: string }) {
  return (
    <div className="audit-panel-muted p-4">
      <p className="audit-label">{label}</p>
      <p className="audit-metric-value mt-2">{value}</p>
    </div>
  );
}

function RemediationCard({ item }: { readonly item: RemediationCaseApiItem }) {
  return (
    <article className="audit-panel-muted p-4">
      <div className="flex items-start justify-between gap-3">
        <div>
          <h3 className="audit-compact-title">{item.title}</h3>
          <p className="audit-meta mt-1">{item.reportNo}</p>
        </div>
        <StatusPill tone={getRemediationStatusTone(item.status)}>{item.status}</StatusPill>
      </div>
      <p className="audit-copy mt-3">{item.nextAction}</p>
      <dl className="audit-meta mt-4 grid grid-cols-2 gap-3">
        <div>
          <dt className="font-semibold">责任科室</dt>
          <dd className="mt-1 text-[var(--audit-ink)]">{item.department}</dd>
        </div>
        <div>
          <dt className="font-semibold">期限</dt>
          <dd className="mt-1 text-[var(--audit-ink)]">{item.dueDate}</dd>
        </div>
        <div>
          <dt className="font-semibold">来源</dt>
          <dd className="mt-1 break-words text-[var(--audit-ink)]">{item.sourceFinding}</dd>
        </div>
        <div>
          <dt className="font-semibold">补证</dt>
          <dd className="mt-1 text-[var(--audit-ink)]">{item.evidenceStatus}</dd>
        </div>
      </dl>
      <div className="mt-4">
        <ProgressBar value={item.progress} />
      </div>
      <a className="audit-focus-ring audit-btn audit-btn-primary mt-4 w-full" href={item.href}>
        查看详情
      </a>
    </article>
  );
}

function EvidenceRequestCard({ request }: { readonly request: RemediationEvidenceRequestApiItem }) {
  return (
    <article className="audit-panel-muted p-4">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h3 className="audit-card-title">{request.title}</h3>
          <p className="audit-meta mt-1">
            {request.kind} / {request.owner} / {request.dueDate}
          </p>
        </div>
        <StatusPill tone={getEvidenceStatusTone(request.status)}>{request.status}</StatusPill>
      </div>
      <p className="audit-copy mt-3">{request.detail}</p>
      <a className="audit-focus-ring audit-btn audit-btn-secondary mt-4" href={request.href}>
        查看材料
      </a>
    </article>
  );
}

function ClosureGateCard({ gate }: { readonly gate: RemediationClosureGateApiItem }) {
  return (
    <article className="rounded-[var(--audit-radius-md)] border border-[var(--audit-line)] bg-[var(--audit-surface-muted)] p-3">
      <div className="flex items-start justify-between gap-3">
        <div>
          <h3 className="audit-compact-title">{gate.label}</h3>
          <p className="audit-meta mt-1">责任方：{gate.owner}</p>
        </div>
        <StatusPill tone={getGateTone(gate.status)}>{gate.status}</StatusPill>
      </div>
      <p className="audit-copy mt-3">{gate.detail}</p>
    </article>
  );
}

function TimelineCard({ item }: { readonly item: RemediationTimelineApiItem }) {
  return (
    <article className="rounded-[var(--audit-radius-md)] border border-[var(--audit-line)] bg-[var(--audit-surface-muted)] p-3">
      <div className="flex items-start justify-between gap-3">
        <div>
          <h3 className="audit-compact-title">{item.title}</h3>
          <p className="audit-meta mt-1">{item.time}</p>
        </div>
        <StatusPill tone={item.status === "已记录" ? "success" : item.status === "已阻断" ? "danger" : "warning"}>
          {item.status}
        </StatusPill>
      </div>
      <p className="audit-copy mt-3">{item.detail}</p>
    </article>
  );
}

function ProgressBar({ value }: { readonly value: number }) {
  return (
    <div>
      <div className="flex items-center justify-between gap-2 text-xs">
        <span className="font-semibold text-[var(--audit-ink-subtle)]">进度</span>
        <span className="font-semibold text-[var(--audit-ink)]">{value}%</span>
      </div>
      <div className="mt-2 h-2 overflow-hidden rounded-full bg-[var(--audit-surface-subtle)]">
        <div className={`h-full rounded-full bg-[var(--audit-primary)] ${getProgressWidthClass(value)}`} />
      </div>
    </div>
  );
}

function getProgressWidthClass(value: number) {
  if (value >= 100) {
    return "w-full";
  }

  if (value >= 80) {
    return "w-4/5";
  }

  if (value >= 60) {
    return "w-3/5";
  }

  if (value >= 20) {
    return "w-1/4";
  }

  return "w-1/5";
}

function getRemediationStatusTone(status: RemediationCaseApiItem["status"]) {
  if (status === "已关闭") {
    return "success";
  }

  if (status === "待验收" || status === "整改中") {
    return "info";
  }

  return "warning";
}

function getEvidenceStatusTone(status: RemediationEvidenceRequestApiItem["status"]) {
  if (status === "已验收") {
    return "success";
  }

  if (status === "已提交") {
    return "info";
  }

  if (status === "需退回") {
    return "danger";
  }

  return "warning";
}

function getGateTone(status: RemediationClosureGateApiItem["status"]) {
  if (status === "通过") {
    return "success";
  }

  if (status === "阻断") {
    return "danger";
  }

  return "warning";
}

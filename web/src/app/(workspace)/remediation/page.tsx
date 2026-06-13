import { StatusPill } from "@/components/ui/status-pill";
import {
  remediationCases,
  remediationClosureGates,
  remediationEvidenceRequests,
  remediationTimeline
} from "@/lib/portal-data";
import type {
  RemediationCase,
  RemediationClosureGate,
  RemediationEvidenceRequest,
  RemediationTimelineItem
} from "@/lib/portal-data";

const activeCaseCount = remediationCases.filter((item) => item.status !== "已关闭").length;
const pendingEvidenceCount = remediationEvidenceRequests.filter((item) => item.status === "待上传" || item.status === "需退回").length;
const blockedGateCount = remediationClosureGates.filter((gate) => gate.status === "阻断").length;
const averageProgress = Math.round(remediationCases.reduce((sum, item) => sum + item.progress, 0) / remediationCases.length);

export default function RemediationPage() {
  return (
    <main className="grid min-w-0 items-start gap-4 xl:grid-cols-[17rem_minmax(0,1fr)_18rem]">
      <aside className="audit-panel-rail min-w-0 p-5">
        <h2 className="audit-section-title">整改事项</h2>
        <p className="audit-copy mt-2">按责任科室和验收状态跟踪报告后的整改闭环。</p>
        <div className="mt-5 space-y-3">
          {remediationCases.map((item) => (
            <RemediationIndexCard key={item.id} item={item} />
          ))}
        </div>
      </aside>

      <section className="audit-panel min-w-0 p-6">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div>
            <p className="audit-kicker">补证整改</p>
            <h1 className="audit-page-title">整改事项与补证闭环</h1>
            <p className="audit-copy mt-2 max-w-3xl">
              把报告整改事项、补证请求、责任科室和验收门禁组织成可追踪的整改工作台。
            </p>
          </div>
          <StatusPill tone="warning">验收门禁</StatusPill>
        </div>

        <div className="mt-6 grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
          <RemediationMetric label="未关闭事项" value={`${activeCaseCount} 项`} />
          <RemediationMetric label="待补证材料" value={`${pendingEvidenceCount} 份`} />
          <RemediationMetric label="阻断门禁" value={`${blockedGateCount} 项`} />
          <RemediationMetric label="平均进度" value={`${averageProgress}%`} />
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
            {remediationCases.map((item) => (
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
              {remediationEvidenceRequests.map((request) => (
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
            {remediationClosureGates.map((gate) => (
              <ClosureGateCard key={gate.id} gate={gate} />
            ))}
          </div>
        </section>

        <section className="audit-panel-rail p-5">
          <h2 className="audit-section-title">整改动态</h2>
          <div className="mt-4 space-y-3">
            {remediationTimeline.map((item) => (
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

function RemediationIndexCard({ item }: { readonly item: RemediationCase }) {
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

function RemediationCard({ item }: { readonly item: RemediationCase }) {
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

function EvidenceRequestCard({ request }: { readonly request: RemediationEvidenceRequest }) {
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

function ClosureGateCard({ gate }: { readonly gate: RemediationClosureGate }) {
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

function TimelineCard({ item }: { readonly item: RemediationTimelineItem }) {
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

function getRemediationStatusTone(status: RemediationCase["status"]) {
  if (status === "已关闭") {
    return "success";
  }

  if (status === "待验收" || status === "整改中") {
    return "info";
  }

  return "warning";
}

function getEvidenceStatusTone(status: RemediationEvidenceRequest["status"]) {
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

function getGateTone(status: RemediationClosureGate["status"]) {
  if (status === "通过") {
    return "success";
  }

  if (status === "阻断") {
    return "danger";
  }

  return "warning";
}

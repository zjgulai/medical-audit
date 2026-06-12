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
    <main className="grid gap-5 xl:grid-cols-[minmax(0,1fr)_22rem]">
      <section className="rounded-2xl border border-slate-200 bg-white p-6 shadow-[var(--audit-shadow-card)]">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div>
            <p className="text-sm font-semibold text-blue-700">补证整改</p>
            <h1 className="mt-2 text-3xl font-semibold text-slate-950">整改事项与补证闭环</h1>
            <p className="mt-2 max-w-3xl text-sm leading-6 text-slate-600">
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
            <h2 id="remediation-ledger-title" className="text-lg font-semibold text-slate-950">
              整改台账
            </h2>
            <a className="audit-focus-ring rounded-xl border border-blue-200 bg-white px-3 py-2 text-sm font-semibold text-blue-700 hover:bg-blue-50" href="/reports">
              查看报告来源
            </a>
          </div>

          <div className="mt-4 hidden overflow-hidden rounded-2xl border border-slate-200 md:block">
            <table className="w-full table-fixed text-left text-sm">
              <thead className="bg-slate-50 text-slate-500">
                <tr>
                  <th scope="col" className="w-[25%] px-4 py-3 font-semibold">
                    整改事项
                  </th>
                  <th scope="col" className="w-[12%] px-4 py-3 font-semibold">
                    状态
                  </th>
                  <th scope="col" className="w-[16%] px-4 py-3 font-semibold">
                    责任科室
                  </th>
                  <th scope="col" className="w-[18%] px-4 py-3 font-semibold">
                    来源
                  </th>
                  <th scope="col" className="w-[14%] px-4 py-3 font-semibold">
                    进度
                  </th>
                  <th scope="col" className="w-[15%] px-4 py-3 font-semibold">
                    操作
                  </th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-200">
                {remediationCases.map((item) => (
                  <RemediationRow key={item.id} item={item} />
                ))}
              </tbody>
            </table>
          </div>

          <div className="mt-4 grid gap-3 md:hidden">
            {remediationCases.map((item) => (
              <RemediationCard key={item.id} item={item} />
            ))}
          </div>
        </section>

        <section className="mt-6 grid gap-5 xl:grid-cols-[minmax(0,1fr)_20rem]" aria-labelledby="evidence-requests-title">
          <div>
            <h2 id="evidence-requests-title" className="text-lg font-semibold text-slate-950">
              补证请求
            </h2>
            <div className="mt-4 grid gap-3 lg:grid-cols-2">
              {remediationEvidenceRequests.map((request) => (
                <EvidenceRequestCard key={request.id} request={request} />
              ))}
            </div>
          </div>

          <aside className="rounded-2xl border border-blue-100 bg-blue-50 p-5">
            <p className="text-sm font-semibold text-blue-700">关闭规则</p>
            <h3 className="mt-2 text-lg font-semibold text-slate-950">验收前不得结案</h3>
            <p className="mt-2 text-sm leading-6 text-slate-600">
              整改说明、补证材料和负责人确认全部通过后，才能进入项目归档检查。
            </p>
          </aside>
        </section>
      </section>

      <aside className="space-y-4">
        <section className="rounded-2xl border border-slate-200 bg-white p-5 shadow-[var(--audit-shadow-card)]">
          <h2 className="text-lg font-semibold text-slate-950">关闭门禁</h2>
          <div className="mt-4 space-y-3">
            {remediationClosureGates.map((gate) => (
              <ClosureGateCard key={gate.id} gate={gate} />
            ))}
          </div>
        </section>

        <section className="rounded-2xl border border-slate-200 bg-white p-5 shadow-[var(--audit-shadow-card)]">
          <h2 className="text-lg font-semibold text-slate-950">整改动态</h2>
          <div className="mt-4 space-y-3">
            {remediationTimeline.map((item) => (
              <TimelineCard key={item.id} item={item} />
            ))}
          </div>
        </section>

        <a className="audit-focus-ring block rounded-2xl border border-slate-200 bg-white p-5 shadow-[var(--audit-shadow-card)]" href="/graph">
          <p className="text-sm font-semibold text-blue-700">知识图谱</p>
          <h2 className="mt-2 text-lg font-semibold text-slate-950">查看整改证据链</h2>
          <p className="mt-2 text-sm leading-6 text-slate-600">整改事项已经和报告、复核、疑点、项目归档关系连通。</p>
        </a>
      </aside>
    </main>
  );
}

function RemediationMetric({ label, value }: { readonly label: string; readonly value: string }) {
  return (
    <div className="rounded-2xl border border-slate-200 bg-slate-50 p-4">
      <p className="text-sm font-semibold text-slate-500">{label}</p>
      <p className="mt-2 text-2xl font-semibold text-slate-950">{value}</p>
    </div>
  );
}

function RemediationRow({ item }: { readonly item: RemediationCase }) {
  return (
    <tr>
      <td className="px-4 py-3">
        <p className="font-semibold text-slate-950">{item.title}</p>
        <p className="mt-1 text-xs text-slate-500">{item.nextAction}</p>
      </td>
      <td className="px-4 py-3">
        <StatusPill tone={getRemediationStatusTone(item.status)}>{item.status}</StatusPill>
      </td>
      <td className="px-4 py-3 text-slate-700">
        <p className="font-medium text-slate-900">{item.department}</p>
        <p className="mt-1 text-xs text-slate-500">责任方：{item.owner}</p>
      </td>
      <td className="px-4 py-3 text-slate-700">
        <p className="break-words font-medium text-slate-900">{item.reportNo}</p>
        <p className="mt-1 break-words text-xs text-slate-500">{item.sourceFinding}</p>
      </td>
      <td className="px-4 py-3 text-slate-700">
        <ProgressBar value={item.progress} />
        <p className="mt-2 text-xs text-slate-500">{item.evidenceStatus}</p>
      </td>
      <td className="px-4 py-3">
        <a className="audit-focus-ring inline-flex min-w-24 items-center justify-center rounded-xl bg-blue-600 px-3 py-2 text-sm font-semibold text-white hover:bg-blue-700" href={item.href}>
          查看详情
        </a>
      </td>
    </tr>
  );
}

function RemediationCard({ item }: { readonly item: RemediationCase }) {
  return (
    <article className="rounded-2xl border border-slate-200 bg-slate-50 p-4">
      <div className="flex items-start justify-between gap-3">
        <div>
          <h3 className="text-sm font-semibold leading-6 text-slate-950">{item.title}</h3>
          <p className="mt-1 text-xs text-slate-500">{item.reportNo}</p>
        </div>
        <StatusPill tone={getRemediationStatusTone(item.status)}>{item.status}</StatusPill>
      </div>
      <p className="mt-3 text-sm leading-6 text-slate-600">{item.nextAction}</p>
      <dl className="mt-4 grid grid-cols-2 gap-3 text-xs">
        <div>
          <dt className="font-semibold text-slate-500">责任科室</dt>
          <dd className="mt-1 text-slate-900">{item.department}</dd>
        </div>
        <div>
          <dt className="font-semibold text-slate-500">期限</dt>
          <dd className="mt-1 text-slate-900">{item.dueDate}</dd>
        </div>
        <div>
          <dt className="font-semibold text-slate-500">来源</dt>
          <dd className="mt-1 break-words text-slate-900">{item.sourceFinding}</dd>
        </div>
        <div>
          <dt className="font-semibold text-slate-500">补证</dt>
          <dd className="mt-1 text-slate-900">{item.evidenceStatus}</dd>
        </div>
      </dl>
      <div className="mt-4">
        <ProgressBar value={item.progress} />
      </div>
      <a className="audit-focus-ring mt-4 inline-flex w-full items-center justify-center rounded-xl bg-blue-600 px-3 py-2 text-sm font-semibold text-white hover:bg-blue-700" href={item.href}>
        查看详情
      </a>
    </article>
  );
}

function EvidenceRequestCard({ request }: { readonly request: RemediationEvidenceRequest }) {
  return (
    <article className="rounded-2xl border border-slate-200 bg-slate-50 p-4">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h3 className="text-base font-semibold text-slate-950">{request.title}</h3>
          <p className="mt-1 text-xs text-slate-500">
            {request.kind} · {request.owner} · {request.dueDate}
          </p>
        </div>
        <StatusPill tone={getEvidenceStatusTone(request.status)}>{request.status}</StatusPill>
      </div>
      <p className="mt-3 text-sm leading-6 text-slate-600">{request.detail}</p>
      <a className="audit-focus-ring mt-4 inline-flex rounded-xl border border-blue-200 bg-white px-3 py-2 text-sm font-semibold text-blue-700 hover:bg-blue-50" href={request.href}>
        查看材料
      </a>
    </article>
  );
}

function ClosureGateCard({ gate }: { readonly gate: RemediationClosureGate }) {
  return (
    <article className="rounded-xl border border-slate-200 bg-slate-50 p-3">
      <div className="flex items-start justify-between gap-3">
        <div>
          <h3 className="text-sm font-semibold text-slate-950">{gate.label}</h3>
          <p className="mt-1 text-xs text-slate-500">责任方：{gate.owner}</p>
        </div>
        <StatusPill tone={getGateTone(gate.status)}>{gate.status}</StatusPill>
      </div>
      <p className="mt-3 text-sm leading-6 text-slate-600">{gate.detail}</p>
    </article>
  );
}

function TimelineCard({ item }: { readonly item: RemediationTimelineItem }) {
  return (
    <article className="rounded-xl border border-slate-200 bg-slate-50 p-3">
      <div className="flex items-start justify-between gap-3">
        <div>
          <h3 className="text-sm font-semibold text-slate-950">{item.title}</h3>
          <p className="mt-1 text-xs text-slate-500">{item.time}</p>
        </div>
        <StatusPill tone={item.status === "已记录" ? "success" : item.status === "已阻断" ? "danger" : "warning"}>
          {item.status}
        </StatusPill>
      </div>
      <p className="mt-3 text-sm leading-6 text-slate-600">{item.detail}</p>
    </article>
  );
}

function ProgressBar({ value }: { readonly value: number }) {
  return (
    <div>
      <div className="flex items-center justify-between gap-2 text-xs">
        <span className="font-semibold text-slate-500">进度</span>
        <span className="font-semibold text-slate-950">{value}%</span>
      </div>
      <div className="mt-2 h-2 overflow-hidden rounded-full bg-slate-200">
        <div className={`h-full rounded-full bg-blue-600 ${getProgressWidthClass(value)}`} />
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

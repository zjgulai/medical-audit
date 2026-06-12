import { StatusPill } from "@/components/ui/status-pill";
import {
  archiveAuditRuns,
  archivePackages,
  archivePolicyItems,
  archiveSignatureItems,
  archiveTimeline
} from "@/lib/portal-data";
import type {
  ArchiveAuditRun,
  ArchivePackage,
  ArchivePolicyItem,
  ArchiveSignatureItem,
  ArchiveTimelineItem
} from "@/lib/portal-data";

const archivedPackageCount = archivePackages.filter((item) => item.status === "已归档").length;
const pendingPackageCount = archivePackages.filter((item) => item.status !== "已归档").length;
const blockedPackageCount = archivePackages.filter((item) => item.status === "材料阻断").length;
const latestArchiveRun = archiveAuditRuns[0];

export default function ArchivePage() {
  return (
    <main className="grid gap-5 xl:grid-cols-[minmax(0,1fr)_22rem]">
      <section className="min-w-0 rounded-2xl border border-slate-200 bg-white p-6 shadow-[var(--audit-shadow-card)]">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div>
            <p className="text-sm font-semibold text-blue-700">项目档案</p>
            <h1 className="mt-2 text-3xl font-semibold text-slate-950">项目档案与审计日志归档</h1>
            <p className="mt-2 max-w-3xl text-sm leading-6 text-slate-600">
              汇总项目档案包、审计日志归档、签名链和归档前阻断原因，保留到后台审计日志台的受控入口。
            </p>
          </div>
          <StatusPill tone="info">首期只读</StatusPill>
        </div>

        <div className="mt-6 grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
          <ArchiveMetric label="已归档项目" value={`${archivedPackageCount} 个`} />
          <ArchiveMetric label="待归档档案" value={`${pendingPackageCount} 个`} />
          <ArchiveMetric label="材料阻断" value={`${blockedPackageCount} 项`} />
          <ArchiveMetric label="巡检状态" value={latestArchiveRun.status} />
        </div>

        <section className="mt-6" aria-labelledby="archive-package-title">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div>
              <h2 id="archive-package-title" className="text-lg font-semibold text-slate-950">
                项目档案包
              </h2>
              <p className="mt-1 text-sm text-slate-500">归档前检查直接继承报告、整改和审计日志链路状态。</p>
            </div>
            <a className="audit-focus-ring rounded-xl border border-blue-200 bg-white px-3 py-2 text-sm font-semibold text-blue-700 hover:bg-blue-50" href="/pages/audit-logs">
              打开审计日志台
            </a>
          </div>

          <div className="mt-4 hidden overflow-hidden rounded-2xl border border-slate-200 md:block">
            <table className="w-full table-fixed text-left text-sm">
              <thead className="bg-slate-50 text-slate-500">
                <tr>
                  <th scope="col" className="w-[23%] px-4 py-3 font-semibold">
                    档案包
                  </th>
                  <th scope="col" className="w-[12%] px-4 py-3 font-semibold">
                    状态
                  </th>
                  <th scope="col" className="w-[17%] px-4 py-3 font-semibold">
                    报告/签发
                  </th>
                  <th scope="col" className="w-[23%] px-4 py-3 font-semibold">
                    范围与校验
                  </th>
                  <th scope="col" className="w-[10%] px-4 py-3 font-semibold">
                    留存
                  </th>
                  <th scope="col" className="w-[15%] px-4 py-3 font-semibold">
                    操作
                  </th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-200">
                {archivePackages.map((item) => (
                  <ArchivePackageRow key={item.id} item={item} />
                ))}
              </tbody>
            </table>
          </div>

          <div className="mt-4 grid gap-3 md:hidden">
            {archivePackages.map((item) => (
              <ArchivePackageCard key={item.id} item={item} />
            ))}
          </div>
        </section>

        <section className="mt-6 grid gap-5 xl:grid-cols-[minmax(0,1fr)_20rem]" aria-labelledby="archive-policy-title">
          <div>
            <h2 id="archive-policy-title" className="text-lg font-semibold text-slate-950">
              审计日志治理策略
            </h2>
            <div className="mt-4 grid gap-3 lg:grid-cols-2">
              {archivePolicyItems.map((item) => (
                <ArchivePolicyCard key={item.id} item={item} />
              ))}
            </div>
          </div>

          <aside className="rounded-2xl border border-blue-100 bg-blue-50 p-5">
            <p className="text-sm font-semibold text-blue-700">受控导出</p>
            <h3 className="mt-2 text-lg font-semibold text-slate-950">审计日志不进入普通检索</h3>
            <p className="mt-2 text-sm leading-6 text-slate-600">
              原始日志归档作为受控证据保存，查询和导出必须经过审计日志权限校验。
            </p>
            <a className="audit-focus-ring mt-4 inline-flex rounded-xl border border-blue-200 bg-white px-3 py-2 text-sm font-semibold text-blue-700 hover:bg-blue-50" href="/audit/logs/export">
              导出日志 JSON
            </a>
          </aside>
        </section>
      </section>

      <aside className="min-w-0 space-y-4">
        <section className="rounded-2xl border border-slate-200 bg-white p-5 shadow-[var(--audit-shadow-card)]">
          <h2 className="text-lg font-semibold text-slate-950">归档巡检</h2>
          <div className="mt-4 space-y-3">
            {archiveAuditRuns.map((item) => (
              <ArchiveAuditRunCard key={item.id} item={item} />
            ))}
          </div>
        </section>

        <section className="rounded-2xl border border-slate-200 bg-white p-5 shadow-[var(--audit-shadow-card)]">
          <h2 className="text-lg font-semibold text-slate-950">签名链</h2>
          <div className="mt-4 space-y-3">
            {archiveSignatureItems.map((item) => (
              <ArchiveSignatureCard key={item.id} item={item} />
            ))}
          </div>
        </section>

        <section className="rounded-2xl border border-slate-200 bg-white p-5 shadow-[var(--audit-shadow-card)]">
          <h2 className="text-lg font-semibold text-slate-950">入档动态</h2>
          <div className="mt-4 space-y-3">
            {archiveTimeline.map((item) => (
              <ArchiveTimelineCard key={item.id} item={item} />
            ))}
          </div>
        </section>
      </aside>
    </main>
  );
}

function ArchiveMetric({ label, value }: { readonly label: string; readonly value: string }) {
  return (
    <div className="rounded-2xl border border-slate-200 bg-slate-50 p-4">
      <p className="text-sm font-semibold text-slate-500">{label}</p>
      <p className="mt-2 text-2xl font-semibold text-slate-950">{value}</p>
    </div>
  );
}

function ArchivePackageRow({ item }: { readonly item: ArchivePackage }) {
  return (
    <tr>
      <td className="px-4 py-3">
        <p className="font-semibold text-slate-950">{item.projectName}</p>
        <p className="mt-1 break-words text-xs text-slate-500">{item.archiveNo}</p>
      </td>
      <td className="px-4 py-3">
        <StatusPill tone={getArchivePackageTone(item.status)}>{item.status}</StatusPill>
      </td>
      <td className="px-4 py-3 text-slate-700">
        <p className="break-words font-medium text-slate-900">{item.reportNo}</p>
        <p className="mt-1 text-xs text-slate-500">签发：{item.signedAt}</p>
      </td>
      <td className="px-4 py-3 text-slate-700">
        <p className="leading-6 text-slate-900">{item.archiveScope}</p>
        <p className="mt-1 leading-5 text-slate-500">{item.evidenceSummary}</p>
      </td>
      <td className="px-4 py-3 text-slate-700">{item.retainedUntil}</td>
      <td className="px-4 py-3">
        <div className="grid gap-2">
          <a className="audit-focus-ring inline-flex justify-center whitespace-nowrap rounded-xl bg-blue-600 px-3 py-2 text-sm font-semibold text-white hover:bg-blue-700" href={item.href}>
            查看档案
          </a>
          <a className="audit-focus-ring inline-flex justify-center whitespace-nowrap rounded-xl border border-blue-200 bg-white px-3 py-2 text-sm font-semibold text-blue-700 hover:bg-blue-50" href={item.logHref}>
            查看日志
          </a>
        </div>
      </td>
    </tr>
  );
}

function ArchivePackageCard({ item }: { readonly item: ArchivePackage }) {
  return (
    <article className="rounded-2xl border border-slate-200 bg-slate-50 p-4">
      <div className="flex items-start justify-between gap-3">
        <div>
          <h3 className="text-sm font-semibold leading-6 text-slate-950">{item.projectName}</h3>
          <p className="mt-1 break-words text-xs text-slate-500">{item.archiveNo}</p>
        </div>
        <StatusPill tone={getArchivePackageTone(item.status)}>{item.status}</StatusPill>
      </div>
      <p className="mt-3 text-sm leading-6 text-slate-600">{item.archiveScope}</p>
      <dl className="mt-4 grid grid-cols-2 gap-3 text-xs">
        <div>
          <dt className="font-semibold text-slate-500">报告</dt>
          <dd className="mt-1 break-words text-slate-900">{item.reportNo}</dd>
        </div>
        <div>
          <dt className="font-semibold text-slate-500">签发</dt>
          <dd className="mt-1 text-slate-900">{item.signedAt}</dd>
        </div>
        <div>
          <dt className="font-semibold text-slate-500">责任方</dt>
          <dd className="mt-1 text-slate-900">{item.owner}</dd>
        </div>
        <div>
          <dt className="font-semibold text-slate-500">留存</dt>
          <dd className="mt-1 text-slate-900">{item.retainedUntil}</dd>
        </div>
      </dl>
      <p className="mt-3 text-sm leading-6 text-slate-600">{item.evidenceSummary}</p>
      <div className="mt-4 grid grid-cols-2 gap-2">
        <a className="audit-focus-ring inline-flex justify-center rounded-xl bg-blue-600 px-3 py-2 text-sm font-semibold text-white hover:bg-blue-700" href={item.href}>
          查看档案
        </a>
        <a className="audit-focus-ring inline-flex justify-center rounded-xl border border-blue-200 bg-white px-3 py-2 text-sm font-semibold text-blue-700 hover:bg-blue-50" href={item.logHref}>
          查看日志
        </a>
      </div>
    </article>
  );
}

function ArchivePolicyCard({ item }: { readonly item: ArchivePolicyItem }) {
  return (
    <article className="rounded-2xl border border-slate-200 bg-slate-50 p-4">
      <p className="text-xs font-semibold text-slate-500">{item.label}</p>
      <h3 className="mt-2 break-words text-base font-semibold text-slate-950">{item.value}</h3>
      <p className="mt-2 text-sm leading-6 text-slate-600">{item.detail}</p>
    </article>
  );
}

function ArchiveAuditRunCard({ item }: { readonly item: ArchiveAuditRun }) {
  return (
    <article className="rounded-xl border border-slate-200 bg-slate-50 p-3">
      <div className="flex items-start justify-between gap-3">
        <div>
          <h3 className="text-sm font-semibold text-slate-950">{item.title}</h3>
          <p className="mt-1 text-xs text-slate-500">{item.time}</p>
        </div>
        <StatusPill tone={getArchiveRunTone(item.status)}>{item.status}</StatusPill>
      </div>
      <dl className="mt-3 grid grid-cols-2 gap-2 text-xs text-slate-600">
        <div>
          <dt className="font-semibold text-slate-500">manifest</dt>
          <dd className="mt-1 text-slate-900">{item.manifestCount}</dd>
        </div>
        <div>
          <dt className="font-semibold text-slate-500">failed</dt>
          <dd className="mt-1 text-slate-900">{item.failedCount}</dd>
        </div>
      </dl>
      <p className="mt-3 break-words text-xs text-slate-500">{item.archiveRoot}</p>
      <p className="mt-2 text-sm leading-6 text-slate-600">{item.detail}</p>
    </article>
  );
}

function ArchiveSignatureCard({ item }: { readonly item: ArchiveSignatureItem }) {
  return (
    <article className="rounded-xl border border-slate-200 bg-slate-50 p-3">
      <div className="flex items-start justify-between gap-3">
        <h3 className="break-words text-sm font-semibold text-slate-950">{item.label}</h3>
        <StatusPill tone={getSignatureTone(item.status)}>{item.status}</StatusPill>
      </div>
      <p className="mt-2 break-words font-mono text-xs text-slate-500">{item.sha256}</p>
      <p className="mt-3 text-sm leading-6 text-slate-600">{item.detail}</p>
    </article>
  );
}

function ArchiveTimelineCard({ item }: { readonly item: ArchiveTimelineItem }) {
  return (
    <article className="rounded-xl border border-slate-200 bg-slate-50 p-3">
      <div className="flex items-start justify-between gap-3">
        <div>
          <h3 className="text-sm font-semibold text-slate-950">{item.title}</h3>
          <p className="mt-1 text-xs text-slate-500">{item.time}</p>
        </div>
        <StatusPill tone={item.status === "待补证" ? "warning" : "success"}>{item.status}</StatusPill>
      </div>
      <p className="mt-3 text-sm leading-6 text-slate-600">{item.detail}</p>
    </article>
  );
}

function getArchivePackageTone(status: ArchivePackage["status"]) {
  if (status === "已归档") {
    return "success";
  }

  if (status === "材料阻断") {
    return "danger";
  }

  if (status === "归档前检查") {
    return "info";
  }

  return "warning";
}

function getArchiveRunTone(status: ArchiveAuditRun["status"]) {
  if (status === "通过") {
    return "success";
  }

  if (status === "阻断") {
    return "danger";
  }

  return "warning";
}

function getSignatureTone(status: ArchiveSignatureItem["status"]) {
  if (status === "验签通过") {
    return "success";
  }

  if (status === "已生成") {
    return "info";
  }

  return "warning";
}

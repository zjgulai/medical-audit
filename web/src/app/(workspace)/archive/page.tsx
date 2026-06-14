import { SearchBackendStatusPill } from "@/components/portal/search-backend-status-pill";
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
    <main className="grid min-w-0 items-start gap-4 xl:grid-cols-[17rem_minmax(0,1fr)_18rem]">
      <aside className="audit-panel-rail min-w-0 p-5">
        <h2 className="audit-section-title">档案包索引</h2>
        <p className="audit-copy mt-2">归档前检查继承报告、整改、日志和签名链状态。</p>
        <div className="mt-3">
          <SearchBackendStatusPill />
        </div>
        <div className="mt-5 space-y-3">
          {archivePackages.map((item) => (
            <ArchiveIndexCard key={item.id} item={item} />
          ))}
        </div>
      </aside>

      <section className="audit-panel min-w-0 p-6">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div>
            <p className="audit-kicker">项目档案</p>
            <h1 className="audit-page-title">项目档案与审计日志归档</h1>
            <p className="audit-copy mt-2 max-w-3xl">
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
              <h2 id="archive-package-title" className="audit-section-title">
                项目档案包
              </h2>
              <p className="audit-copy mt-1">归档前检查直接继承报告、整改和审计日志链路状态。</p>
            </div>
            <a className="audit-focus-ring audit-btn audit-btn-secondary" href="/pages/audit-logs">
              打开审计日志台
            </a>
          </div>

          <div className="mt-4 grid gap-3">
            {archivePackages.map((item) => (
              <ArchivePackageCard key={item.id} item={item} />
            ))}
          </div>
        </section>

        <section className="mt-6 grid gap-5" aria-labelledby="archive-policy-title">
          <div>
            <h2 id="archive-policy-title" className="audit-section-title">
              审计日志治理策略
            </h2>
            <div className="mt-4 grid gap-3">
              {archivePolicyItems.map((item) => (
                <ArchivePolicyCard key={item.id} item={item} />
              ))}
            </div>
          </div>

          <aside className="audit-callout p-5">
            <p className="audit-kicker">受控导出</p>
            <h3 className="audit-section-title mt-2">审计日志不进入普通检索</h3>
            <p className="audit-copy mt-2">
              原始日志归档作为受控证据保存，查询和导出必须经过审计日志权限校验。
            </p>
            <a className="audit-focus-ring audit-btn audit-btn-secondary mt-4" href="/audit/logs/export">
              导出日志 JSON
            </a>
          </aside>
        </section>
      </section>

      <aside className="min-w-0 space-y-4">
        <section className="audit-panel-rail p-5">
          <h2 className="audit-section-title">归档巡检</h2>
          <div className="mt-4 space-y-3">
            {archiveAuditRuns.map((item) => (
              <ArchiveAuditRunCard key={item.id} item={item} />
            ))}
          </div>
        </section>

        <section className="audit-panel-rail p-5">
          <h2 className="audit-section-title">签名链</h2>
          <div className="mt-4 space-y-3">
            {archiveSignatureItems.map((item) => (
              <ArchiveSignatureCard key={item.id} item={item} />
            ))}
          </div>
        </section>

        <section className="audit-panel-rail p-5">
          <h2 className="audit-section-title">入档动态</h2>
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

function ArchiveIndexCard({ item }: { readonly item: ArchivePackage }) {
  return (
    <a className="audit-focus-ring block rounded-[var(--audit-radius-md)] border border-[var(--audit-line)] bg-white p-3 hover:bg-[var(--audit-primary-soft)]" href={item.href}>
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <h3 className="truncate text-sm font-semibold text-[var(--audit-ink)]">{item.projectName}</h3>
          <p className="audit-meta mt-1 break-words">{item.reportNo}</p>
        </div>
        <StatusPill tone={getArchivePackageTone(item.status)}>{item.status}</StatusPill>
      </div>
      <p className="audit-meta mt-3">留存至 {item.retainedUntil}</p>
    </a>
  );
}

function ArchiveMetric({ label, value }: { readonly label: string; readonly value: string }) {
  return (
    <div className="audit-panel-muted p-4">
      <p className="audit-label">{label}</p>
      <p className="audit-metric-value mt-2">{value}</p>
    </div>
  );
}

function ArchivePackageCard({ item }: { readonly item: ArchivePackage }) {
  return (
    <article className="audit-panel-muted p-4">
      <div className="flex items-start justify-between gap-3">
        <div>
          <h3 className="audit-compact-title">{item.projectName}</h3>
          <p className="audit-meta mt-1 break-words">{item.archiveNo}</p>
        </div>
        <StatusPill tone={getArchivePackageTone(item.status)}>{item.status}</StatusPill>
      </div>
      <p className="audit-copy mt-3">{item.archiveScope}</p>
      <dl className="audit-meta mt-4 grid grid-cols-2 gap-3">
        <div>
          <dt className="font-semibold">报告</dt>
          <dd className="mt-1 break-words text-[var(--audit-ink)]">{item.reportNo}</dd>
        </div>
        <div>
          <dt className="font-semibold">签发</dt>
          <dd className="mt-1 text-[var(--audit-ink)]">{item.signedAt}</dd>
        </div>
        <div>
          <dt className="font-semibold">责任方</dt>
          <dd className="mt-1 text-[var(--audit-ink)]">{item.owner}</dd>
        </div>
        <div>
          <dt className="font-semibold">留存</dt>
          <dd className="mt-1 text-[var(--audit-ink)]">{item.retainedUntil}</dd>
        </div>
      </dl>
      <p className="audit-copy mt-3">{item.evidenceSummary}</p>
      <div className="mt-4 grid grid-cols-2 gap-2">
        <a className="audit-focus-ring audit-btn audit-btn-primary" href={item.href}>
          查看档案
        </a>
        <a className="audit-focus-ring audit-btn audit-btn-secondary" href={item.logHref}>
          查看日志
        </a>
      </div>
    </article>
  );
}

function ArchivePolicyCard({ item }: { readonly item: ArchivePolicyItem }) {
  return (
    <article className="audit-panel-muted p-4">
      <p className="audit-meta font-semibold">{item.label}</p>
      <h3 className="audit-card-title mt-2 break-words">{item.value}</h3>
      <p className="audit-copy mt-2">{item.detail}</p>
    </article>
  );
}

function ArchiveAuditRunCard({ item }: { readonly item: ArchiveAuditRun }) {
  return (
    <article className="rounded-[var(--audit-radius-md)] border border-[var(--audit-line)] bg-[var(--audit-surface-muted)] p-3">
      <div className="flex items-start justify-between gap-3">
        <div>
          <h3 className="audit-compact-title">{item.title}</h3>
          <p className="audit-meta mt-1">{item.time}</p>
        </div>
        <StatusPill tone={getArchiveRunTone(item.status)}>{item.status}</StatusPill>
      </div>
      <dl className="audit-meta mt-3 grid grid-cols-2 gap-2">
        <div>
          <dt className="font-semibold">manifest</dt>
          <dd className="mt-1 text-[var(--audit-ink)]">{item.manifestCount}</dd>
        </div>
        <div>
          <dt className="font-semibold">failed</dt>
          <dd className="mt-1 text-[var(--audit-ink)]">{item.failedCount}</dd>
        </div>
      </dl>
      <p className="audit-meta mt-3 break-words">{item.archiveRoot}</p>
      <p className="audit-copy mt-2">{item.detail}</p>
    </article>
  );
}

function ArchiveSignatureCard({ item }: { readonly item: ArchiveSignatureItem }) {
  return (
    <article className="rounded-[var(--audit-radius-md)] border border-[var(--audit-line)] bg-[var(--audit-surface-muted)] p-3">
      <div className="flex items-start justify-between gap-3">
        <h3 className="audit-compact-title break-words">{item.label}</h3>
        <StatusPill tone={getSignatureTone(item.status)}>{item.status}</StatusPill>
      </div>
      <p className="audit-meta mt-2 break-words font-mono">{item.sha256}</p>
      <p className="audit-copy mt-3">{item.detail}</p>
    </article>
  );
}

function ArchiveTimelineCard({ item }: { readonly item: ArchiveTimelineItem }) {
  return (
    <article className="rounded-[var(--audit-radius-md)] border border-[var(--audit-line)] bg-[var(--audit-surface-muted)] p-3">
      <div className="flex items-start justify-between gap-3">
        <div>
          <h3 className="audit-compact-title">{item.title}</h3>
          <p className="audit-meta mt-1">{item.time}</p>
        </div>
        <StatusPill tone={item.status === "待补证" ? "warning" : "success"}>{item.status}</StatusPill>
      </div>
      <p className="audit-copy mt-3">{item.detail}</p>
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

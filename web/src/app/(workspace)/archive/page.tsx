"use client";

import { useEffect, useState } from "react";

import { SearchBackendStatusPill } from "@/components/portal/search-backend-status-pill";
import { buildReplicaLocalGateNotice } from "@/components/replica/replica-page-kit";
import { StatusPill } from "@/components/ui/status-pill";
import { fetchArchiveWorkbench } from "@/lib/api-client";
import type {
  ArchiveAuditRunApiItem,
  ArchivePackageApiItem,
  ArchivePolicyItemApiItem,
  ArchiveSignatureItemApiItem,
  ArchiveTimelineApiItem,
  ArchiveWorkbenchResponse
} from "@/lib/api-types";
import {
  archiveAuditRuns,
  archivePackages,
  archivePolicyItems,
  archiveSignatureItems,
  archiveTimeline
} from "@/lib/portal-data";

const archivePolicyHref = "#archive-policy-title";
const backendAuditLogsPath = "/pages/audit-logs";

type ArchiveAction = "查看档案" | "查看留痕" | "导出清单" | "移交归档";

const staticArchiveWorkbench: ArchiveWorkbenchResponse = {
  format: "archive-workbench-v1",
  generated_at: "static-fallback",
  archive_id: "FUND-USAGE-ARCHIVE",
  archive_title: "项目档案与审计日志归档",
  archive_scope: "汇总项目档案包、审计日志归档、签名链和归档前阻断原因，首期只读展示归档状态和受控导出入口。",
  archive_packages: archivePackages,
  audit_runs: archiveAuditRuns,
  signature_items: archiveSignatureItems,
  policy_items: archivePolicyItems,
  timeline: archiveTimeline,
  metrics: buildArchiveMetrics(
    archivePackages,
    archiveAuditRuns,
    archiveSignatureItems,
    archivePolicyItems,
    archiveTimeline
  ),
  evidence_grade: "static-fallback",
  production_side_effect: "none",
  store: { ready: false, backend: "portal-data-static-fallback" }
};

export default function ArchivePage() {
  const [workbench, setWorkbench] = useState<ArchiveWorkbenchResponse>(staticArchiveWorkbench);
  const [backendStatus, setBackendStatus] = useState<"loading" | "ready" | "fallback">("loading");
  const [selectedPackageId, setSelectedPackageId] = useState(workbench.archive_packages[0]?.id ?? "");
  const [packageDetailOpen, setPackageDetailOpen] = useState(false);
  const [activeArchiveAction, setActiveArchiveAction] = useState<ArchiveAction | null>(null);
  const [archiveNotice, setArchiveNotice] = useState("");

  useEffect(() => {
    let active = true;

    fetchArchiveWorkbench()
      .then((response) => {
        if (!active) {
          return;
        }
        setWorkbench(normalizeArchiveWorkbench(response));
        setBackendStatus("ready");
      })
      .catch(() => {
        if (!active) {
          return;
        }
        setWorkbench(staticArchiveWorkbench);
        setBackendStatus("fallback");
      });

    return () => {
      active = false;
    };
  }, []);

  useEffect(() => {
    if (workbench.archive_packages.length === 0) {
      setSelectedPackageId("");
      setPackageDetailOpen(false);
      return;
    }

    if (!workbench.archive_packages.some((item) => item.id === selectedPackageId)) {
      setSelectedPackageId(workbench.archive_packages[0]?.id ?? "");
    }
  }, [selectedPackageId, workbench.archive_packages]);

  const statusTone = backendStatus === "ready" ? "success" : backendStatus === "loading" ? "info" : "warning";
  const statusLabel =
    backendStatus === "ready" ? "数据已同步" : backendStatus === "loading" ? "同步中" : "演示数据";
  const selectedPackage =
    workbench.archive_packages.find((item) => item.id === selectedPackageId) ?? workbench.archive_packages[0];

  function runArchiveAction(item: ArchivePackageApiItem, action: ArchiveAction) {
    setSelectedPackageId(item.id);
    setPackageDetailOpen(true);
    setActiveArchiveAction(action);
    setArchiveNotice(buildReplicaLocalGateNotice({
      action: `${action}「${item.projectName}」`,
      nextStep: getArchiveActionNextStep(action)
    }));
  }

  return (
    <main className="space-y-5">
      <section className="audit-panel p-6">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div className="min-w-0">
            <p className="audit-kicker">项目档案</p>
            <h1 className="audit-page-title">{workbench.archive_title}</h1>
          </div>
          <div className="flex flex-wrap items-center gap-2">
            <SearchBackendStatusPill />
            <StatusPill tone={statusTone}>{statusLabel}</StatusPill>
          </div>
        </div>
        {backendStatus === "fallback" ? (
          <p className="audit-meta mt-4">当前展示演示归档包，用于核对材料完整性、签名链和归档策略。</p>
        ) : null}

        <div className="mt-5 grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
          <ArchiveMetric label="已归档项目" value={`${workbench.metrics.archived_package_count} 个`} />
          <ArchiveMetric label="待归档档案" value={`${workbench.metrics.pending_package_count} 个`} />
          <ArchiveMetric label="材料阻断" value={`${workbench.metrics.blocked_package_count} 项`} />
          <ArchiveMetric label="巡检状态" value={workbench.metrics.latest_archive_run_status} />
        </div>
      </section>

      <section className="audit-panel p-6" aria-labelledby="archive-package-title">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <h2 id="archive-package-title" className="audit-section-title">项目档案包</h2>
          <a className="audit-focus-ring audit-btn audit-btn-secondary" href={archivePolicyHref}>查看归档策略</a>
        </div>
        <div className="mt-4 grid gap-3 xl:grid-cols-2">
          {workbench.archive_packages.map((item) => (
            <ArchivePackageCard
              key={item.id}
              item={item}
              selected={selectedPackageId === item.id}
              onAction={runArchiveAction}
            />
          ))}
        </div>
        {archiveNotice ? (
          <p className="archive-local-notice" role="status">{archiveNotice}</p>
        ) : null}
        {packageDetailOpen && selectedPackage ? (
          <section className="archive-package-detail" aria-label="档案包详情预览">
            <div className="flex flex-wrap items-start justify-between gap-3">
              <div className="min-w-0">
                <p className="audit-kicker">档案包详情</p>
                <h3 className="audit-section-title break-words">{selectedPackage.projectName}</h3>
                <p className="audit-meta mt-1 break-words">{selectedPackage.archiveNo}</p>
              </div>
              <button
                type="button"
                className="audit-focus-ring audit-btn audit-btn-secondary"
                aria-label="关闭档案包详情"
                onClick={() => setPackageDetailOpen(false)}
              >
                关闭
              </button>
            </div>
            <dl className="mt-4 grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
              <div className="min-w-0">
                <dt className="audit-label">报告编号</dt>
                <dd className="audit-copy mt-1 break-words">{selectedPackage.reportNo}</dd>
              </div>
              <div className="min-w-0">
                <dt className="audit-label">责任方</dt>
                <dd className="audit-copy mt-1 break-words">{selectedPackage.owner}</dd>
              </div>
              <div className="min-w-0">
                <dt className="audit-label">签发时间</dt>
                <dd className="audit-copy mt-1">{selectedPackage.signedAt}</dd>
              </div>
              <div className="min-w-0">
                <dt className="audit-label">留存期限</dt>
                <dd className="audit-copy mt-1">{selectedPackage.retainedUntil}</dd>
              </div>
            </dl>
            <p className="audit-copy mt-4">{getArchiveActionPreview(selectedPackage, activeArchiveAction)}</p>
            <div className="archive-action-panel" aria-label="档案包后续操作预览">
              <button type="button" className="audit-focus-ring audit-btn audit-btn-primary" onClick={() => runArchiveAction(selectedPackage, "查看档案")}>
                查看档案
              </button>
              <button type="button" className="audit-focus-ring audit-btn audit-btn-secondary" onClick={() => runArchiveAction(selectedPackage, "查看留痕")}>
                查看留痕
              </button>
              <button type="button" className="audit-focus-ring audit-btn audit-btn-secondary" onClick={() => runArchiveAction(selectedPackage, "导出清单")}>
                导出清单
              </button>
              <button type="button" className="audit-focus-ring audit-btn audit-btn-secondary" onClick={() => runArchiveAction(selectedPackage, "移交归档")}>
                移交归档
              </button>
            </div>
          </section>
        ) : null}
      </section>

      <section className="audit-panel p-6" aria-labelledby="archive-policy-title">
        <h2 id="archive-policy-title" className="audit-section-title">审计日志治理策略</h2>
        <div className="mt-4 grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
          {workbench.policy_items.map((item) => (
            <ArchivePolicyCard key={item.id} item={item} />
          ))}
        </div>
      </section>

      <div className="grid gap-5 xl:grid-cols-3">
        <section className="audit-panel p-6">
          <h2 className="audit-section-title">归档巡检</h2>
          <div className="mt-4 grid gap-3">
            {workbench.audit_runs.map((item) => (
              <ArchiveAuditRunCard key={item.id} item={item} />
            ))}
          </div>
        </section>
        <section className="audit-panel p-6">
          <h2 className="audit-section-title">签名链</h2>
          <div className="mt-4 grid gap-3">
            {workbench.signature_items.map((item) => (
              <ArchiveSignatureCard key={item.id} item={item} />
            ))}
          </div>
        </section>
        <section className="audit-panel p-6">
          <h2 className="audit-section-title">入档动态</h2>
          <div className="mt-4 grid gap-3">
            {workbench.timeline.map((item) => (
              <ArchiveTimelineCard key={item.id} item={item} />
            ))}
          </div>
        </section>
      </div>
    </main>
  );
}

function ArchiveMetric({ label, value }: { readonly label: string; readonly value: string }) {
  return (
    <div className="audit-panel-muted min-w-0 p-4">
      <p className="audit-label">{label}</p>
      <p className="audit-metric-value mt-2">{value}</p>
    </div>
  );
}

function ArchivePackageCard({
  item,
  selected,
  onAction
}: {
  readonly item: ArchivePackageApiItem;
  readonly selected: boolean;
  readonly onAction: (item: ArchivePackageApiItem, action: ArchiveAction) => void;
}) {
  return (
    <article className={`audit-panel-muted min-w-0 p-4 ${selected ? "archive-package-card-active" : ""}`}>
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <h3 className="audit-compact-title break-words">{item.projectName}</h3>
          <p className="audit-meta mt-1 break-words">{item.archiveNo}</p>
        </div>
        <StatusPill tone={getArchivePackageTone(item.status)}>{item.status}</StatusPill>
      </div>
      <p className="audit-copy mt-3">{item.archiveScope}</p>
      <dl className="audit-meta mt-4 grid gap-3 sm:grid-cols-2">
        <div className="min-w-0">
          <dt className="font-semibold">报告</dt>
          <dd className="mt-1 break-words text-[var(--audit-ink)]">{item.reportNo}</dd>
        </div>
        <div className="min-w-0">
          <dt className="font-semibold">签发</dt>
          <dd className="mt-1 text-[var(--audit-ink)]">{item.signedAt}</dd>
        </div>
        <div className="min-w-0">
          <dt className="font-semibold">责任方</dt>
          <dd className="mt-1 break-words text-[var(--audit-ink)]">{item.owner}</dd>
        </div>
        <div className="min-w-0">
          <dt className="font-semibold">留存</dt>
          <dd className="mt-1 text-[var(--audit-ink)]">{item.retainedUntil}</dd>
        </div>
      </dl>
      <p className="audit-copy mt-3">{item.evidenceSummary}</p>
      <div className="mt-4 grid gap-2 sm:grid-cols-2">
        <button type="button" className="audit-focus-ring audit-btn audit-btn-primary" onClick={() => onAction(item, "查看档案")}>
          查看档案
        </button>
        <button type="button" className="audit-focus-ring audit-btn audit-btn-secondary" onClick={() => onAction(item, "查看留痕")}>
          查看留痕
        </button>
      </div>
    </article>
  );
}

function normalizeArchiveWorkbench(response: ArchiveWorkbenchResponse): ArchiveWorkbenchResponse {
  return {
    ...response,
    archive_packages: response.archive_packages.map((item) => ({
      ...item,
      logHref: safeArchiveLogHref(item.logHref)
    }))
  };
}

function safeArchiveLogHref(href: string | null | undefined): string {
  if (!href || href === `/archive${archivePolicyHref}` || href.startsWith(backendAuditLogsPath)) {
    return archivePolicyHref;
  }
  return href;
}

function ArchivePolicyCard({ item }: { readonly item: ArchivePolicyItemApiItem }) {
  return (
    <article className="audit-panel-muted min-w-0 p-4">
      <p className="audit-meta font-semibold">{item.label}</p>
      <h3 className="audit-card-title mt-2 break-words">{item.value}</h3>
      <p className="audit-copy mt-2">{item.detail}</p>
    </article>
  );
}

function ArchiveAuditRunCard({ item }: { readonly item: ArchiveAuditRunApiItem }) {
  return (
    <article className="min-w-0 rounded-[var(--audit-radius-md)] border border-[var(--audit-line)] bg-[var(--audit-surface-muted)] p-3">
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <h3 className="audit-compact-title break-words">{item.title}</h3>
          <p className="audit-meta mt-1">{item.time}</p>
        </div>
        <StatusPill tone={getArchiveRunTone(item.status)}>{item.status}</StatusPill>
      </div>
      <dl className="audit-meta mt-3 grid gap-2 sm:grid-cols-2">
        <div className="min-w-0">
          <dt className="font-semibold">manifest</dt>
          <dd className="mt-1 text-[var(--audit-ink)]">{item.manifestCount}</dd>
        </div>
        <div className="min-w-0">
          <dt className="font-semibold">failed</dt>
          <dd className="mt-1 text-[var(--audit-ink)]">{item.failedCount}</dd>
        </div>
      </dl>
      <p className="audit-meta mt-3 break-words">{item.archiveRoot}</p>
      <p className="audit-copy mt-2">{item.detail}</p>
    </article>
  );
}

function ArchiveSignatureCard({ item }: { readonly item: ArchiveSignatureItemApiItem }) {
  return (
    <article className="min-w-0 rounded-[var(--audit-radius-md)] border border-[var(--audit-line)] bg-[var(--audit-surface-muted)] p-3">
      <div className="flex items-start justify-between gap-3">
        <h3 className="audit-compact-title min-w-0 break-words">{item.label}</h3>
        <StatusPill tone={getSignatureTone(item.status)}>{item.status}</StatusPill>
      </div>
      <p className="audit-meta mt-2 break-all font-mono">{item.sha256}</p>
      <p className="audit-copy mt-3">{item.detail}</p>
    </article>
  );
}

function ArchiveTimelineCard({ item }: { readonly item: ArchiveTimelineApiItem }) {
  return (
    <article className="min-w-0 rounded-[var(--audit-radius-md)] border border-[var(--audit-line)] bg-[var(--audit-surface-muted)] p-3">
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <h3 className="audit-compact-title break-words">{item.title}</h3>
          <p className="audit-meta mt-1">{item.time}</p>
        </div>
        <StatusPill tone={item.status === "待补证" ? "warning" : "success"}>{item.status}</StatusPill>
      </div>
      <p className="audit-copy mt-3">{item.detail}</p>
    </article>
  );
}

function getArchivePackageTone(status: ArchivePackageApiItem["status"]) {
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

function getArchiveRunTone(status: ArchiveAuditRunApiItem["status"]) {
  if (status === "通过") {
    return "success";
  }

  if (status === "阻断") {
    return "danger";
  }

  return "warning";
}

function getSignatureTone(status: ArchiveSignatureItemApiItem["status"]) {
  if (status === "验签通过") {
    return "success";
  }

  if (status === "已生成") {
    return "info";
  }

  return "warning";
}

function getArchiveActionNextStep(action: ArchiveAction) {
  if (action === "查看档案") {
    return "档案包详情 API";
  }

  if (action === "查看留痕") {
    return "审计日志检索 API";
  }

  if (action === "导出清单") {
    return "受控导出 API";
  }

  return "归档移交 API";
}

function getArchiveActionPreview(item: ArchivePackageApiItem, action: ArchiveAction | null) {
  if (action === "查看留痕") {
    return `已打开「${item.projectName}」留痕预览，正式环境需读取审计日志、签名链和访问记录。`;
  }

  if (action === "导出清单") {
    return `已生成「${item.archiveNo}」清单导出确认态，正式环境需完成权限校验和下载留痕。`;
  }

  if (action === "移交归档") {
    return `已进入「${item.projectName}」移交前检查态，正式环境需复核报告、附件 hash、签名链和保留策略。`;
  }

  return `已打开「${item.projectName}」档案包预览，正式环境需加载文件目录、报告附件和证据摘要。`;
}

function buildArchiveMetrics(
  packages: readonly ArchivePackageApiItem[],
  auditRuns: readonly ArchiveAuditRunApiItem[],
  signatureItems: readonly ArchiveSignatureItemApiItem[],
  policyItems: readonly ArchivePolicyItemApiItem[],
  timeline: readonly ArchiveTimelineApiItem[]
): ArchiveWorkbenchResponse["metrics"] {
  return {
    package_count: packages.length,
    archived_package_count: packages.filter((item) => item.status === "已归档").length,
    pending_package_count: packages.filter((item) => item.status !== "已归档").length,
    blocked_package_count: packages.filter((item) => item.status === "材料阻断").length,
    audit_run_count: auditRuns.length,
    signature_count: signatureItems.length,
    policy_count: policyItems.length,
    timeline_count: timeline.length,
    latest_archive_run_status: auditRuns[0]?.status ?? "无"
  };
}

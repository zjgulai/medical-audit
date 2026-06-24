"use client";

import { useEffect, useMemo, useState } from "react";

import { fetchReportWorkbench } from "@/lib/api-client";
import { DataSourceBadge } from "@/components/ui/data-source-badge";
import { StatusPill } from "@/components/ui/status-pill";
import {
  rectificationSummaries,
  reportEntries,
  reportEvidenceSources,
  reportGateItems,
  workpaperPromptTemplates
} from "@/lib/portal-data";
import type {
  RectificationSummary,
  ReportEntry,
  ReportEvidenceSource,
  ReportGateItem,
  WorkpaperPromptTemplate
} from "@/lib/portal-data";
import type {
  ReportWorkbenchEntry,
  ReportWorkbenchEvidenceSource,
  WorkpaperTemplateRegistryItem
} from "@/lib/api-types";

const reportWorkflowSteps = [
  {
    title: "复核结论进入底稿",
    description: "只允许已确认违规或已明确排除的疑点进入底稿记录。",
    href: "/findings"
  },
  {
    title: "报告门禁预检",
    description: "核对附件、负责人确认、报告正文和整改请求，不通过时阻断签发。",
    href: "/pages/review-tasks"
  },
  {
    title: "正式报告与整改",
    description: "签发后冻结正文 hash，并把整改事项纳入任务结案门禁。",
    href: "/pages/review-tasks"
  }
] as const;

type ReportPageDashboardData = {
  readonly workpaperPromptTemplates: readonly WorkpaperPromptTemplate[];
  readonly reportEntries: readonly ReportEntry[];
  readonly reportEvidenceSources: readonly ReportEvidenceSource[];
};

type LoadState =
  | { readonly status: "fallback" }
  | { readonly status: "backend" }
  | { readonly status: "error" };

const initialDashboardData: ReportPageDashboardData = {
  workpaperPromptTemplates,
  reportEntries,
  reportEvidenceSources
};

export default function ReportsPage() {
  const [dashboardData, setDashboardData] = useState<ReportPageDashboardData>(initialDashboardData);
  const [loadState, setLoadState] = useState<LoadState>({ status: "fallback" });

  useEffect(() => {
    let cancelled = false;

    fetchReportWorkbench()
      .then((response) => {
        if (cancelled) {
          return;
        }
        const mappedTemplates = mapWorkbenchTemplates(response.workpaper_templates);
        const mappedEntries = mapWorkbenchEntries(response.report_entries);
        const mappedEvidenceSources = mapWorkbenchEvidenceSources(response.report_evidence_sources);
        setDashboardData({
          workpaperPromptTemplates:
            mappedTemplates.length > 0 ? mappedTemplates : workpaperPromptTemplates,
          reportEntries: mappedEntries.length > 0 ? mappedEntries : reportEntries,
          reportEvidenceSources:
            mappedEvidenceSources.length > 0 ? mappedEvidenceSources : reportEvidenceSources
        });
        setLoadState({ status: "backend" });
      })
      .catch(() => {
        if (!cancelled) {
          setLoadState({ status: "error" });
        }
      });

    return () => {
      cancelled = true;
    };
  }, []);

  const signedReportCount = useMemo(
    () => dashboardData.reportEntries.filter((entry) => entry.status === "已签发").length,
    [dashboardData]
  );
  const blockedReportCount = useMemo(
    () => dashboardData.reportEntries.filter((entry) => entry.status === "门禁阻断").length,
    [dashboardData]
  );
  const includedFindingCount = useMemo(
    () => dashboardData.reportEntries.reduce((sum, entry) => sum + entry.includedFindingCount, 0),
    [dashboardData]
  );
  const openRectificationCount = useMemo(
    () => rectificationSummaries.filter((item) => item.status !== "已整改").length,
    []
  );
  const dataSourceTag = useMemo(() => {
    if (loadState.status === "backend") {
      return "后端驱动";
    }
    if (loadState.status === "error") {
      return "样例模式（后端异常）";
    }
    return "样例数据";
  }, [loadState]);

  return (
    <main className="grid min-w-0 items-start gap-4 xl:grid-cols-[17rem_minmax(0,1fr)_18rem]">
      <aside className="audit-panel-rail min-w-0 p-5">
        <h2 className="audit-section-title">报告链路</h2>
        <p className="audit-copy mt-2">复核、门禁、签发和整改保持同一条审计链。</p>
        <ol className="mt-5 space-y-3">
          {reportWorkflowSteps.map((step, index) => (
            <li key={step.title}>
              <a className="audit-focus-ring block rounded-[var(--audit-radius-md)] border border-[var(--audit-line)] bg-white p-3 hover:bg-[var(--audit-primary-soft)]" href={step.href}>
                <span className="grid size-7 place-items-center rounded-[var(--audit-radius-md)] bg-[var(--audit-primary)] text-xs font-semibold text-white">
                  {index + 1}
                </span>
                <h3 className="mt-3 text-sm font-semibold text-[var(--audit-ink)]">{step.title}</h3>
                <p className="audit-copy mt-2">{step.description}</p>
              </a>
            </li>
          ))}
        </ol>
      </aside>

      <section className="audit-panel min-w-0 p-6">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div>
            <p className="audit-kicker">审计底稿/报告</p>
            <h1 className="audit-page-title">底稿生成与报告记录</h1>
            <p className="audit-copy mt-2 max-w-3xl">
              把复核结论、底稿、附件、负责人确认和整改事项组织成可追溯的报告首页。
            </p>
          </div>
          <div className="flex flex-col items-end gap-2">
            <StatusPill tone={loadState.status === "error" ? "warning" : "success"}>
              {dataSourceTag}
            </StatusPill>
            <DataSourceBadge source="hybrid" />
          </div>
        </div>

        <div className="mt-6 grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
          <ReportMetric label="已签发报告" value={`${signedReportCount} 份`} />
          <ReportMetric label="门禁阻断" value={`${blockedReportCount} 份`} />
          <ReportMetric label="纳入疑点" value={`${includedFindingCount} 条`} />
          <ReportMetric label="待整改" value={`${openRectificationCount} 项`} />
        </div>

        <section className="mt-6" aria-labelledby="workpaper-template-title">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div>
              <h2 id="workpaper-template-title" className="audit-section-title">
                提示词模板生成
              </h2>
              <p className="audit-copy mt-1">按三张医保费用模板绑定证据字段，生成底稿草稿、问题清单或复核摘要。</p>
            </div>
            <StatusPill tone="warning">仅草稿</StatusPill>
          </div>
          <div className="mt-4 grid gap-3 2xl:grid-cols-3">
            {dashboardData.workpaperPromptTemplates.map((template) => (
              <WorkpaperPromptCard key={template.id} template={template} />
            ))}
          </div>
        </section>

        <section className="mt-6" aria-labelledby="report-records-title">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <h2 id="report-records-title" className="audit-section-title">
              历史生成记录
            </h2>
            <a className="audit-focus-ring audit-btn audit-btn-secondary" href="/pages/review-tasks">
              打开复核任务台
            </a>
          </div>

          <div className="mt-4 grid gap-3">
            {dashboardData.reportEntries.map((entry) => (
              <ReportRecordCard key={entry.id} entry={entry} />
            ))}
          </div>
        </section>

        <section className="mt-6 grid gap-5" aria-labelledby="report-gate-title">
          <div>
            <h2 id="report-gate-title" className="audit-section-title">
              报告门禁预检
            </h2>
            <div className="mt-4 grid gap-3">
              {reportGateItems.map((item) => (
                <GateCard key={item.id} item={item} />
              ))}
            </div>
          </div>

          <aside className="audit-callout p-5">
            <p className="audit-kicker">报告正文规则</p>
            <h3 className="audit-section-title mt-2">只纳入已确认违规问题</h3>
            <p className="audit-copy mt-2">
              附录展示复核分布、附件清单和整改请求；AI 对话内容只能作为引用材料和底稿草稿来源。
            </p>
          </aside>
        </section>
      </section>

      <aside className="min-w-0 space-y-4">
        <section className="audit-panel-rail p-5">
          <h2 className="audit-section-title">底稿证据来源</h2>
          <div className="mt-4 space-y-3">
            {dashboardData.reportEvidenceSources.map((source) => (
              <EvidenceSourceCard key={source.id} source={source} />
            ))}
          </div>
        </section>

        <section className="audit-panel-rail p-5">
          <h2 className="audit-section-title">整改跟踪</h2>
          <div className="mt-4 space-y-3">
            {rectificationSummaries.map((item) => (
              <RectificationCard key={item.id} item={item} />
            ))}
          </div>
        </section>

        <a className="audit-focus-ring audit-action-card p-5" href="/graph">
          <p className="audit-kicker">知识图谱</p>
          <h2 className="audit-section-title mt-2">查看报告证据链</h2>
          <p className="audit-copy mt-2">报告、复核、疑点和整改之间的关系已在图谱页只读展示。</p>
        </a>
      </aside>
    </main>
  );
}

function mapWorkbenchTemplates(
  items: readonly WorkpaperTemplateRegistryItem[]
): readonly WorkpaperPromptTemplate[] {
  return items.map((finding, index) => {
    return {
      id: finding.id,
      name: finding.name,
      sourceTemplateId: finding.source_template_id as WorkpaperPromptTemplate["sourceTemplateId"],
      sourceTable: finding.source_table,
      sourceFileName: finding.source_file_name,
      templateStatus: finding.registry_status === "active" ? "模板字段已注册" : finding.registry_status,
      outputType: mapWorkpaperOutputType(finding.output_type),
      evidenceBindings: finding.evidence_bindings,
      prompt: finding.prompt,
      href: finding.chat_href || workpaperPromptTemplates[index]?.href || "/chat"
    };
  });
}

function mapWorkbenchEntries(items: readonly ReportWorkbenchEntry[]): readonly ReportEntry[] {
  return items.map((entry) => ({
    id: entry.id,
    title: entry.title,
    status: mapReportStatus(entry.status),
    reportNo: entry.report_no,
    owner: entry.owner,
    source: entry.source,
    includedFindingCount: entry.included_finding_count,
    appendixCount: entry.appendix_count,
    gateSummary: entry.gate_summary,
    updatedAt: formatDate(entry.updated_at),
    href: entry.href,
    taskDocxHref: entry.download_links.task_docx,
    reportDocxHref: entry.download_links.report_docx,
    reportMarkdownHref: entry.download_links.report_markdown,
    reportJsonHref: entry.download_links.report_json
  }));
}

function mapWorkbenchEvidenceSources(
  items: readonly ReportWorkbenchEvidenceSource[]
): readonly ReportEvidenceSource[] {
  return items.slice(0, 6).map((source) => ({
    id: source.id,
    title: source.title,
    kind: mapEvidenceKind(source.kind),
    reference: source.reference,
    status: mapEvidenceStatus(source.status),
    href: source.href
  }));
}

function formatDate(value: string): string {
  return value.includes("T") ? value.split("T")[0] : value.slice(0, 10);
}

function mapWorkpaperOutputType(value: string): WorkpaperPromptTemplate["outputType"] {
  if (value === "底稿草稿" || value === "问题清单" || value === "复核摘要") {
    return value;
  }
  return "底稿草稿";
}

function mapReportStatus(value: string): ReportEntry["status"] {
  if (value === "草稿" || value === "门禁阻断" || value === "已签发") {
    return value;
  }
  return "草稿";
}

function mapEvidenceKind(value: string): ReportEvidenceSource["kind"] {
  if (value === "疑点" || value === "底稿" || value === "附件" || value === "负责人确认") {
    return value;
  }
  return "底稿";
}

function mapEvidenceStatus(value: string): ReportEvidenceSource["status"] {
  if (value === "已纳入" || value === "待补证" || value === "只读") {
    return value;
  }
  return "待补证";
}

function WorkpaperPromptCard({ template }: { readonly template: WorkpaperPromptTemplate }) {
  return (
    <article className="rounded-[var(--audit-radius-md)] border border-[var(--audit-line)] bg-[var(--audit-surface-muted)] p-4">
      <div className="flex items-start justify-between gap-3">
        <div>
          <h3 className="audit-card-title">{template.name}</h3>
          <p className="audit-meta mt-1">{template.sourceTable}</p>
          {template.sourceFileName ? (
            <p className="audit-meta mt-1 break-words">{template.sourceFileName}</p>
          ) : null}
        </div>
        <StatusPill tone="info">{template.outputType}</StatusPill>
      </div>
      <p className="audit-copy mt-3">{template.prompt}</p>
      <div className="mt-4 flex flex-wrap gap-2">
        {template.evidenceBindings.map((binding) => (
          <span key={binding} className="audit-chip bg-white">
            {binding}
          </span>
        ))}
        {template.templateStatus ? (
          <span className="audit-chip bg-white">{template.templateStatus}</span>
        ) : null}
      </div>
      <div className="mt-4 flex flex-wrap gap-2">
        <a className="audit-focus-ring audit-btn audit-btn-secondary min-h-8 px-3 py-1.5 text-xs" href={template.href}>
          套用模板
        </a>
        <a className="audit-focus-ring audit-btn audit-btn-neutral min-h-8 px-3 py-1.5 text-xs" href="/pages/review-tasks">
          绑定复核任务
        </a>
      </div>
    </article>
  );
}

function ReportMetric({ label, value }: { readonly label: string; readonly value: string }) {
  return (
    <div className="audit-panel-muted p-4">
      <p className="audit-label">{label}</p>
      <p className="audit-metric-value mt-2">{value}</p>
    </div>
  );
}

function ReportRecordCard({ entry }: { readonly entry: ReportEntry }) {
  return (
    <article className="audit-panel-muted p-4">
      <div className="flex items-start justify-between gap-3">
        <div>
          <h3 className="audit-compact-title">{entry.title}</h3>
          <p className="audit-meta mt-1">{entry.gateSummary}</p>
        </div>
        <StatusPill tone={entry.status === "已签发" ? "success" : entry.status === "门禁阻断" ? "danger" : "neutral"}>
          {entry.status}
        </StatusPill>
      </div>

      <dl className="audit-meta mt-4 grid gap-3">
        <div>
          <dt className="font-semibold">编号</dt>
          <dd className="mt-1 break-words font-medium text-[var(--audit-ink)]">{entry.reportNo}</dd>
        </div>
        <div className="grid grid-cols-2 gap-3">
          <div>
            <dt className="font-semibold">负责人</dt>
            <dd className="mt-1 text-[var(--audit-ink)]">{entry.owner}</dd>
          </div>
          <div>
            <dt className="font-semibold">更新时间</dt>
            <dd className="mt-1 text-[var(--audit-ink)]">{entry.updatedAt}</dd>
          </div>
        </div>
        <div className="grid grid-cols-2 gap-3">
          <div>
            <dt className="font-semibold">纳入疑点</dt>
            <dd className="mt-1 text-[var(--audit-ink)]">{entry.includedFindingCount} 条</dd>
          </div>
          <div>
            <dt className="font-semibold">附录</dt>
            <dd className="mt-1 text-[var(--audit-ink)]">{entry.appendixCount} 个</dd>
          </div>
        </div>
      </dl>

      <div className="mt-4 flex flex-wrap gap-2">
        <a className="audit-focus-ring audit-btn audit-btn-primary min-h-9 flex-1 px-3 py-2 text-sm" href={entry.href}>
          查看详情
        </a>
        {entry.taskDocxHref ? (
          <a className="audit-focus-ring audit-btn audit-btn-secondary min-h-9 px-3 py-2 text-sm" href={entry.taskDocxHref}>
            任务 Word
          </a>
        ) : null}
        {entry.reportDocxHref ? (
          <a className="audit-focus-ring audit-btn audit-btn-secondary min-h-9 px-3 py-2 text-sm" href={entry.reportDocxHref}>
            报告 Word
          </a>
        ) : (
          <span className="inline-flex min-h-9 items-center rounded-[var(--audit-radius-md)] border border-[var(--audit-line)] bg-white px-3 py-2 text-sm font-semibold text-[var(--audit-ink-muted)]">
            报告 Word 需过门禁
          </span>
        )}
      </div>
    </article>
  );
}

function GateCard({ item }: { readonly item: ReportGateItem }) {
  return (
    <article className="audit-panel-muted p-4">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h3 className="audit-card-title">{item.label}</h3>
          <p className="audit-meta mt-1">责任人：{item.owner}</p>
        </div>
        <StatusPill tone={getGateTone(item.status)}>{item.status}</StatusPill>
      </div>
      <p className="audit-copy mt-3">{item.detail}</p>
    </article>
  );
}

function EvidenceSourceCard({ source }: { readonly source: ReportEvidenceSource }) {
  return (
    <a className="audit-focus-ring block rounded-[var(--audit-radius-md)] border border-[var(--audit-line)] bg-[var(--audit-surface-muted)] p-3 hover:bg-[var(--audit-primary-soft)]" href={source.href}>
      <div className="flex items-start justify-between gap-3">
        <div>
          <p className="audit-compact-title">{source.title}</p>
          <p className="audit-meta mt-1">
            {source.kind} / {source.reference}
          </p>
        </div>
        <StatusPill tone={source.status === "已纳入" ? "success" : source.status === "待补证" ? "warning" : "neutral"}>
          {source.status}
        </StatusPill>
      </div>
    </a>
  );
}

function RectificationCard({ item }: { readonly item: RectificationSummary }) {
  return (
    <article className="rounded-[var(--audit-radius-md)] border border-[var(--audit-line)] bg-[var(--audit-surface-muted)] p-3">
      <div className="flex items-start justify-between gap-3">
        <div>
          <h3 className="audit-compact-title">{item.title}</h3>
          <p className="audit-meta mt-1">
            {item.department} / {item.dueDate}
          </p>
          <p className="audit-meta mt-2">{item.reportNo}</p>
        </div>
        <StatusPill tone={item.status === "已整改" ? "success" : item.status === "整改中" ? "info" : "warning"}>
          {item.status}
        </StatusPill>
      </div>
    </article>
  );
}

function getGateTone(status: ReportGateItem["status"]) {
  if (status === "通过") {
    return "success";
  }

  if (status === "阻断") {
    return "danger";
  }

  return "warning";
}

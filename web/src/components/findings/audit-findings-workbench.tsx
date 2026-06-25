"use client";

import { useEffect, useMemo, useState } from "react";

import { fetchAuditFindings } from "@/lib/api-client";
import type {
  AuditFinding,
  AuditFindingGenerationReadiness,
  AuditFindingsResponse
} from "@/lib/api-types";

const STATUS_LABEL_FALLBACK: Record<string, string> = {
  "pending-review": "待复核",
  "needs-evidence": "需补证",
  "confirmed-violation": "确认违规",
  "not-violation": "排除违规",
  closed: "已关闭"
};

const READINESS_STATUS_LABELS: Record<string, string> = {
  blocked: "疑点生成链路未就绪",
  "ready-to-run": "规则运行待执行",
  generated: "疑点已生成"
};

const SEVERITY_BADGE: Record<string, { label: string; cls: string }> = {
  critical: { label: "高", cls: "border-red-200 bg-red-50 text-red-800" },
  high: { label: "高", cls: "border-red-200 bg-red-50 text-red-800" },
  medium: { label: "中", cls: "border-amber-200 bg-amber-50 text-amber-800" },
  low: { label: "低", cls: "border-sky-200 bg-sky-50 text-sky-800" }
};

const STATUS_BADGE: Record<string, string> = {
  "pending-review": "border-amber-200 bg-amber-50 text-amber-800",
  "needs-evidence": "border-amber-200 bg-amber-50 text-amber-800",
  "confirmed-violation": "border-red-200 bg-red-50 text-red-800",
  "not-violation": "border-[var(--audit-line)] bg-[var(--audit-surface-muted)] text-[var(--audit-ink-muted)]",
  closed: "border-emerald-200 bg-emerald-50 text-emerald-700"
};

function severityBadge(severity: string): { label: string; cls: string } {
  return (
    SEVERITY_BADGE[severity] ?? {
      label: severity,
      cls: "border-[var(--audit-line)] bg-[var(--audit-surface-muted)] text-[var(--audit-ink-muted)]"
    }
  );
}

type LoadState =
  | { readonly status: "loading" }
  | { readonly status: "error"; readonly message: string }
  | { readonly status: "ready"; readonly data: AuditFindingsResponse };

export function AuditFindingsWorkbench() {
  const [reviewStatus, setReviewStatus] = useState("");
  const [category, setCategory] = useState("all");
  const [selectedKey, setSelectedKey] = useState<string | null>(null);
  const [loadState, setLoadState] = useState<LoadState>({ status: "loading" });

  useEffect(() => {
    let cancelled = false;
    setLoadState({ status: "loading" });

    fetchAuditFindings(reviewStatus || undefined)
      .then((data) => {
        if (cancelled) {
          return;
        }
        setLoadState({ status: "ready", data });
        setSelectedKey(data.items[0]?.finding_key ?? null);
      })
      .catch(() => {
        if (!cancelled) {
          setLoadState({
            status: "error",
            message: "疑点清单加载失败。请确认后端数据库和审计疑点表已就绪。"
          });
        }
      });

    return () => {
      cancelled = true;
    };
  }, [reviewStatus]);

  const data = loadState.status === "ready" ? loadState.data : null;
  const reviewStatusOptions = useMemo(
    () => data?.review_status_options ?? STATUS_LABEL_FALLBACK,
    [data]
  );

  const categories = useMemo(() => {
    const counts = new Map<string, number>();
    for (const finding of data?.items ?? []) {
      counts.set(finding.finding_type, (counts.get(finding.finding_type) ?? 0) + 1);
    }
    return Array.from(counts.entries()).sort((a, b) => b[1] - a[1]);
  }, [data]);

  const filtered = useMemo(() => {
    const items = data?.items ?? [];
    return category === "all" ? items : items.filter((finding) => finding.finding_type === category);
  }, [data, category]);

  const selected = useMemo(
    () => filtered.find((finding) => finding.finding_key === selectedKey) ?? filtered[0] ?? null,
    [filtered, selectedKey]
  );

  return (
    <main className="space-y-5">
      <section className="audit-panel p-6">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div>
            <p className="audit-kicker">疑点清单</p>
            <h1 className="audit-page-title">规则命中疑点工作台</h1>
            <p className="mt-3 max-w-3xl audit-copy">
              按规则分类浏览结构化疑点，查看源记录定位、计算过程和证据链，并把需要人工判断的线索推进到复核任务。
            </p>
          </div>
          <label className="min-w-56 audit-label" htmlFor="review-status">
            复核状态
            <select
              id="review-status"
              className="audit-focus-ring audit-input mt-2 px-3 py-2.5"
              value={reviewStatus}
              onChange={(event) => setReviewStatus(event.target.value)}
            >
              <option value="">全部</option>
              {Object.entries(reviewStatusOptions).map(([value, label]) => (
                <option key={value} value={value}>
                  {label}
                </option>
              ))}
            </select>
          </label>
        </div>
      </section>

      <section className="grid gap-3 md:grid-cols-4" aria-label="疑点统计">
        <FindingStatCard label="疑点总数" value={data?.stats.total ?? "-"} />
        <FindingStatCard label="开放疑点" value={data?.stats.open ?? "-"} tone="risk" />
        <FindingStatCard label="待复核" value={data?.stats.pending_review ?? "-"} tone="review" />
        <FindingStatCard label="已建任务" value={data?.stats.linked_review_task ?? "-"} tone="evidence" />
      </section>

      {loadState.status === "loading" ? (
        <section className="audit-panel p-6">
          <h2 className="audit-section-title">正在加载疑点</h2>
          <p className="mt-2 audit-copy">读取规则命中结果和证据项。</p>
        </section>
      ) : null}

      {loadState.status === "error" ? (
        <section className="rounded-[var(--audit-radius-lg)] border border-red-200 bg-red-50 p-6 text-red-900">
          <h2 className="audit-section-title text-red-900">加载失败</h2>
          <p className="mt-2 text-sm leading-6">{loadState.message}</p>
        </section>
      ) : null}

      {loadState.status === "ready" && data && data.items.length === 0 ? (
        <section className="audit-panel p-6">
          <h2 className="audit-section-title">暂无疑点</h2>
          <p className="mt-2 audit-copy">当前筛选条件下没有可展示的规则命中记录。</p>
          <GenerationReadinessPanel readiness={data.generation_readiness} />
        </section>
      ) : null}

      {loadState.status === "ready" && data && data.items.length > 0 ? (
        <section
          className="grid gap-4 lg:grid-cols-[210px_minmax(0,1fr)_360px]"
          aria-label="疑点工作台"
        >
          <RuleTree
            categories={categories}
            totalCount={data.items.length}
            active={category}
            onSelect={(next) => setCategory(next)}
          />
          <FindingsTable
            findings={filtered}
            reviewStatusOptions={reviewStatusOptions}
            selectedKey={selected?.finding_key ?? null}
            onSelect={(key) => setSelectedKey(key)}
          />
          {selected ? (
            <FindingDetail finding={selected} reviewStatusOptions={reviewStatusOptions} />
          ) : (
            <aside className="audit-panel-muted p-4 audit-copy">选择左侧疑点查看证据链。</aside>
          )}
        </section>
      ) : null}
    </main>
  );
}

function FindingStatCard({
  label,
  value,
  tone
}: {
  readonly label: string;
  readonly value: number | string;
  readonly tone?: "risk" | "review" | "evidence";
}) {
  const toneClass =
    tone === "risk"
      ? "text-[var(--audit-red)]"
      : tone === "review"
        ? "text-[var(--audit-amber)]"
        : tone === "evidence"
          ? "text-[var(--audit-green)]"
          : "";
  return (
    <article className="audit-panel p-4">
      <div className="audit-label">{label}</div>
      <div className={`mt-2 audit-metric-value ${toneClass}`}>{value}</div>
    </article>
  );
}

function RuleTree({
  categories,
  totalCount,
  active,
  onSelect
}: {
  readonly categories: readonly (readonly [string, number])[];
  readonly totalCount: number;
  readonly active: string;
  readonly onSelect: (category: string) => void;
}) {
  const rows: (readonly [string, string, number])[] = [
    ["all", "全部疑点", totalCount],
    ...categories.map(([type, count]) => [type, type, count] as const)
  ];
  return (
    <nav className="audit-panel p-3" aria-label="规则导航">
      <p className="px-2 pb-2 audit-meta">规则导航</p>
      <ul className="space-y-1">
        {rows.map(([value, label, count]) => {
          const isActive = active === value;
          return (
            <li key={value}>
              <button
                type="button"
                onClick={() => onSelect(value)}
                aria-pressed={isActive}
                className={`audit-focus-ring flex w-full items-center justify-between rounded-[var(--audit-radius-sm)] px-2.5 py-2 text-left text-sm ${
                  isActive
                    ? "bg-[var(--audit-primary-soft)] font-semibold text-[var(--audit-primary)]"
                    : "text-[var(--audit-ink-muted)] hover:bg-[var(--audit-surface-muted)]"
                }`}
              >
                <span className="truncate">{label}</span>
                <span className="ml-2 shrink-0 tabular-nums">{count}</span>
              </button>
            </li>
          );
        })}
      </ul>
    </nav>
  );
}

function FindingsTable({
  findings,
  reviewStatusOptions,
  selectedKey,
  onSelect
}: {
  readonly findings: readonly AuditFinding[];
  readonly reviewStatusOptions: Record<string, string>;
  readonly selectedKey: string | null;
  readonly onSelect: (key: string) => void;
}) {
  if (findings.length === 0) {
    return (
      <section className="audit-panel p-6">
        <h2 className="audit-section-title">该分类暂无疑点</h2>
        <p className="mt-2 audit-copy">切换左侧规则分类查看其他疑点。</p>
      </section>
    );
  }
  return (
    <section className="audit-panel overflow-hidden p-0" aria-label="审计疑点列表">
      <table className="w-full table-fixed border-collapse text-sm">
        <thead>
          <tr className="audit-meta text-left">
            <th className="px-4 py-3 font-normal">疑点 / 规则</th>
            <th className="w-14 px-2 py-3 font-normal">严重</th>
            <th className="w-20 px-2 py-3 font-normal">复核</th>
          </tr>
        </thead>
        <tbody>
          {findings.map((finding) => {
            const sev = severityBadge(finding.severity);
            const isActive = finding.finding_key === selectedKey;
            return (
              <tr
                key={finding.finding_key}
                onClick={() => onSelect(finding.finding_key)}
                className={`cursor-pointer border-t border-[var(--audit-line)] ${
                  isActive ? "bg-[var(--audit-primary-soft)]" : "hover:bg-[var(--audit-surface-muted)]"
                }`}
              >
                <td className="max-w-0 px-4 py-3">
                  <div className="truncate font-semibold text-[var(--audit-ink)]">
                    {finding.rule_key ?? finding.finding_type}
                  </div>
                  <div className="truncate audit-meta font-mono">{finding.finding_key}</div>
                </td>
                <td className="px-2 py-3">
                  <span className={`inline-block rounded-full border px-2 py-0.5 text-xs font-semibold ${sev.cls}`}>
                    {sev.label}
                  </span>
                </td>
                <td className="px-2 py-3">
                  <span
                    className={`inline-block rounded-full border px-2 py-0.5 text-xs font-semibold ${
                      STATUS_BADGE[finding.review_status] ??
                      "border-[var(--audit-line)] bg-[var(--audit-surface-muted)] text-[var(--audit-ink-muted)]"
                    }`}
                  >
                    {reviewStatusOptions[finding.review_status] ?? finding.review_status}
                  </span>
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </section>
  );
}

function FindingDetail({
  finding,
  reviewStatusOptions
}: {
  readonly finding: AuditFinding;
  readonly reviewStatusOptions: Record<string, string>;
}) {
  const sev = severityBadge(finding.severity);
  return (
    <aside className="audit-panel p-5" aria-label={`${finding.finding_key} 证据链`}>
      <header className="flex flex-wrap items-start justify-between gap-2">
        <div>
          <p className="audit-meta font-mono">{finding.finding_key}</p>
          <h2 className="mt-1 audit-section-title">
            {finding.finding_type} · {finding.rule_key ?? "未绑定规则"}
          </h2>
        </div>
        <span className={`rounded-full border px-3 py-1 text-xs font-semibold ${sev.cls}`}>
          {sev.label}危
        </span>
      </header>

      <dl className="mt-4 grid grid-cols-2 gap-2 text-sm">
        <FindingSummaryItem label="rule version" value={finding.rule_version_key ?? "n/a"} />
        <FindingSummaryItem label="run" value={finding.audit_run_key ?? "n/a"} />
        <FindingSummaryItem label="task" value={finding.audit_task_key ?? "n/a"} />
        <FindingSummaryItem
          label="复核"
          value={reviewStatusOptions[finding.review_status] ?? finding.review_status}
        />
      </dl>

      <div className="mt-4 space-y-3">
        <JsonPanel title="源记录定位" value={finding.source_record_locator} />
        <JsonPanel title="计算过程" value={finding.calculation_trace} />
      </div>

      <section className="mt-4" aria-label={`${finding.finding_key} 证据项`}>
        <h3 className="audit-card-title">证据链</h3>
        <div className="mt-2 space-y-2">
          {finding.evidence_items.map((evidence) => (
            <article
              key={`${evidence.evidence_type}-${evidence.citation_id ?? evidence.created_at}`}
              className="audit-panel-muted p-3"
            >
              <div className="flex flex-wrap items-center justify-between gap-2 audit-meta font-semibold text-[var(--audit-ink-muted)]">
                <span>{evidence.evidence_type}</span>
                <span>{evidence.citation_id ?? "无 citation_id"}</span>
              </div>
              <p className="mt-2 audit-copy">{evidence.snippet ?? "未记录证据片段"}</p>
              <div className="mt-2 audit-meta">
                index: {evidence.index_version_key ?? "n/a"} · package:{" "}
                {evidence.source_package_version_key ?? "n/a"}
              </div>
            </article>
          ))}
          {finding.evidence_items.length === 0 ? (
            <p className="audit-panel-muted p-3 audit-copy">
              未绑定证据项；该疑点不得进入正式报告。
            </p>
          ) : null}
        </div>
      </section>

      <div className="mt-5 flex flex-wrap items-center gap-3">
        <a
          className="audit-focus-ring audit-btn audit-btn-neutral"
          href={`/audit-findings/${finding.finding_key}/export`}
        >
          导出疑点 JSON
        </a>
        {finding.review_task_id ? (
          <span className="rounded-full border border-emerald-200 bg-emerald-50 px-3 py-1.5 text-xs font-semibold text-emerald-700">
            已创建复核任务：{finding.review_task_id}
          </span>
        ) : (
          <form method="post" action={`/pages/audit-findings/${finding.finding_key}/review-task`}>
            <button className="audit-focus-ring audit-btn audit-btn-primary" type="submit">
              创建复核任务
            </button>
          </form>
        )}
      </div>
    </aside>
  );
}

function GenerationReadinessPanel({
  readiness
}: {
  readonly readiness: AuditFindingGenerationReadiness;
}) {
  const statusLabel = READINESS_STATUS_LABELS[readiness.status] ?? readiness.status;
  const missingPrerequisites = readiness.prerequisites.filter((item) => !item.ready);

  return (
    <div className="audit-panel-muted mt-5 p-4">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h3 className="audit-card-title">{statusLabel}</h3>
          <p className="mt-1 audit-copy">
            {readiness.status === "blocked"
              ? "规则疑点需要先完成业务数据底座、HIS staging 和规则运行上下文。"
              : "规则运行上下文已具备，等待受控执行后写入疑点。"}
          </p>
        </div>
        <span
          className={`rounded-full border px-3 py-1 text-xs font-semibold ${
            readiness.ready
              ? "border-emerald-200 bg-emerald-50 text-emerald-700"
              : "border-amber-200 bg-amber-50 text-amber-800"
          }`}
        >
          {readiness.ready ? "ready" : "blocked"}
        </span>
      </div>

      {missingPrerequisites.length > 0 ? (
        <div className="mt-4">
          <h4 className="audit-label">缺失前置数据</h4>
          <div className="mt-2 grid gap-2 md:grid-cols-2">
            {missingPrerequisites.map((item) => (
              <div
                key={item.key}
                className="rounded-[var(--audit-radius-md)] border border-amber-200 bg-white px-3 py-2"
              >
                <div className="audit-compact-title">{item.label}</div>
                <div className="mt-1 font-mono text-xs leading-5 text-amber-700">
                  {item.key}: {item.count}
                </div>
              </div>
            ))}
          </div>
        </div>
      ) : null}

      {readiness.blocking_reasons.length > 0 ? (
        <div className="mt-4">
          <h4 className="audit-label">阻断原因</h4>
          <ul className="mt-2 space-y-1 audit-copy">
            {readiness.blocking_reasons.slice(0, 4).map((reason) => (
              <li key={reason.code}>{reason.message}</li>
            ))}
          </ul>
        </div>
      ) : null}

      {readiness.next_actions.length > 0 ? (
        <div className="mt-4">
          <h4 className="audit-label">下一步</h4>
          <ul className="mt-2 space-y-1 audit-copy">
            {readiness.next_actions.map((action) => (
              <li key={action}>{action}</li>
            ))}
          </ul>
        </div>
      ) : null}
    </div>
  );
}

function FindingSummaryItem({ label, value }: { readonly label: string; readonly value: string }) {
  return (
    <div className="audit-panel-muted p-3">
      <dt className="audit-meta font-mono">{label}</dt>
      <dd className="mt-1 break-words audit-compact-title">{value}</dd>
    </div>
  );
}

function JsonPanel({ title, value }: { readonly title: string; readonly value: Record<string, unknown> }) {
  return (
    <section className="audit-panel-muted p-3">
      <h3 className="audit-card-title">{title}</h3>
      <pre className="mt-2 max-h-56 overflow-auto whitespace-pre-wrap break-words font-mono text-xs leading-5 text-[var(--audit-ink-muted)]">
        {JSON.stringify(value, null, 2)}
      </pre>
    </section>
  );
}

"use client";

import { useEffect, useMemo, useState } from "react";

import { fetchAuditFindings } from "@/lib/api-client";
import type { AuditFinding, AuditFindingsResponse } from "@/lib/api-types";

const STATUS_LABEL_FALLBACK: Record<string, string> = {
  "pending-review": "待复核",
  "needs-evidence": "需补证",
  "confirmed-violation": "确认违规",
  "not-violation": "排除违规",
  closed: "已关闭"
};

type LoadState =
  | { readonly status: "loading" }
  | { readonly status: "error"; readonly message: string }
  | { readonly status: "ready"; readonly data: AuditFindingsResponse };

export function AuditFindingsWorkbench() {
  const [reviewStatus, setReviewStatus] = useState("");
  const [loadState, setLoadState] = useState<LoadState>({ status: "loading" });

  useEffect(() => {
    let cancelled = false;
    setLoadState({ status: "loading" });

    fetchAuditFindings(reviewStatus || undefined)
      .then((data) => {
        if (!cancelled) {
          setLoadState({ status: "ready", data });
        }
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

  return (
    <main className="space-y-5">
      <section className="rounded-[28px] border border-slate-200 bg-white p-6 shadow-[var(--audit-shadow-card)]">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div>
            <p className="text-sm font-medium text-blue-700">疑点清单</p>
            <h1 className="mt-2 text-3xl font-semibold tracking-tight text-slate-950">
              规则命中疑点工作台
            </h1>
            <p className="mt-3 max-w-3xl text-sm leading-6 text-slate-600">
              展示结构化规则产生的疑点、源记录定位、计算过程和证据项，并把需要人工判断的线索推进到复核任务。
            </p>
          </div>
          <a
            className="audit-focus-ring rounded-2xl border border-slate-200 px-4 py-2.5 text-sm font-semibold text-slate-700 transition hover:bg-slate-50"
            href="/pages/audit-findings"
          >
            打开后端兼容页
          </a>
        </div>
      </section>

      <section className="grid gap-3 md:grid-cols-4" aria-label="疑点统计">
        <FindingStatCard label="疑点总数" value={data?.stats.total ?? "-"} />
        <FindingStatCard label="开放疑点" value={data?.stats.open ?? "-"} />
        <FindingStatCard label="待复核" value={data?.stats.pending_review ?? "-"} />
        <FindingStatCard label="已建任务" value={data?.stats.linked_review_task ?? "-"} />
      </section>

      <section className="rounded-[28px] border border-slate-200 bg-white p-5 shadow-[var(--audit-shadow-card)]">
        <div className="flex flex-wrap items-end justify-between gap-4">
          <label className="min-w-56 text-sm font-semibold text-slate-950" htmlFor="review-status">
            复核状态
            <select
              id="review-status"
              className="audit-focus-ring mt-2 w-full rounded-2xl border border-slate-200 bg-slate-50 px-3 py-2.5 text-sm text-slate-950"
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
          <div className="text-right text-xs leading-5 text-slate-500">
            <div>store: {data?.store.backend ?? "loading"}</div>
            <div>{data?.store.ready ? "persistent" : "pending"}</div>
          </div>
        </div>
      </section>

      {loadState.status === "loading" ? (
        <section className="rounded-[28px] border border-slate-200 bg-white p-6 shadow-[var(--audit-shadow-card)]">
          <h2 className="text-xl font-semibold tracking-tight text-slate-950">正在加载疑点</h2>
          <p className="mt-2 text-sm text-slate-600">读取规则命中结果和证据项。</p>
        </section>
      ) : null}

      {loadState.status === "error" ? (
        <section className="rounded-[28px] border border-red-200 bg-red-50 p-6 text-red-900">
          <h2 className="text-xl font-semibold tracking-tight">加载失败</h2>
          <p className="mt-2 text-sm leading-6">{loadState.message}</p>
        </section>
      ) : null}

      {loadState.status === "ready" ? (
        <FindingsList findings={loadState.data.items} reviewStatusOptions={reviewStatusOptions} />
      ) : null}
    </main>
  );
}

function FindingStatCard({ label, value }: { readonly label: string; readonly value: number | string }) {
  return (
    <article className="rounded-[24px] border border-slate-200 bg-white p-4 shadow-[var(--audit-shadow-card)]">
      <div className="text-xs font-medium uppercase text-slate-500">{label}</div>
      <div className="mt-2 text-3xl font-semibold tracking-tight text-slate-950">{value}</div>
    </article>
  );
}

function FindingsList({
  findings,
  reviewStatusOptions
}: {
  readonly findings: readonly AuditFinding[];
  readonly reviewStatusOptions: Record<string, string>;
}) {
  if (findings.length === 0) {
    return (
      <section className="rounded-[28px] border border-slate-200 bg-white p-6 shadow-[var(--audit-shadow-card)]">
        <h2 className="text-xl font-semibold tracking-tight text-slate-950">暂无疑点</h2>
        <p className="mt-2 text-sm leading-6 text-slate-600">当前筛选条件下没有可展示的规则命中记录。</p>
      </section>
    );
  }

  return (
    <section className="space-y-4" aria-label="审计疑点列表">
      {findings.map((finding) => (
        <article
          key={finding.finding_key}
          className="rounded-[28px] border border-slate-200 bg-white p-5 shadow-[var(--audit-shadow-card)]"
        >
          <header className="flex flex-wrap items-start justify-between gap-3">
            <div>
              <p className="text-xs font-medium uppercase text-slate-500">{finding.finding_key}</p>
              <h2 className="mt-1 text-xl font-semibold tracking-tight text-slate-950">
                {finding.finding_type} · {finding.rule_key ?? "未绑定规则"}
              </h2>
            </div>
            <span className="rounded-full border border-amber-200 bg-amber-50 px-3 py-1 text-xs font-semibold text-amber-800">
              {reviewStatusOptions[finding.review_status] ?? finding.review_status}
            </span>
          </header>

          <dl className="mt-4 grid gap-3 text-sm md:grid-cols-4">
            <FindingSummaryItem label="rule version" value={finding.rule_version_key ?? "n/a"} />
            <FindingSummaryItem label="run" value={finding.audit_run_key ?? "n/a"} />
            <FindingSummaryItem label="task" value={finding.audit_task_key ?? "n/a"} />
            <FindingSummaryItem label="severity" value={finding.severity} />
          </dl>

          <div className="mt-4 grid gap-4 lg:grid-cols-2">
            <JsonPanel title="源记录定位" value={finding.source_record_locator} />
            <JsonPanel title="计算过程" value={finding.calculation_trace} />
          </div>

          <section className="mt-4" aria-label={`${finding.finding_key} 证据项`}>
            <h3 className="text-sm font-semibold text-slate-950">证据项</h3>
            <div className="mt-2 space-y-2">
              {finding.evidence_items.map((evidence) => (
                <article
                  key={`${evidence.evidence_type}-${evidence.citation_id ?? evidence.created_at}`}
                  className="rounded-2xl border border-slate-200 bg-slate-50 p-3"
                >
                  <div className="flex flex-wrap items-center justify-between gap-2 text-xs font-semibold text-slate-700">
                    <span>{evidence.evidence_type}</span>
                    <span>{evidence.citation_id ?? "无 citation_id"}</span>
                  </div>
                  <p className="mt-2 text-sm leading-6 text-slate-700">
                    {evidence.snippet ?? "未记录证据片段"}
                  </p>
                  <div className="mt-2 text-xs text-slate-500">
                    index: {evidence.index_version_key ?? "n/a"} · package:{" "}
                    {evidence.source_package_version_key ?? "n/a"}
                  </div>
                </article>
              ))}
              {finding.evidence_items.length === 0 ? (
                <p className="rounded-2xl border border-slate-200 bg-slate-50 p-3 text-sm text-slate-600">
                  未绑定证据项；该疑点不得进入正式报告。
                </p>
              ) : null}
            </div>
          </section>

          <div className="mt-4 flex flex-wrap items-center gap-3">
            <a
              className="audit-focus-ring rounded-2xl border border-slate-200 px-4 py-2.5 text-sm font-semibold text-slate-700 transition hover:bg-slate-50"
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
                <button
                  className="audit-focus-ring rounded-2xl bg-blue-600 px-4 py-2.5 text-sm font-semibold text-white shadow-lg shadow-blue-600/20 transition hover:bg-blue-700"
                  type="submit"
                >
                  创建复核任务
                </button>
              </form>
            )}
          </div>
        </article>
      ))}
    </section>
  );
}

function FindingSummaryItem({ label, value }: { readonly label: string; readonly value: string }) {
  return (
    <div className="rounded-2xl border border-slate-200 bg-slate-50 p-3">
      <dt className="text-xs font-medium uppercase text-slate-500">{label}</dt>
      <dd className="mt-1 break-words font-semibold text-slate-900">{value}</dd>
    </div>
  );
}

function JsonPanel({ title, value }: { readonly title: string; readonly value: Record<string, unknown> }) {
  return (
    <section className="rounded-2xl border border-slate-200 bg-slate-50 p-3">
      <h3 className="text-sm font-semibold text-slate-950">{title}</h3>
      <pre className="mt-2 max-h-64 overflow-auto whitespace-pre-wrap break-words text-xs leading-5 text-slate-700">
        {JSON.stringify(value, null, 2)}
      </pre>
    </section>
  );
}

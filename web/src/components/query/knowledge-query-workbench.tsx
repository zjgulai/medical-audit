"use client";

import { FormEvent, useMemo, useState } from "react";

import { StatusPill } from "@/components/ui/status-pill";
import { runKnowledgeQuery } from "@/lib/api-client";
import type { QueryCitation, QueryResponse, SourceCollection } from "@/lib/api-types";

type QueryState =
  | { readonly status: "idle" }
  | { readonly status: "loading" }
  | { readonly status: "success"; readonly result: QueryResponse }
  | { readonly status: "error"; readonly message: string };

type SourceCollectionOption = {
  readonly value: SourceCollection;
  readonly label: string;
  readonly description: string;
};

const SOURCE_COLLECTION_OPTIONS: readonly SourceCollectionOption[] = [
  {
    value: "medical-insurance-laws",
    label: "法规政策",
    description: "医保、医疗、药品、基金监管相关法律政策。"
  },
  {
    value: "supervision-rules-knowledge",
    label: "监管两库",
    description: "智能监管规则库、知识库和知识点明细。"
  },
  {
    value: "medical-insurance-catalog",
    label: "医保目录",
    description: "药品、诊疗项目、编码、支付范围和限制条件。"
  },
  {
    value: "risk-negative-list",
    label: "风险清单",
    description: "高风险负面清单、案例和风险线索。"
  }
];

const DEFAULT_QUESTION = "医保基金审核发现异常收费时应优先核验证据链的哪些要点？";

export function KnowledgeQueryWorkbench() {
  const [question, setQuestion] = useState(DEFAULT_QUESTION);
  const [selectedCollections, setSelectedCollections] = useState<readonly SourceCollection[]>([]);
  const [queryState, setQueryState] = useState<QueryState>({ status: "idle" });

  const chatHref = useMemo(() => {
    const params = new URLSearchParams();
    params.set("question", question);
    for (const collection of selectedCollections) {
      params.append("source_collection", collection);
    }
    return `/pages/chat?${params.toString()}`;
  }, [question, selectedCollections]);

  async function submitQuery(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const normalizedQuestion = question.trim();

    if (!normalizedQuestion) {
      setQueryState({ status: "error", message: "请输入需要检索的医保审核问题。" });
      return;
    }

    setQueryState({ status: "loading" });
    try {
      const result = await runKnowledgeQuery({
        question: normalizedQuestion,
        top_k: 5,
        source_collections: selectedCollections
      });
      setQueryState({ status: "success", result });
    } catch {
      setQueryState({ status: "error", message: "查询失败。请确认后端检索已就绪后重试。" });
    }
  }

  function toggleCollection(collection: SourceCollection) {
    setSelectedCollections((current) =>
      current.includes(collection) ? current.filter((item) => item !== collection) : [...current, collection]
    );
  }

  return (
    <main className="space-y-5">
      <section className="audit-panel p-6">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div>
            <p className="audit-kicker">查询工作台</p>
            <h1 className="audit-page-title">引用优先的知识查询</h1>
            <p className="mt-3 max-w-3xl audit-copy">
              直接调用 FastAPI 查询接口，返回可核验引用、原文预览和证据分组。查询结果只作为审证线索，
              进入底稿前仍需人工复核。
            </p>
          </div>
          <StatusPill tone="info">API-first</StatusPill>
        </div>

        <form className="mt-6 space-y-5" onSubmit={submitQuery}>
          <label className="block" htmlFor="knowledge-query-question">
            <span className="audit-label">审计问题</span>
            <textarea
              id="knowledge-query-question"
              className="audit-focus-ring audit-input mt-2 min-h-28 resize-y px-4 py-3 leading-6"
              value={question}
              onChange={(event) => setQuestion(event.target.value)}
              required
            />
          </label>

          <fieldset className="space-y-3">
            <legend className="audit-label">来源过滤</legend>
            <div className="grid gap-3 lg:grid-cols-4">
              {SOURCE_COLLECTION_OPTIONS.map((option) => {
                const checked = selectedCollections.includes(option.value);
                return (
                  <label
                    className={`audit-focus-ring block rounded-[var(--audit-radius-lg)] border p-4 text-sm transition ${
                      checked
                        ? "border-[var(--audit-primary-line)] bg-[var(--audit-primary-soft)] text-[var(--audit-primary)]"
                        : "border-[var(--audit-line-soft)] bg-[var(--audit-surface-muted)] text-[var(--audit-ink-muted)]"
                    }`}
                    key={option.value}
                  >
                    <span className="flex items-center gap-2 font-semibold text-[var(--audit-ink)]">
                      <input
                        checked={checked}
                        className="size-4"
                        onChange={() => toggleCollection(option.value)}
                        type="checkbox"
                      />
                      {option.label}
                    </span>
                    <span className="mt-2 block audit-meta">{option.description}</span>
                  </label>
                );
              })}
            </div>
          </fieldset>

          <div className="flex flex-wrap items-center gap-3">
            <button
              className="audit-focus-ring audit-btn audit-btn-primary"
              disabled={queryState.status === "loading"}
              type="submit"
            >
              {queryState.status === "loading" ? "查询中" : "执行查询"}
            </button>
            <a
              className="audit-focus-ring audit-btn audit-btn-neutral"
              href="/pages/query"
            >
              打开后端兼容页
            </a>
          </div>
        </form>
      </section>

      {queryState.status === "idle" && (
        <section className="audit-panel p-6">
          <h2 className="audit-section-title">等待查询</h2>
          <p className="mt-2 audit-copy">
            提交后会展示答案、证据分组和每条引用的原文预览入口。
          </p>
        </section>
      )}

      {queryState.status === "error" && (
        <section className="rounded-[var(--audit-radius-lg)] border border-red-200 bg-red-50 p-6">
          <h2 className="audit-section-title text-red-900">查询未完成</h2>
          <p className="mt-2 text-sm leading-6 text-red-800">{queryState.message}</p>
        </section>
      )}

      {queryState.status === "success" && <QueryResultPanel chatHref={chatHref} result={queryState.result} />}
    </main>
  );
}

function QueryResultPanel({
  chatHref,
  result
}: {
  readonly chatHref: string;
  readonly result: QueryResponse;
}) {
  return (
    <section className="audit-panel p-6">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <p className="audit-kicker">查询结果摘要</p>
          <h2 className="mt-2 max-w-3xl audit-section-title">{result.question}</h2>
        </div>
        <StatusPill tone={result.citations.length > 0 ? "success" : "warning"}>
          {result.citations.length} 条引用
        </StatusPill>
      </div>

      <div className="audit-panel-muted mt-5 p-4 audit-copy">
        {result.answer}
      </div>

      <div className="mt-5 flex flex-wrap gap-2">
        <span className="audit-chip">confidence: {result.confidence}</span>
        <span className="audit-chip">fallback: {result.fallback_used ? "yes" : "no"}</span>
        <span className="audit-chip">query_log_index: {result.query_log_index}</span>
      </div>

      <div className="mt-6 grid gap-5 xl:grid-cols-[1fr_22rem]">
        <div>
          <h3 className="audit-card-title">引用证据</h3>
          <div className="audit-table-shell mt-3 divide-y divide-[var(--audit-line-soft)]">
            {result.citations.map((citation) => (
              <CitationRow citation={citation} key={citation.citation_id} />
            ))}
          </div>
        </div>

        <aside className="audit-panel-muted p-4">
          <h3 className="audit-card-title">证据分组</h3>
          <div className="mt-3 space-y-3">
            {result.basis_groups.map((group) => (
              <div key={`${group.evidence_type}-${group.title}`}>
                <p className="audit-compact-title">{group.title}</p>
                <p className="mt-1 audit-meta">
                  {group.evidence_type} · {group.items.length} 条依据
                </p>
              </div>
            ))}
          </div>
          <a
            className="audit-focus-ring audit-btn audit-btn-primary mt-5"
            href={chatHref}
          >
            转入对话审证
          </a>
        </aside>
      </div>
    </section>
  );
}

function CitationRow({ citation }: { readonly citation: QueryCitation }) {
  return (
    <article className="p-4">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <p className="audit-compact-title">
            {citation.marker} · {citation.evidence_type}
          </p>
          <p className="mt-1 audit-meta">{locatorSummary(citation.locator)}</p>
        </div>
        <a
          className="audit-focus-ring audit-btn audit-btn-neutral min-h-8 px-3 py-1.5 text-xs"
          href={`/pages/preview/${citation.chunk_id}`}
        >
          核验原文
        </a>
      </div>
      <p className="mt-3 audit-copy">{citation.snippet}</p>
      <p className="mt-3 break-all font-mono text-xs leading-5 text-[var(--audit-ink-subtle)]">chunk: {citation.chunk_id}</p>
    </article>
  );
}

function locatorSummary(locator: Record<string, unknown>): string {
  const source = stringValue(locator.source_path) ?? stringValue(locator.file_name) ?? "unknown source";
  const page = numberOrStringValue(locator.page_number);
  const lineStart = numberOrStringValue(locator.line_start);
  const lineEnd = numberOrStringValue(locator.line_end);

  if (page !== undefined) {
    return `${source} · page ${page}`;
  }
  if (lineStart !== undefined) {
    return `${source} · lines ${lineStart}${lineEnd !== undefined ? `-${lineEnd}` : ""}`;
  }
  return source;
}

function stringValue(value: unknown): string | undefined {
  return typeof value === "string" && value.trim() ? value : undefined;
}

function numberOrStringValue(value: unknown): string | undefined {
  if (typeof value === "number") {
    return String(value);
  }
  return stringValue(value);
}

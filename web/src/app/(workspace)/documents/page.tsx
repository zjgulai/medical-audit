"use client";

import { FormEvent, useMemo, useState } from "react";

import { StatusPill } from "@/components/ui/status-pill";
import { runKnowledgeQuery } from "@/lib/api-client";
import type { QueryCitation, QueryResponse, SourceCollection } from "@/lib/api-types";
import {
  conversationDocuments,
  documentCategoryStats,
  documentSearchHistory,
  knowledgeDocuments,
  PortalDocumentItem
} from "@/lib/portal-data";

type DocumentSearchState =
  | { readonly status: "idle" }
  | { readonly status: "loading" }
  | { readonly status: "success"; readonly result: QueryResponse }
  | { readonly status: "error"; readonly message: string };

const SOURCE_COLLECTIONS: readonly SourceCollection[] = [
  "medical-insurance-laws",
  "supervision-rules-knowledge",
  "medical-insurance-catalog",
  "risk-negative-list"
];

export default function DocumentsPage() {
  const totalDocuments = documentCategoryStats.reduce((sum, category) => sum + category.documentCount, 0);
  const [query, setQuery] = useState("");
  const [selectedCollections, setSelectedCollections] = useState<readonly SourceCollection[]>([]);
  const [searchState, setSearchState] = useState<DocumentSearchState>({ status: "idle" });

  const selectedScopeText = useMemo(() => {
    if (selectedCollections.length === 0) {
      return "全部来源";
    }
    return documentCategoryStats
      .filter((category) => selectedCollections.includes(category.sourceCollection as SourceCollection))
      .map((category) => category.name)
      .join("、");
  }, [selectedCollections]);

  async function submitSearch(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const normalizedQuery = query.trim();
    if (!normalizedQuery) {
      setSearchState({ status: "error", message: "请输入审计问题或文档关键词。" });
      return;
    }

    setSearchState({ status: "loading" });
    try {
      const result = await runKnowledgeQuery({
        question: normalizedQuery,
        top_k: 8,
        source_collections: selectedCollections
      });
      setSearchState({ status: "success", result });
    } catch {
      setSearchState({ status: "error", message: "检索失败。请确认后端检索已就绪后重试。" });
    }
  }

  function toggleCollection(sourceCollection: string) {
    if (!isSourceCollection(sourceCollection)) {
      return;
    }
    setSelectedCollections((current) =>
      current.includes(sourceCollection)
        ? current.filter((item) => item !== sourceCollection)
        : [...current, sourceCollection]
    );
  }

  function runHistorySearch(item: string) {
    setQuery(item);
    setSearchState({ status: "idle" });
  }

  return (
    <main className="grid min-w-0 gap-4 xl:grid-cols-[17rem_minmax(0,1fr)_18rem]">
      <aside className="audit-panel-rail min-w-0 p-5">
        <h2 className="audit-section-title">文档源</h2>
        <p className="audit-copy mt-2">按审计材料来源限定后端检索范围。</p>
        <div className="mt-5 space-y-3">
          {documentCategoryStats.map((category) => (
            <DocumentSourceCard
              category={category}
              key={category.id}
              onToggle={() => toggleCollection(category.sourceCollection)}
              selected={selectedCollections.includes(category.sourceCollection as SourceCollection)}
            />
          ))}
        </div>
      </aside>

      <section className="audit-panel min-w-0 p-6">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div>
            <p className="audit-kicker">文档检索</p>
            <h1 className="audit-page-title">材料与知识库统一检索</h1>
            <p className="audit-copy mt-2 max-w-3xl">围绕当前审计项目检索对话文档、知识库文档和可引用材料。</p>
          </div>
          <StatusPill tone={searchState.status === "success" ? "success" : "info"}>API-first</StatusPill>
        </div>

        <form className="audit-panel-muted mt-6 p-5" onSubmit={submitSearch}>
          <label className="block" htmlFor="document-query">
            <span className="audit-label">审计问题或文档关键词</span>
            <textarea
              className="audit-focus-ring audit-input mt-2 min-h-24 resize-y px-3 py-2.5 leading-6"
              id="document-query"
              onChange={(event) => setQuery(event.target.value)}
              placeholder="例如：重复收费、目录限制、超量开药"
              value={query}
            />
          </label>
          <div className="mt-4 flex flex-wrap items-center justify-between gap-3">
            <div className="audit-meta">检索范围：{selectedScopeText}</div>
            <div className="flex flex-wrap gap-3">
              <button
                className="audit-focus-ring audit-btn audit-btn-primary"
                disabled={searchState.status === "loading"}
                type="submit"
              >
                {searchState.status === "loading" ? "检索中" : "执行检索"}
              </button>
              <a
                className="audit-focus-ring audit-btn audit-btn-secondary"
                href={`/chat${query.trim() ? `?question=${encodeURIComponent(query.trim())}` : ""}`}
              >
                转入 AI 对话
              </a>
            </div>
          </div>
        </form>

        <div className="mt-5 grid gap-3 sm:grid-cols-3">
          <Metric label="可检索材料" value={totalDocuments.toLocaleString()} />
          <Metric
            label="本次引用"
            value={searchState.status === "success" ? String(searchState.result.citations.length) : "-"}
          />
          <Metric label="引用入口" value="已开启" />
        </div>

        <div className="mt-6">
          <DocumentSearchResult state={searchState} />
        </div>

        <div className="mt-6 grid gap-5 lg:grid-cols-2">
          <DocumentList title="对话文档" documents={conversationDocuments} />
          <DocumentList title="知识库文档" documents={knowledgeDocuments} />
        </div>
      </section>

      <aside className="min-w-0 space-y-4">
        <section className="audit-panel-rail p-5">
          <h2 className="audit-section-title">搜索历史</h2>
          <div className="mt-4 space-y-2">
            {documentSearchHistory.map((item) => (
              <button
                className="audit-focus-ring block w-full rounded-[var(--audit-radius-md)] bg-[var(--audit-surface-muted)] px-3 py-2 text-left text-sm text-[var(--audit-ink-muted)] hover:bg-[var(--audit-surface-subtle)] hover:text-[var(--audit-ink)]"
                key={item}
                onClick={() => runHistorySearch(item)}
                type="button"
              >
                {item}
              </button>
            ))}
          </div>
        </section>

        <a className="audit-focus-ring audit-action-card p-5" href="/knowledge-base">
          <p className="audit-kicker">知识库</p>
          <h2 className="audit-section-title mt-2">查看索引覆盖</h2>
          <p className="audit-copy mt-2">确认个人、系统、公开知识库的文档数、字符数和应用绑定。</p>
        </a>

        <a className="audit-focus-ring audit-callout block p-5" href="/chat">
          <p className="audit-kicker">AI 对话</p>
          <h2 className="audit-section-title mt-2">带着材料进入审证</h2>
          <p className="audit-copy mt-2">检索不到充分引用时，转入 AI 对话继续限定来源、补充问题和形成复核清单。</p>
        </a>
      </aside>
    </main>
  );
}

function DocumentSourceCard({
  category,
  onToggle,
  selected
}: {
  readonly category: (typeof documentCategoryStats)[number];
  readonly onToggle: () => void;
  readonly selected: boolean;
}) {
  return (
    <button
      aria-pressed={selected}
      className={`audit-focus-ring w-full rounded-[var(--audit-radius-md)] border p-3 text-left transition ${
        selected ? "border-[var(--audit-primary-line)] bg-[var(--audit-primary-soft)]" : "border-[var(--audit-line)] bg-white"
      }`}
      onClick={onToggle}
      type="button"
    >
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <h3 className="truncate text-sm font-semibold text-[var(--audit-ink)]">{category.name}</h3>
          <p className="audit-meta mt-1 truncate">{category.sourceCollection}</p>
        </div>
        <StatusPill tone={selected ? "info" : category.scope === "公开知识库" ? "neutral" : "info"}>{category.scope}</StatusPill>
      </div>
      <p className="audit-metric-value-sm mt-3">{category.documentCount.toLocaleString()}</p>
      <p className="audit-copy mt-2">{category.description}</p>
    </button>
  );
}

function DocumentSearchResult({ state }: { readonly state: DocumentSearchState }) {
  if (state.status === "idle") {
    return (
      <section className="audit-panel-muted p-5">
        <h2 className="audit-section-title">等待检索</h2>
        <p className="audit-copy mt-2">提交后会展示后端返回的引用片段、原文入口和证据分组。</p>
      </section>
    );
  }

  if (state.status === "loading") {
    return (
      <section className="audit-panel-muted p-5">
        <h2 className="audit-section-title">正在检索知识库</h2>
        <p className="audit-copy mt-2">后端正在按来源过滤检索可引用材料。</p>
      </section>
    );
  }

  if (state.status === "error") {
    return (
      <section className="rounded-[var(--audit-radius-md)] border border-red-200 bg-red-50 p-5">
        <h2 className="audit-section-title text-red-900">检索未完成</h2>
        <p className="mt-2 text-sm leading-6 text-red-800">{state.message}</p>
      </section>
    );
  }

  const { result } = state;
  const chatHref = `/chat?question=${encodeURIComponent(result.question)}`;
  return (
    <section className="audit-panel-muted p-5">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <p className="audit-kicker">检索结果</p>
          <h2 className="audit-section-title mt-2">{result.question}</h2>
        </div>
        <StatusPill tone={result.citations.length > 0 ? "success" : "warning"}>
          {result.citations.length} 条引用
        </StatusPill>
      </div>
      <p className="audit-copy mt-4">{result.answer}</p>
      <div className="mt-4 flex flex-wrap gap-2">
        <span className="audit-chip">confidence: {result.confidence}</span>
        <span className="audit-chip">fallback: {result.fallback_used ? "yes" : "no"}</span>
        <span className="audit-chip">query_log_index: {result.query_log_index}</span>
      </div>
      <div className="mt-5 space-y-4">
        <div className="space-y-3">
          {result.citations.map((citation) => (
            <DocumentCitationCard citation={citation} key={citation.citation_id} />
          ))}
        </div>
        <aside className="rounded-[var(--audit-radius-md)] border border-[var(--audit-line)] bg-white p-4">
          <h3 className="audit-compact-title">证据分组</h3>
          <div className="mt-3 space-y-3">
            {result.basis_groups.map((group) => (
              <div key={`${group.evidence_type}-${group.title}`}>
                <p className="audit-card-title">{group.title}</p>
                <p className="audit-meta mt-1">
                  {group.evidence_type} / {group.items.length} 条依据
                </p>
              </div>
            ))}
          </div>
          <a className="audit-focus-ring audit-btn audit-btn-primary mt-5" href={chatHref}>
            转入对话审证
          </a>
        </aside>
      </div>
    </section>
  );
}

function DocumentCitationCard({ citation }: { readonly citation: QueryCitation }) {
  return (
    <article className="rounded-[var(--audit-radius-md)] border border-[var(--audit-line)] bg-white p-4">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0">
          <p className="audit-compact-title">
            {citation.marker} / {citation.evidence_type}
          </p>
          <p className="audit-meta mt-1 break-words">{locatorSummary(citation.locator)}</p>
        </div>
        <a
          className="audit-focus-ring audit-btn audit-btn-neutral min-h-8 px-3 py-1.5 text-xs"
          href={`/pages/preview/${citation.chunk_id}`}
        >
          核验原文
        </a>
      </div>
      <p className="audit-copy mt-3">{citation.snippet}</p>
      <p className="mt-3 break-all font-mono text-xs leading-5 text-[var(--audit-ink-subtle)]">chunk: {citation.chunk_id}</p>
    </article>
  );
}

function DocumentList({ title, documents }: { readonly title: string; readonly documents: readonly PortalDocumentItem[] }) {
  return (
    <section className="audit-panel-muted min-w-0 p-4">
      <div className="flex items-center justify-between gap-3">
        <h2 className="audit-section-title">{title}</h2>
        <StatusPill tone="neutral">{documents.length} 份</StatusPill>
      </div>
      <div className="mt-4 space-y-3">
        {documents.map((document) => (
          <article key={document.id} className="rounded-[var(--audit-radius-md)] border border-[var(--audit-line)] bg-white p-4">
            <div className="flex flex-wrap items-start justify-between gap-3">
              <div>
                <h3 className="audit-card-title">{document.title}</h3>
                <p className="audit-meta mt-1">
                  {document.libraryName} / {document.owner} / {document.updatedAt}
                </p>
              </div>
              <StatusPill tone={document.status === "可审证" ? "success" : document.status === "待补引用" ? "warning" : "neutral"}>
                {document.status}
              </StatusPill>
            </div>
            <p className="audit-copy mt-3">{document.summary}</p>
            <div className="mt-4 flex flex-wrap gap-2">
              <a className="audit-focus-ring audit-btn audit-btn-primary" href={document.href}>
                查看引用
              </a>
              <a
                className="audit-focus-ring audit-btn audit-btn-secondary"
                href={document.chatHref}
              >
                转入 AI 对话
              </a>
            </div>
          </article>
        ))}
      </div>
    </section>
  );
}

function Metric({ label, value }: { readonly label: string; readonly value: string }) {
  return (
    <div className="rounded-[var(--audit-radius-md)] border border-[var(--audit-line)] bg-[var(--audit-surface-muted)] p-4">
      <p className="audit-meta font-semibold">{label}</p>
      <p className="audit-metric-value-sm mt-1">{value}</p>
    </div>
  );
}

function isSourceCollection(value: string): value is SourceCollection {
  return SOURCE_COLLECTIONS.includes(value as SourceCollection);
}

function locatorSummary(locator: Record<string, unknown>): string {
  const source = stringValue(locator.source_path) ?? stringValue(locator.file_name) ?? "unknown source";
  const page = numberOrStringValue(locator.page_number);
  const lineStart = numberOrStringValue(locator.line_start);
  const lineEnd = numberOrStringValue(locator.line_end);

  if (page !== undefined) {
    return `${source} / page ${page}`;
  }
  if (lineStart !== undefined) {
    return `${source} / lines ${lineStart}${lineEnd !== undefined ? `-${lineEnd}` : ""}`;
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

"use client";

import { FormEvent, useMemo, useState } from "react";

import { StatusPill } from "@/components/ui/status-pill";
import { isApiClientError, runKnowledgeQuery } from "@/lib/api-client";
import type { QueryBasisItem, QueryCitation, QueryResponse, SourceCollection } from "@/lib/api-types";

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
  const [yearFilter, setYearFilter] = useState("");
  const [regionFilter, setRegionFilter] = useState("");
  const [documentTypeFilter, setDocumentTypeFilter] = useState("");
  const [businessTopicFilter, setBusinessTopicFilter] = useState("");
  const [queryState, setQueryState] = useState<QueryState>({ status: "idle" });

  const chatHref = useMemo(() => {
    const params = new URLSearchParams();
    params.set("question", question);
    for (const collection of selectedCollections) {
      params.append("source_collection", collection);
    }
    for (const year of parseYearFilter(yearFilter)) {
      params.append("year", String(year));
    }
    for (const region of parseListFilter(regionFilter)) {
      params.append("region", region);
    }
    for (const documentType of parseListFilter(documentTypeFilter)) {
      params.append("document_type", documentType);
    }
    for (const businessTopic of parseListFilter(businessTopicFilter)) {
      params.append("business_topic", businessTopic);
    }
    return `/chat?${params.toString()}`;
  }, [businessTopicFilter, documentTypeFilter, question, regionFilter, selectedCollections, yearFilter]);

  async function submitQuery(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const normalizedQuestion = question.trim();

    if (!normalizedQuestion) {
      setQueryState({ status: "error", message: "请输入需要检索的医保审核问题。" });
      return;
    }

    setQueryState({ status: "loading" });
    try {
      const years = parseYearFilter(yearFilter);
      const regions = parseListFilter(regionFilter);
      const documentTypes = parseListFilter(documentTypeFilter);
      const businessTopics = parseListFilter(businessTopicFilter);
      const result = await runKnowledgeQuery({
        question: normalizedQuestion,
        top_k: 5,
        source_collections: selectedCollections,
        ...(years.length > 0 ? { years } : {}),
        ...(regions.length > 0 ? { regions } : {}),
        ...(documentTypes.length > 0 ? { document_types: documentTypes } : {}),
        ...(businessTopics.length > 0 ? { business_topics: businessTopics } : {}),
        topic: "medical-insurance-fund"
      });
      setQueryState({ status: "success", result });
    } catch (error) {
      if (shouldUseLocalQueryFallback(error)) {
        setQueryState({
          status: "success",
          result: buildLocalQueryFallback(normalizedQuestion, selectedCollections)
        });
        return;
      }
      setQueryState({ status: "error", message: queryErrorMessage(error) });
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
              输入审计问题后，系统会按法规政策、监管规则、医保目录和风险清单整理证据线索。进入底稿前仍需人工复核。
            </p>
          </div>
          <StatusPill tone="info">引用优先</StatusPill>
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
            <p className="audit-meta">
              不勾选来源时，将在当前可访问的全部知识范围内检索。
            </p>
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
                        aria-label={`${option.label} 来源`}
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

          <fieldset className="space-y-3">
            <legend className="audit-label">精细过滤</legend>
            <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-4">
              <FilterInput
                label="年份"
                onChange={setYearFilter}
                placeholder="2024, 2025"
                value={yearFilter}
              />
              <FilterInput
                label="地区"
                onChange={setRegionFilter}
                placeholder="国家, 广东"
                value={regionFilter}
              />
              <FilterInput
                label="文档类型"
                onChange={setDocumentTypeFilter}
                placeholder="法规, 目录"
                value={documentTypeFilter}
              />
              <FilterInput
                label="业务主题"
                onChange={setBusinessTopicFilter}
                placeholder="基金监管, 支付限制"
                value={businessTopicFilter}
              />
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
              href="/documents"
            >
              回到文档依据
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

      <div className="audit-panel-muted mt-4 p-4">
        <p className="audit-card-title">实际检索范围</p>
        <div className="mt-3 flex flex-wrap gap-2">
          {result.effective_source_collections.map((collection) => (
            <span className="audit-chip" key={collection}>
              {collection}
            </span>
          ))}
        </div>
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
  const indexVersion = citation.index_version_key ?? "n/a";
  const packageVersion = citation.source_package_version_key ?? "n/a";

  return (
    <article className="p-4">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <p className="audit-compact-title">
            {citation.marker} · {citation.evidence_type}
          </p>
          <p className="mt-1 audit-meta">来源: {citation.source_collection}</p>
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
      <dl className="mt-3 grid gap-2 text-xs leading-5 text-[var(--audit-ink-subtle)] sm:grid-cols-2">
        <div>
          <dt className="audit-meta">index</dt>
          <dd className="break-all font-mono">{indexVersion}</dd>
        </div>
        <div>
          <dt className="audit-meta">package</dt>
          <dd className="break-all font-mono">{packageVersion}</dd>
        </div>
        <div className="sm:col-span-2">
          <dt className="audit-meta">chunk</dt>
          <dd className="break-all font-mono">{citation.chunk_id}</dd>
        </div>
      </dl>
    </article>
  );
}

function queryErrorMessage(error: unknown): string {
  if (!isApiClientError(error)) {
    return "查询未完成。请确认检索服务可用后重试。";
  }
  if (error.code === "search-engine-not-initialized") {
    return "检索服务尚未就绪。请先完成索引加载后再查询。";
  }
  if (error.code === "no-cited-evidence") {
    return "未找到可引用证据。请调整问题、来源或过滤条件后重试。";
  }
  if (error.code === "unknown-topic") {
    return "查询主题不受支持。请清空主题或选择已配置的医保基金主题。";
  }
  if (error.code === "source-collection-denied") {
    return "当前账号没有访问所选知识库的权限。请调整来源范围或联系管理员。";
  }
  return `查询暂未完成。当前状态 ${error.status}，请稍后重试或调整筛选条件。`;
}

function shouldUseLocalQueryFallback(error: unknown): boolean {
  if (!isApiClientError(error)) {
    return true;
  }
  return (
    error.code === "backend-request-failed" ||
    error.code === "search-engine-not-initialized" ||
    error.status === 404 ||
    error.status >= 500
  );
}

function buildLocalQueryFallback(
  question: string,
  selectedCollections: readonly SourceCollection[]
): QueryResponse {
  const effectiveCollections =
    selectedCollections.length > 0
      ? selectedCollections
      : SOURCE_COLLECTION_OPTIONS.map((option) => option.value);
  const citations = effectiveCollections.slice(0, 3).map((collection, index): QueryCitation => {
    const option = SOURCE_COLLECTION_OPTIONS.find((item) => item.value === collection);
    return {
      citation_id: `local-preview-${collection}-${index + 1}`,
      marker: `[${index + 1}]`,
      chunk_id: `local-preview-${collection}`,
      evidence_type: option?.label ?? "本地预览",
      source_collection: collection,
      snippet: `${option?.label ?? "知识库"}用于审计问题的本地预览核验。正式进入底稿前，需要连接生产检索服务并复核原文引用。`,
      locator: {
        source_path: option?.label ?? collection,
        preview_mode: true
      },
      index_version_key: "local-preview",
      source_package_version_key: "local-preview"
    };
  });
  const basisItems: readonly QueryBasisItem[] = citations.map((citation) => ({
    citation_id: citation.citation_id,
    chunk_id: citation.chunk_id,
    source_collection: citation.source_collection,
    snippet: citation.snippet,
    locator: citation.locator,
    index_version_key: citation.index_version_key,
    source_package_version_key: citation.source_package_version_key
  }));

  return {
    question,
    answer:
      "当前为本地重构站预览结果：系统会先按法规政策、监管规则、医保目录和风险清单组织证据方向，再由审计人员核验原文后进入底稿。生产检索服务接通后将替换为真实引用结果。",
    confidence: "local-preview",
    fallback_used: true,
    effective_source_collections: effectiveCollections,
    basis_groups: [
      {
        evidence_type: "local-preview",
        title: "本地预览依据",
        items: basisItems
      }
    ],
    citations,
    personal_upload_matches: [],
    query_log_index: 0,
    query_log_id: null,
    agent_invocation_id: null
  };
}

function FilterInput({
  label,
  onChange,
  placeholder,
  value
}: {
  readonly label: string;
  readonly onChange: (value: string) => void;
  readonly placeholder: string;
  readonly value: string;
}) {
  const id = `knowledge-query-filter-${label}`;

  return (
    <label className="block" htmlFor={id}>
      <span className="audit-label">{label}</span>
      <input
        id={id}
        className="audit-focus-ring audit-input mt-2 px-3 py-2"
        onChange={(event) => onChange(event.target.value)}
        placeholder={placeholder}
        value={value}
      />
    </label>
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

function parseListFilter(value: string): readonly string[] {
  return value
    .split(/[,，\n]/)
    .map((item) => item.trim())
    .filter(Boolean);
}

function parseYearFilter(value: string): readonly number[] {
  return parseListFilter(value)
    .map((item) => Number(item))
    .filter((item) => Number.isInteger(item) && item > 0);
}

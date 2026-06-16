"use client";

import { FormEvent, useCallback, useEffect, useMemo, useState } from "react";

import { StatusPill } from "@/components/ui/status-pill";
import {
  fetchDocumentPermissions,
  fetchDocumentUploads,
  fetchQueryHistory,
  runKnowledgeQuery,
  uploadPersonalDocument
} from "@/lib/api-client";
import type {
  DocumentIndexReadinessBlocker,
  DocumentPermissionsResponse,
  DocumentUploadItem,
  QueryCitation,
  QueryHistoryItem,
  QueryResponse,
  SourceCollection
} from "@/lib/api-types";
import {
  conversationDocuments,
  documentCategoryStats,
  knowledgeDocuments,
  PortalDocumentItem
} from "@/lib/portal-data";

type DocumentSearchState =
  | { readonly status: "idle" }
  | { readonly status: "loading" }
  | { readonly status: "success"; readonly result: QueryResponse }
  | { readonly status: "error"; readonly message: string };
type HistoryStatus = "loading" | "ready" | "unavailable";
type PermissionStatus = "loading" | "ready" | "unavailable";
type UploadStatus = "loading" | "ready" | "uploading" | "unavailable";

const SOURCE_COLLECTIONS: readonly SourceCollection[] = [
  "medical-insurance-laws",
  "supervision-rules-knowledge",
  "medical-insurance-catalog",
  "risk-negative-list"
];
const INDEX_READINESS_BLOCKER_LABELS: Record<DocumentIndexReadinessBlocker, string> = {
  "virus-scan-required": "待病毒扫描",
  "dlp-review-required": "待脱敏审查",
  "manual-index-approval-required": "待入索引审批",
  "manual-index-approval-rejected": "入索引已驳回"
};

export default function DocumentsPage() {
  const totalDocuments = documentCategoryStats.reduce((sum, category) => sum + category.documentCount, 0);
  const [query, setQuery] = useState("");
  const [selectedCollections, setSelectedCollections] = useState<readonly SourceCollection[]>([]);
  const [searchState, setSearchState] = useState<DocumentSearchState>({ status: "idle" });
  const [history, setHistory] = useState<readonly QueryHistoryItem[]>([]);
  const [historyStatus, setHistoryStatus] = useState<HistoryStatus>("loading");
  const [documentPermissions, setDocumentPermissions] = useState<DocumentPermissionsResponse | null>(null);
  const [permissionStatus, setPermissionStatus] = useState<PermissionStatus>("loading");
  const [uploads, setUploads] = useState<readonly DocumentUploadItem[]>([]);
  const [uploadStatus, setUploadStatus] = useState<UploadStatus>("loading");
  const [selectedUploadFile, setSelectedUploadFile] = useState<File | null>(null);
  const [uploadMessage, setUploadMessage] = useState("");

  const refreshHistory = useCallback(async () => {
    setHistoryStatus("loading");
    try {
      const result = await fetchQueryHistory();
      setHistory(result.items);
      setHistoryStatus(result.store.ready ? "ready" : "unavailable");
    } catch {
      setHistory([]);
      setHistoryStatus("unavailable");
    }
  }, []);

  const refreshDocumentPermissions = useCallback(async () => {
    setPermissionStatus("loading");
    try {
      const result = await fetchDocumentPermissions();
      setDocumentPermissions(result);
      setPermissionStatus("ready");
    } catch {
      setDocumentPermissions(null);
      setPermissionStatus("unavailable");
    }
  }, []);

  const refreshDocumentUploads = useCallback(async () => {
    setUploadStatus("loading");
    try {
      const result = await fetchDocumentUploads();
      setUploads(result.items);
      setUploadStatus(result.store.ready ? "ready" : "unavailable");
    } catch {
      setUploads([]);
      setUploadStatus("unavailable");
    }
  }, []);

  useEffect(() => {
    void refreshHistory();
    void refreshDocumentPermissions();
    void refreshDocumentUploads();
  }, [refreshDocumentPermissions, refreshDocumentUploads, refreshHistory]);

  const readableCollections = useMemo(() => {
    if (documentPermissions === null) {
      return new Set<SourceCollection>(SOURCE_COLLECTIONS);
    }
    return new Set(
      documentPermissions.source_collections
        .filter((item) => item.access === "read")
        .map((item) => item.source_collection)
    );
  }, [documentPermissions]);

  const selectedScopeText = useMemo(() => {
    if (selectedCollections.length === 0) {
      return "全部来源";
    }
    return documentCategoryStats
      .filter((category) => selectedCollections.includes(category.sourceCollection as SourceCollection))
      .map((category) => category.name)
      .join("、");
  }, [selectedCollections]);

  const canUploadPersonal =
    permissionStatus === "ready" && (documentPermissions?.upload_permissions.can_upload_personal ?? false);

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
      await refreshHistory();
    } catch {
      setSearchState({ status: "error", message: "检索失败。请确认后端检索已就绪后重试。" });
    }
  }

  function toggleCollection(sourceCollection: string) {
    if (!isSourceCollection(sourceCollection)) {
      return;
    }
    if (!readableCollections.has(sourceCollection)) {
      return;
    }
    setSelectedCollections((current) =>
      current.includes(sourceCollection)
        ? current.filter((item) => item !== sourceCollection)
        : [...current, sourceCollection]
    );
  }

  function runHistorySearch(item: QueryHistoryItem) {
    setQuery(item.question);
    setSelectedCollections(historySourceCollections(item));
    setSearchState({ status: "idle" });
  }

  async function submitDocumentUpload(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!selectedUploadFile) {
      setUploadMessage("请选择个人材料文件。");
      return;
    }

    setUploadStatus("uploading");
    setUploadMessage("");
    try {
      const result = await uploadPersonalDocument(selectedUploadFile);
      setUploadMessage(`${result.item.name} 已留存，入索引门禁：${indexReadinessText(result.item)}`);
      setSelectedUploadFile(null);
      await refreshDocumentUploads();
    } catch {
      setUploadStatus("unavailable");
      setUploadMessage("个人材料留存失败。");
    }
  }

  return (
    <main className="grid min-w-0 gap-4 xl:grid-cols-[17rem_minmax(0,1fr)_18rem]">
      <aside className="audit-panel-rail min-w-0 p-5">
        <div className="flex items-start justify-between gap-3">
          <h2 className="audit-section-title">文档源</h2>
          <StatusPill tone={permissionStatus === "ready" ? "success" : permissionStatus === "loading" ? "info" : "warning"}>
            {permissionStatus === "ready" ? "权限已连接" : permissionStatus === "loading" ? "读取中" : "权限不可用"}
          </StatusPill>
        </div>
        <p className="audit-copy mt-2">按审计材料来源限定后端检索范围。</p>
        <div className="mt-5 space-y-3">
          {documentCategoryStats.map((category) => (
            <DocumentSourceCard
              category={category}
              readable={readableCollections.has(category.sourceCollection as SourceCollection)}
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
        <DocumentUploadPanel
          canUpload={canUploadPersonal}
          message={uploadMessage}
          onFileChange={setSelectedUploadFile}
          onSubmit={submitDocumentUpload}
          selectedFile={selectedUploadFile}
          status={uploadStatus}
          uploads={uploads}
        />

        <section className="audit-panel-rail p-5">
          <div className="flex items-start justify-between gap-3">
            <h2 className="audit-section-title">搜索历史</h2>
            <StatusPill tone={historyStatus === "ready" ? "success" : historyStatus === "loading" ? "info" : "warning"}>
              {historyStatus === "ready" ? "已连接" : historyStatus === "loading" ? "读取中" : "不可用"}
            </StatusPill>
          </div>
          <div className="mt-4 space-y-2">
            {history.length > 0 ? (
              history.map((item) => (
                <button
                  className="audit-focus-ring block w-full rounded-[var(--audit-radius-md)] bg-[var(--audit-surface-muted)] px-3 py-2 text-left hover:bg-[var(--audit-surface-subtle)]"
                  key={item.id}
                  onClick={() => runHistorySearch(item)}
                  type="button"
                >
                  <span className="block truncate text-sm font-semibold text-[var(--audit-ink)]">{item.question}</span>
                  <span className="audit-meta mt-1 block">
                    {item.citation_count} 条引用 / {formatDateTime(item.created_at)}
                  </span>
                </button>
              ))
            ) : (
              <p className="audit-copy">暂无持久化搜索记录。</p>
            )}
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
  readable,
  selected
}: {
  readonly category: (typeof documentCategoryStats)[number];
  readonly onToggle: () => void;
  readonly readable: boolean;
  readonly selected: boolean;
}) {
  return (
    <button
      aria-pressed={selected}
      disabled={!readable}
      className={`audit-focus-ring w-full rounded-[var(--audit-radius-md)] border p-3 text-left transition ${
        selected ? "border-[var(--audit-primary-line)] bg-[var(--audit-primary-soft)]" : "border-[var(--audit-line)] bg-white"
      } ${readable ? "hover:bg-[var(--audit-surface-muted)]" : "cursor-not-allowed opacity-55"
      }`}
      onClick={onToggle}
      type="button"
    >
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <h3 className="truncate text-sm font-semibold text-[var(--audit-ink)]">{category.name}</h3>
          <p className="audit-meta mt-1 truncate">{category.sourceCollection}</p>
        </div>
        <StatusPill tone={!readable ? "warning" : selected ? "info" : category.scope === "公开知识库" ? "neutral" : "info"}>
          {readable ? category.scope : "无权限"}
        </StatusPill>
      </div>
      <p className="audit-metric-value-sm mt-3">{category.documentCount.toLocaleString()}</p>
      <p className="audit-copy mt-2">{category.description}</p>
    </button>
  );
}

function DocumentUploadPanel({
  canUpload,
  message,
  onFileChange,
  onSubmit,
  selectedFile,
  status,
  uploads
}: {
  readonly canUpload: boolean;
  readonly message: string;
  readonly onFileChange: (file: File | null) => void;
  readonly onSubmit: (event: FormEvent<HTMLFormElement>) => void;
  readonly selectedFile: File | null;
  readonly status: UploadStatus;
  readonly uploads: readonly DocumentUploadItem[];
}) {
  return (
    <section className="audit-panel-rail p-5">
      <div className="flex items-start justify-between gap-3">
        <h2 className="audit-section-title">个人材料</h2>
        <StatusPill tone={status === "ready" ? "success" : status === "uploading" || status === "loading" ? "info" : "warning"}>
          {status === "ready" ? "已连接" : status === "uploading" ? "留存中" : status === "loading" ? "读取中" : "不可用"}
        </StatusPill>
      </div>

      <form className="mt-4 space-y-3" onSubmit={onSubmit}>
        <label className="block" htmlFor="personal-document-upload">
          <span className="audit-label">个人材料文件</span>
          <input
            accept=".pdf,.md,.txt,.csv,.xlsx,.xlsm"
            aria-label="上传个人知识库材料"
            className="audit-focus-ring mt-2 block w-full rounded-[var(--audit-radius-md)] border border-[var(--audit-line)] bg-white px-3 py-2 text-sm text-[var(--audit-ink)] file:mr-3 file:rounded-[var(--audit-radius-sm)] file:border-0 file:bg-[var(--audit-primary-soft)] file:px-3 file:py-1.5 file:text-xs file:font-semibold file:text-[var(--audit-primary)]"
            disabled={!canUpload || status === "uploading"}
            id="personal-document-upload"
            onChange={(event) => onFileChange(event.target.files?.[0] ?? null)}
            type="file"
          />
        </label>
        <button
          className="audit-focus-ring audit-btn audit-btn-primary w-full"
          disabled={!canUpload || status === "uploading" || selectedFile === null}
          type="submit"
        >
          {status === "uploading" ? "留存中" : "上传材料"}
        </button>
        {message ? <p className="audit-meta break-words">{message}</p> : null}
      </form>

      <div className="mt-5 space-y-2">
        {uploads.length > 0 ? (
          uploads.map((item) => <DocumentUploadRow item={item} key={item.id} />)
        ) : (
          <p className="audit-copy">暂无个人材料留存。</p>
        )}
      </div>
    </section>
  );
}

function DocumentUploadRow({ item }: { readonly item: DocumentUploadItem }) {
  return (
    <article className="rounded-[var(--audit-radius-md)] border border-[var(--audit-line)] bg-[var(--audit-surface-muted)] p-3">
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <h3 className="truncate text-sm font-semibold text-[var(--audit-ink)]">{item.name}</h3>
          <p className="audit-meta mt-1">
            {item.extension.toUpperCase()} / {item.size_kb} KB / {formatDateTime(item.created_at)}
          </p>
        </div>
        <StatusPill tone="warning">待治理</StatusPill>
      </div>
      <p className="audit-meta mt-2">入索引门禁：{indexReadinessText(item)}</p>
    </article>
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
          <p className="audit-meta mt-1">来源: {citation.source_collection}</p>
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

function historySourceCollections(item: QueryHistoryItem): readonly SourceCollection[] {
  const sourceCollections = item.filters.source_collections;
  if (!Array.isArray(sourceCollections)) {
    return [];
  }
  return sourceCollections.filter((value): value is SourceCollection =>
    typeof value === "string" && isSourceCollection(value)
  );
}

function formatDateTime(value: string): string {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return value;
  }
  return date.toLocaleString("zh-CN", {
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit"
  });
}

function indexReadinessText(item: DocumentUploadItem): string {
  if (item.index_readiness.blockers.length === 0) {
    return item.index_status;
  }
  return item.index_readiness.blockers.map((blocker) => INDEX_READINESS_BLOCKER_LABELS[blocker]).join("、");
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

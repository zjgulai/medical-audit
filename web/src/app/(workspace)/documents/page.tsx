"use client";

import { FormEvent, useCallback, useEffect, useMemo, useState } from "react";

import { StatusPill } from "@/components/ui/status-pill";
import {
  fetchDocumentPermissions,
  fetchDocumentUploads,
  fetchQueryHistory,
  indexPersonalDocument,
  runKnowledgeQuery,
  updateDocumentUploadGovernance,
  uploadPersonalDocument
} from "@/lib/api-client";
import type {
  DocumentPermissionsResponse,
  DocumentUploadItem,
  PersonalUploadMatch,
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
type DocumentGovernanceAction = DocumentUploadItem["governance_status"];

const SOURCE_COLLECTIONS: readonly SourceCollection[] = [
  "medical-insurance-laws",
  "supervision-rules-knowledge",
  "medical-insurance-catalog",
  "risk-negative-list"
];

export default function DocumentsPage() {
  const totalDocuments = documentCategoryStats.reduce((sum, category) => sum + category.documentCount, 0);
  const [query, setQuery] = useState("");
  const [titleOnly, setTitleOnly] = useState(false);
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
  const canGovernPersonalUploads =
    permissionStatus === "ready" && (documentPermissions?.upload_permissions.can_govern_personal_uploads ?? false);
  const filteredConversationDocuments = filterPortalDocuments(conversationDocuments, query, titleOnly);
  const filteredKnowledgeDocuments = filterPortalDocuments(knowledgeDocuments, query, titleOnly);

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
        source_collections: selectedCollections,
        title_only: titleOnly,
        topic: "medical-insurance-fund"
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
      setUploadMessage(`${result.item.name} 已留存，治理状态：${governanceStatusLabel(result.item.governance_status)}`);
      setSelectedUploadFile(null);
      await refreshDocumentUploads();
    } catch {
      setUploadStatus("unavailable");
      setUploadMessage("个人材料留存失败。");
    }
  }

  async function updateUploadGovernance(uploadId: string, governanceStatus: DocumentGovernanceAction) {
    setUploadStatus("uploading");
    setUploadMessage("");
    try {
      const result = await updateDocumentUploadGovernance(uploadId, {
        governance_status: governanceStatus,
        note: governanceNoteForStatus(governanceStatus)
      });
      setUploadMessage(`${result.item.name} 已更新为：${governanceStatusLabel(result.item.governance_status)}`);
      await refreshDocumentUploads();
    } catch {
      setUploadStatus("unavailable");
      setUploadMessage("材料治理状态更新失败。");
    }
  }

  async function indexUpload(uploadId: string) {
    setUploadStatus("uploading");
    setUploadMessage("");
    try {
      const result = await indexPersonalDocument(uploadId);
      setUploadMessage(
        `${result.item.name} 本地入索引状态：${personalIndexStatusLabel(result.item.personal_index_status)}`
      );
      await refreshDocumentUploads();
    } catch {
      setUploadStatus("unavailable");
      setUploadMessage("材料入索引任务执行失败。");
    }
  }

  return (
    <main className="mx-auto grid max-w-6xl min-w-0 gap-4">
      <section className="audit-panel-rail min-w-0 p-4 sm:p-5">
        <div className="flex items-start justify-between gap-3">
          <div>
            <p className="audit-kicker">依据范围</p>
            <h2 className="audit-section-title mt-1">选择检索来源</h2>
          </div>
          <StatusPill tone={permissionStatus === "ready" ? "success" : permissionStatus === "loading" ? "info" : "warning"}>
            {permissionStatus === "ready" ? "可用" : permissionStatus === "loading" ? "读取中" : "需登录"}
          </StatusPill>
        </div>
        <div className="mt-4 grid gap-2 sm:grid-cols-2 lg:grid-cols-4">
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
      </section>

      <section className="audit-panel min-w-0 p-5 sm:p-6">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div className="min-w-0">
            <p className="audit-kicker">文档依据</p>
            <h1 className="audit-page-title">文档依据检索</h1>
            <p className="audit-copy mt-2 max-w-2xl">输入审计问题，先找可引用材料，再进入对话或底稿环节。</p>
          </div>
          <div className="flex flex-wrap gap-2">
            <StatusPill tone={searchState.status === "success" ? "success" : "info"}>依据优先</StatusPill>
            <StatusPill tone="neutral">需人工复核</StatusPill>
          </div>
        </div>

        <form className="audit-panel-muted mt-5 p-4 sm:p-5" onSubmit={submitSearch}>
          <label className="block" htmlFor="document-query">
            <span className="audit-label">审计问题或文档关键词</span>
            <textarea
              className="audit-focus-ring audit-input mt-2 min-h-20 resize-y px-3 py-2.5 leading-6"
              id="document-query"
              onChange={(event) => setQuery(event.target.value)}
              placeholder="例如：重复收费、目录限制、超量开药"
              value={query}
            />
          </label>
          <div className="mt-4 flex flex-wrap items-center justify-between gap-3 rounded-[var(--audit-radius-md)] border border-[var(--audit-line)] bg-white px-3 py-2">
            <label className="audit-focus-ring flex cursor-pointer items-center gap-2 rounded-[var(--audit-radius-sm)] px-1 py-1 text-sm font-semibold text-[var(--audit-ink)]">
              <input
                checked={titleOnly}
                className="h-4 w-4 accent-[var(--audit-primary)]"
                onChange={(event) => setTitleOnly(event.target.checked)}
                type="checkbox"
              />
              仅标题
            </label>
            <p className="audit-meta">
              {titleOnly ? "只按标题找材料。" : "按标题、摘要和正文线索找材料。"}
            </p>
          </div>
          <div className="mt-4 flex flex-wrap items-center justify-between gap-3">
            <div className="audit-meta">检索范围：{selectedScopeText}</div>
            <div className="flex flex-wrap gap-3">
              <button className="audit-focus-ring audit-btn audit-btn-primary" disabled={searchState.status === "loading"} type="submit">
                {searchState.status === "loading" ? "检索中" : "执行检索"}
              </button>
              <a
                className="audit-focus-ring audit-btn audit-btn-secondary"
                href={`/chat${query.trim() ? `?question=${encodeURIComponent(query.trim())}` : ""}`}
              >
                转入对话
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
          <Metric label="检索模式" value={titleOnly ? "仅标题" : "全文"} />
        </div>

        <div className="mt-6">
          <DocumentSearchResult state={searchState} />
        </div>

        <div className="mt-6 grid gap-5 lg:grid-cols-2">
          <DocumentList title="对话文档" documents={filteredConversationDocuments} />
          <DocumentList title="知识库文档" documents={filteredKnowledgeDocuments} />
        </div>
      </section>

      <section className="grid min-w-0 gap-4 lg:grid-cols-2">
        <DocumentUploadPanel
          canUpload={canUploadPersonal}
          canGovern={canGovernPersonalUploads}
          message={uploadMessage}
          onGovernanceUpdate={updateUploadGovernance}
          onFileChange={setSelectedUploadFile}
          onIndex={indexUpload}
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
        </a>

        <a className="audit-focus-ring audit-callout block p-5" href="/chat">
          <p className="audit-kicker">审计问答</p>
          <h2 className="audit-section-title mt-2">带着材料进入审证</h2>
        </a>
      </section>
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
      <div className="flex items-center justify-between gap-3">
        <h3 className="min-w-0 truncate text-sm font-semibold text-[var(--audit-ink)]">{category.name}</h3>
        <StatusPill tone={!readable ? "warning" : selected ? "info" : category.scope === "公开知识库" ? "neutral" : "info"}>
          {readable ? category.scope : "无权限"}
        </StatusPill>
      </div>
      <p className="audit-metric-value-sm mt-2">{category.documentCount.toLocaleString()}</p>
    </button>
  );
}

function DocumentUploadPanel({
  canUpload,
  canGovern,
  message,
  onGovernanceUpdate,
  onFileChange,
  onIndex,
  onSubmit,
  selectedFile,
  status,
  uploads
}: {
  readonly canUpload: boolean;
  readonly canGovern: boolean;
  readonly message: string;
  readonly onGovernanceUpdate: (uploadId: string, governanceStatus: DocumentGovernanceAction) => void;
  readonly onFileChange: (file: File | null) => void;
  readonly onIndex: (uploadId: string) => void;
  readonly onSubmit: (event: FormEvent<HTMLFormElement>) => void;
  readonly selectedFile: File | null;
  readonly status: UploadStatus;
  readonly uploads: readonly DocumentUploadItem[];
}) {
  return (
    <section className="audit-panel-rail min-w-0 overflow-hidden p-5">
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
            className="audit-focus-ring mt-2 block w-full min-w-0 max-w-full rounded-[var(--audit-radius-md)] border border-[var(--audit-line)] bg-white px-3 py-2 text-sm text-[var(--audit-ink)] file:mr-3 file:rounded-[var(--audit-radius-sm)] file:border-0 file:bg-[var(--audit-primary-soft)] file:px-3 file:py-1.5 file:text-xs file:font-semibold file:text-[var(--audit-primary)]"
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

      <div className="mt-5 min-w-0 space-y-2 overflow-hidden">
        {uploads.length > 0 ? (
          uploads.map((item) => (
            <DocumentUploadRow
              canGovern={canGovern}
              item={item}
              key={item.id}
              onGovernanceUpdate={onGovernanceUpdate}
              onIndex={onIndex}
              updating={status === "uploading"}
            />
          ))
        ) : (
          <p className="audit-copy">暂无个人材料留存。</p>
        )}
      </div>
    </section>
  );
}

function DocumentUploadRow({
  canGovern,
  item,
  onGovernanceUpdate,
  onIndex,
  updating
}: {
  readonly canGovern: boolean;
  readonly item: DocumentUploadItem;
  readonly onGovernanceUpdate: (uploadId: string, governanceStatus: DocumentGovernanceAction) => void;
  readonly onIndex: (uploadId: string) => void;
  readonly updating: boolean;
}) {
  return (
    <article className="min-w-0 overflow-hidden rounded-[var(--audit-radius-md)] border border-[var(--audit-line)] bg-[var(--audit-surface-muted)] p-3">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0 overflow-hidden">
          <h3 className="block max-w-full truncate text-sm font-semibold text-[var(--audit-ink)]">{item.name}</h3>
          <p className="audit-meta mt-1">
            {item.extension.toUpperCase()} / {item.size_kb} KB / {formatDateTime(item.created_at)}
          </p>
          <p className="audit-meta mt-1 break-all">上传人：{item.created_by ?? "unknown"}</p>
          <p className="audit-meta mt-1">
            安全：{securityStatusLabel(item.security_scan_status)} / DLP：{dlpStatusLabel(item.dlp_status)}
          </p>
          <p className="audit-meta mt-1">
            本地索引：{personalIndexStatusLabel(item.personal_index_status)}
            {item.personal_index_chunk_count > 0 ? ` / ${item.personal_index_chunk_count} 块` : ""}
          </p>
          {item.personal_index_error ? (
            <p className="audit-meta mt-1 break-words">索引提示：{item.personal_index_error}</p>
          ) : null}
          {item.governance_note ? <p className="audit-meta mt-1 break-words">{item.governance_note}</p> : null}
          {item.security_findings.length > 0 ? (
            <p className="audit-meta mt-1 break-words">治理提示：{item.security_findings.join("、")}</p>
          ) : null}
        </div>
        <div className="flex shrink-0 flex-col items-end gap-2">
          <StatusPill tone={governanceStatusTone(item.governance_status)}>
            {governanceStatusLabel(item.governance_status)}
          </StatusPill>
          <span className="audit-meta">{indexStatusLabel(item.index_status)}</span>
        </div>
      </div>
      {canGovern ? (
        <div className="mt-3 flex flex-wrap gap-2">
          <button
            className="audit-focus-ring audit-btn audit-btn-secondary min-h-8 px-3 py-1.5 text-xs"
            disabled={updating || item.governance_status === "approved-for-index"}
            onClick={() => onGovernanceUpdate(item.id, "approved-for-index")}
            type="button"
          >
            准入索引
          </button>
          <button
            className="audit-focus-ring audit-btn audit-btn-neutral min-h-8 px-3 py-1.5 text-xs"
            disabled={updating || item.governance_status === "blocked"}
            onClick={() => onGovernanceUpdate(item.id, "blocked")}
            type="button"
          >
            阻断
          </button>
          <button
            className="audit-focus-ring audit-btn audit-btn-neutral min-h-8 px-3 py-1.5 text-xs"
            disabled={updating || item.governance_status === "pending-review"}
            onClick={() => onGovernanceUpdate(item.id, "pending-review")}
            type="button"
          >
            退回复核
          </button>
          <button
            className="audit-focus-ring audit-btn audit-btn-secondary min-h-8 px-3 py-1.5 text-xs"
            disabled={updating || !canRunPersonalIndex(item)}
            onClick={() => onIndex(item.id)}
            type="button"
          >
            入索引
          </button>
        </div>
      ) : null}
      <a
        className="audit-focus-ring audit-btn audit-btn-secondary mt-3 min-h-8 px-3 py-1.5 text-xs"
        href={item.download_url}
      >
        下载留存文件
      </a>
    </article>
  );
}

function DocumentSearchResult({ state }: { readonly state: DocumentSearchState }) {
  if (state.status === "idle") {
    return (
      <section className="audit-panel-muted p-5">
        <h2 className="audit-section-title">等待检索</h2>
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
  const citationGroups = groupCitationsBySource(result.citations);
  const personalMatches = result.personal_upload_matches ?? [];
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
      {result.citations.length === 0 ? (
        <div className="mt-4 rounded-[var(--audit-radius-md)] border border-amber-200 bg-amber-50 p-4">
          <h3 className="audit-compact-title text-amber-950">引用不足</h3>
          <p className="mt-2 text-sm leading-6 text-amber-900">
            当前检索未返回可核验引用，只能作为补证线索，不能直接形成审计结论。
          </p>
        </div>
      ) : null}
      <div className="mt-4 flex flex-wrap gap-2">
        <span className="audit-chip">可信度：{result.confidence}</span>
        <span className="audit-chip">补证模式：{result.fallback_used ? "已启用" : "未启用"}</span>
        <span className="audit-chip">检索记录：{result.query_log_index}</span>
        <span className="audit-chip">个人材料: {personalMatches.length}</span>
      </div>
      <div className="mt-5 space-y-4">
        {personalMatches.length > 0 ? (
          <section className="rounded-[var(--audit-radius-md)] border border-[var(--audit-primary-line)] bg-white p-4">
            <div className="flex flex-wrap items-center justify-between gap-3">
              <div>
                <h3 className="audit-compact-title">个人材料命中</h3>
                <p className="audit-meta mt-1">仅作为当前权限下的补证线索，不替代法规引用。</p>
              </div>
              <StatusPill tone="info">{personalMatches.length} 条</StatusPill>
            </div>
            <div className="mt-3 space-y-3">
              {personalMatches.map((match) => (
                <DocumentPersonalMatchCard key={match.id} match={match} />
              ))}
            </div>
          </section>
        ) : null}
        <div className="space-y-3">
          {citationGroups.map((group) => (
            <section className="rounded-[var(--audit-radius-md)] border border-[var(--audit-line)] bg-white p-4" key={group.sourceCollection}>
              <div className="flex flex-wrap items-center justify-between gap-3">
                <div>
                  <h3 className="audit-compact-title">引用分组：{group.label}</h3>
                  <p className="audit-meta mt-1">按来源归并引用。</p>
                </div>
                <StatusPill tone="neutral">{group.citations.length} 条引用</StatusPill>
              </div>
              <div className="mt-3 space-y-3">
                {group.citations.map((citation) => (
                  <DocumentCitationCard citation={citation} key={citation.citation_id} />
                ))}
              </div>
            </section>
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
            转入对话
          </a>
        </aside>
      </div>
    </section>
  );
}

function DocumentPersonalMatchCard({ match }: { readonly match: PersonalUploadMatch }) {
  return (
    <article className="rounded-[var(--audit-radius-md)] border border-[var(--audit-line)] bg-[var(--audit-surface-muted)] p-4">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0">
          <p className="audit-compact-title">{match.name}</p>
          <p className="audit-meta mt-1">
            {match.extension.toUpperCase()} / 片段 {match.chunk_index + 1} / 匹配度 {match.score}
          </p>
          <p className="audit-meta mt-1 break-words">{locatorSummary(match.locator)}</p>
        </div>
        <StatusPill tone="info">个人材料</StatusPill>
      </div>
      <p className="audit-copy mt-3">{match.snippet}</p>
    </article>
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
          <p className="audit-meta mt-1">来源：{friendlySourceCollectionLabel(citation.source_collection)}</p>
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
      <p className="mt-3 break-all text-xs leading-5 text-[var(--audit-ink-subtle)]">材料片段：{citation.chunk_id}</p>
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
        {documents.length > 0 ? (
          documents.map((document) => (
            <article key={document.id} className="rounded-[var(--audit-radius-md)] border border-[var(--audit-line)] bg-white p-4">
              <div className="flex flex-wrap items-start justify-between gap-3">
                <div className="min-w-0">
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
                  转入对话
                </a>
              </div>
            </article>
          ))
        ) : (
          <p className="rounded-[var(--audit-radius-md)] border border-dashed border-[var(--audit-line)] bg-white p-4 audit-copy">
            当前关键词没有匹配的标题文档，可切换为全文模式或直接执行后端检索。
          </p>
        )}
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

function filterPortalDocuments(
  documents: readonly PortalDocumentItem[],
  query: string,
  titleOnly: boolean
): readonly PortalDocumentItem[] {
  const normalizedQuery = query.trim().toLowerCase();
  if (!titleOnly || !normalizedQuery) {
    return documents;
  }
  return documents.filter((document) => document.title.toLowerCase().includes(normalizedQuery));
}

function groupCitationsBySource(citations: readonly QueryCitation[]): readonly {
  readonly sourceCollection: SourceCollection;
  readonly label: string;
  readonly citations: readonly QueryCitation[];
}[] {
  return SOURCE_COLLECTIONS.map((sourceCollection) => {
    const category = documentCategoryStats.find((item) => item.sourceCollection === sourceCollection);
    return {
      sourceCollection,
      label: category?.name ?? sourceCollection,
      citations: citations.filter((citation) => citation.source_collection === sourceCollection)
    };
  }).filter((group) => group.citations.length > 0);
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

function governanceStatusLabel(status: DocumentUploadItem["governance_status"]): string {
  if (status === "approved-for-index") {
    return "准入索引";
  }
  if (status === "blocked") {
    return "已阻断";
  }
  return "待治理";
}

function governanceStatusTone(status: DocumentUploadItem["governance_status"]) {
  if (status === "approved-for-index") {
    return "success";
  }
  if (status === "blocked") {
    return "warning";
  }
  return "neutral";
}

function indexStatusLabel(status: DocumentUploadItem["index_status"]): string {
  if (status === "index-ready") {
    return "index-ready";
  }
  if (status === "staged-for-index") {
    return "staged-for-index";
  }
  if (status === "blocked") {
    return "index-blocked";
  }
  return "not-indexed";
}

function personalIndexStatusLabel(status: DocumentUploadItem["personal_index_status"]): string {
  if (status === "indexed") {
    return "已入本地索引";
  }
  if (status === "failed") {
    return "入索引失败";
  }
  return "未入本地索引";
}

function canRunPersonalIndex(item: DocumentUploadItem): boolean {
  return (
    item.governance_status === "approved-for-index" &&
    item.index_status === "index-ready" &&
    item.security_scan_status === "local-policy-passed" &&
    item.dlp_status === "clear"
  );
}

function securityStatusLabel(status: DocumentUploadItem["security_scan_status"]): string {
  if (status === "local-policy-review") {
    return "本地策略待复核";
  }
  return "本地策略通过";
}

function dlpStatusLabel(status: DocumentUploadItem["dlp_status"]): string {
  if (status === "needs-review") {
    return "待复核";
  }
  return "未提示";
}

function governanceNoteForStatus(status: DocumentGovernanceAction): string {
  if (status === "approved-for-index") {
    return "已通过本地材料治理，可进入后续索引任务队列。";
  }
  if (status === "blocked") {
    return "材料暂不进入索引，需补充脱敏、DLP 或人工复核。";
  }
  return "退回待治理状态，等待管理员、技术人员或主任复核。";
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

function friendlySourceCollectionLabel(sourceCollection: SourceCollection): string {
  return documentCategoryStats.find((category) => category.sourceCollection === sourceCollection)?.name ?? sourceCollection;
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

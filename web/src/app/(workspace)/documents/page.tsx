"use client";

import { FormEvent, useEffect, useMemo, useState } from "react";
import Link from "next/link";

import {
  buildReplicaLocalGateNotice,
  ReplicaNotice,
  ReplicaRuntimeBadge
} from "@/components/replica/replica-page-kit";
import { useReplicaDocumentsData } from "@/components/replica/use-replica-runtime";
import { runKnowledgeQuery, searchDocuments } from "@/lib/api-client";
import type { DocumentSearchResponse, QueryResponse, SourceCollection } from "@/lib/api-types";
import type { ReferenceDocumentResult } from "@/lib/reference-replica-data";
import { FALLBACK_SOURCE_COLLECTION_GROUPS, isSourceCollectionValue } from "@/lib/source-collection-catalog";

const documentLibraryIcons = ["gavel", "badge", "report", "archive", "help", "target", "book"] as const;
const sourceCollectionFallbackLabelByValue = new Map<SourceCollection, string>(
  FALLBACK_SOURCE_COLLECTION_GROUPS.flatMap((group) =>
    group.options.map((option) => [option.value, option.label] as const)
  )
);

const ALL_DOCUMENTS_CATEGORY = "全部文档";
const DEFAULT_DOCUMENT_QUERY = "医保基金监管";

type DocumentPreview = ReferenceDocumentResult & {
  readonly previewType: "对话文档" | "检索命中" | "知识库目录";
  readonly previewUrl?: string;
  readonly sourceCollection?: string;
};

type DocumentSearchState =
  | { readonly kind: "idle" }
  | { readonly kind: "searching"; readonly request: SearchRequestSnapshot }
  | { readonly kind: "results"; readonly request: SearchRequestSnapshot; readonly response: DocumentSearchResponse }
  | { readonly kind: "empty"; readonly request: SearchRequestSnapshot; readonly response: DocumentSearchResponse }
  | { readonly kind: "error"; readonly request: SearchRequestSnapshot; readonly message: string };

type AiDocumentSearchState =
  | { readonly kind: "idle" }
  | { readonly kind: "searching"; readonly request: SearchRequestSnapshot }
  | { readonly kind: "results"; readonly request: SearchRequestSnapshot; readonly response: QueryResponse }
  | { readonly kind: "empty"; readonly request: SearchRequestSnapshot; readonly response: QueryResponse }
  | { readonly kind: "error"; readonly request: SearchRequestSnapshot; readonly message: string };

type SearchRequestSnapshot = {
  readonly query: string;
  readonly titleOnly: boolean;
  readonly sourceCollections: readonly SourceCollection[];
  readonly categoryLabel: string;
};

export default function DocumentsPage() {
  const documentsData = useReplicaDocumentsData();
  const runtimeDataVisible = documentsData.status === "ready" || documentsData.status === "degraded";
  const categories = useMemo(
    () => runtimeDataVisible ? documentsData.data.categories : [],
    [documentsData.data.categories, runtimeDataVisible]
  );
  const searchHistory = useMemo(
    () => runtimeDataVisible ? documentsData.data.searchHistory : [],
    [documentsData.data.searchHistory, runtimeDataVisible]
  );
  const libraryTiles = categories.length > 0
    ? [
      {
        id: "all-documents",
        label: ALL_DOCUMENTS_CATEGORY,
        count: categories.reduce((sum, item) => sum + item.count, 0),
        icon: "archive"
      },
      ...categories.slice(0, 6).map((category, index) => ({
        id: category.id,
        label: category.name,
        count: category.count,
        icon: documentLibraryIcons[index % documentLibraryIcons.length]
      }))
    ]
    : [];
  const [query, setQuery] = useState(DEFAULT_DOCUMENT_QUERY);
  const [titleOnly, setTitleOnly] = useState(false);
  const [activeCategory, setActiveCategory] = useState(ALL_DOCUMENTS_CATEGORY);
  const [historyVisible, setHistoryVisible] = useState(true);
  const [actionNotice, setActionNotice] = useState("");
  const [selectedDocumentId, setSelectedDocumentId] = useState("");
  const [detailOpen, setDetailOpen] = useState(true);
  const [documentSearchState, setDocumentSearchState] = useState<DocumentSearchState>({ kind: "idle" });
  const [aiSearchState, setAiSearchState] = useState<AiDocumentSearchState>({ kind: "idle" });
  const [urlSourceCollections, setUrlSourceCollections] = useState<readonly SourceCollection[]>([]);
  const documentSearchResponse = documentSearchState.kind === "results" || documentSearchState.kind === "empty"
    ? documentSearchState.response
    : null;
  const aiSearchResponse = aiSearchState.kind === "results" || aiSearchState.kind === "empty"
    ? aiSearchState.response
    : null;
  const hasExplicitSearch = documentSearchState.kind !== "idle" || aiSearchState.kind !== "idle";
  const documentResults = useMemo(
    () => aiSearchState.kind === "results"
      ? queryResponseToDocumentResults(aiSearchState.response)
      : documentSearchState.kind === "results"
        ? documentSearchResponseToDocumentResults(documentSearchState.response)
        : !hasExplicitSearch && runtimeDataVisible && documentsData.source === "fixture"
          ? documentsData.data.results
          : [],
    [
      aiSearchState,
      documentSearchState,
      documentsData.data.results,
      documentsData.source,
      hasExplicitSearch,
      runtimeDataVisible
    ]
  );
  const searchRunning = documentSearchState.kind === "searching" || aiSearchState.kind === "searching";
  const activeSourceCollections = useMemo(
    () => selectedSourceCollections(categories, activeCategory, urlSourceCollections),
    [activeCategory, categories, urlSourceCollections]
  );
  const executedRequest = aiSearchState.kind !== "idle"
    ? aiSearchState.request
    : documentSearchState.kind !== "idle"
      ? documentSearchState.request
      : null;
  const completedSourceCollections = aiSearchState.kind === "results" || aiSearchState.kind === "empty"
    ? aiSearchState.response.effective_source_collections
    : documentSearchState.kind === "results" || documentSearchState.kind === "empty"
      ? documentSearchState.response.effective_source_collections
      : null;
  const displayedSourceCollections = completedSourceCollections ?? executedRequest?.sourceCollections ?? activeSourceCollections;
  const displayedQuery = executedRequest?.query ?? query;
  const displayedTitleOnly = executedRequest?.titleOnly ?? titleOnly;
  const displayedCategory = executedRequest?.categoryLabel ?? activeCategory;
  const displayedScopeLabel = sourceCollectionScopeLabel(categories, displayedSourceCollections);

  useEffect(() => {
    if (typeof window === "undefined") {
      return;
    }
    const params = new URLSearchParams(window.location.search);
    const scopedCollections = normalizeSourceCollectionParams(params.getAll("source_collection"));
    if (scopedCollections.length > 0) {
      setUrlSourceCollections((current) =>
        sameSourceCollections(current, scopedCollections) ? current : scopedCollections
      );
      if (scopedCollections.length === 1) {
        const matchedCategory = categories.find((category) => category.id === `source-${scopedCollections[0]}`);
        if (matchedCategory) {
          setActiveCategory((current) => (current === matchedCategory.name ? current : matchedCategory.name));
        }
      }
    }
    const initialQuery = params.get("query") ?? params.get("question");
    if (initialQuery?.trim()) {
      setQuery(initialQuery.trim());
    }
  }, [categories]);

  const filteredResults = useMemo(() => {
    if (hasExplicitSearch) {
      return documentResults;
    }
    const normalizedQuery = query.trim().toLowerCase();
    return documentResults.filter((item) => {
      const categoryMatched =
        activeCategory === ALL_DOCUMENTS_CATEGORY ||
        item.category === activeCategory ||
        normalizedQuery.length > 0;
      const text = titleOnly ? item.title : `${item.title} ${item.excerpt} ${item.source}`;
      const queryMatched = normalizedQuery.length === 0 || text.toLowerCase().includes(normalizedQuery);
      return categoryMatched && queryMatched;
    });
  }, [activeCategory, documentResults, hasExplicitSearch, query, titleOnly]);

  async function submitSearch(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    await runDocumentSearch(createSearchRequestSnapshot({
      query: query.trim() || DEFAULT_DOCUMENT_QUERY,
      titleOnly,
      sourceCollections: activeSourceCollections,
      categoryLabel: activeCategory
    }));
  }

  async function runDocumentSearch(request: SearchRequestSnapshot) {
    if (searchRunning) {
      return;
    }
    setDocumentSearchState({ kind: "searching", request });
    setAiSearchState({ kind: "idle" });
    setActionNotice("");
    try {
      const response = await searchDocuments({
        query: request.query,
        limit: 10,
        titleOnly: request.titleOnly,
        sourceCollections: request.sourceCollections
      });
      const mappedResults = documentSearchResponseToDocumentResults(response);
      setDocumentSearchState({ kind: mappedResults.length > 0 ? "results" : "empty", request, response });
      if (mappedResults.length > 0) {
        setSelectedDocumentId(mappedResults[0].id);
        setDetailOpen(true);
      }
    } catch {
      setDocumentSearchState({
        kind: "error",
        request,
        message: "文档检索失败：请确认知识库检索服务可用后重试。"
      });
    }
  }

  async function runAiDocumentSearch(request: SearchRequestSnapshot) {
    if (searchRunning) {
      return;
    }
    setDocumentSearchState({ kind: "idle" });
    setAiSearchState({ kind: "searching", request });
    setActionNotice("");
    try {
      const response = await runKnowledgeQuery({
        question: request.query,
        top_k: 5,
        title_only: request.titleOnly,
        source_collections: request.sourceCollections
      });
      const mappedResults = queryResponseToDocumentResults(response);
      setAiSearchState({ kind: mappedResults.length > 0 ? "results" : "empty", request, response });
      if (mappedResults.length > 0) {
        setSelectedDocumentId(mappedResults[0].id);
        setDetailOpen(true);
      }
    } catch {
      setAiSearchState({
        kind: "error",
        request,
        message: "AI+ 审证未完成：请确认问答服务可用后重试。"
      });
    }
  }

  const apiDirectoryDocuments = useMemo(
    () => categories.slice(0, 10).map((category) => categoryToDirectoryPreview(category)),
    [categories]
  );
  const shouldShowApiDirectory =
    !hasExplicitSearch &&
    documentsData.source !== "fixture" &&
    apiDirectoryDocuments.length > 0;
  const shownFeaturedDocuments: readonly DocumentPreview[] = shouldShowApiDirectory
    ? apiDirectoryDocuments
    : filteredResults.length > 0
      ? (filteredResults.map((item) => ({
        id: item.id,
        title: item.title,
        category: item.category,
        excerpt: item.excerpt,
        source: item.source,
        updatedAt: item.updatedAt,
        previewUrl: (item as DocumentPreview).previewUrl,
        sourceCollection: (item as DocumentPreview).sourceCollection,
        previewType: "检索命中" as const
      })).slice(0, 10) as readonly DocumentPreview[])
      : [];

  const selectedDocument =
    shownFeaturedDocuments.find((item) => item.id === selectedDocumentId) ??
    shownFeaturedDocuments[0];

  function recordDocumentAction(item: DocumentPreview, action: string) {
    setSelectedDocumentId(item.id);
    setDetailOpen(true);
    if (action === "打开文档" && item.previewUrl) {
      window.location.assign(item.previewUrl);
      return;
    }
    setActionNotice(buildReplicaLocalGateNotice({
      action: `${action}「${item.title}」`,
      nextStep: "文档详情 API"
    }));
  }

  return (
    <main
      className="replica-doc-page"
      data-replica-source={documentsData.source}
      data-replica-status={documentsData.status}
    >
      <section className="replica-doc-hero" aria-labelledby="replica-doc-title">
        <div>
          <p className="replica-kicker">文档检索</p>
          <h1 id="replica-doc-title">文档检索</h1>
          <p>快速检索系统内的相关文档</p>
          <div className="mt-3">
            <ReplicaRuntimeBadge
              source={documentsData.source}
              status={documentsData.status}
              issueCount={documentsData.issues.length}
            />
          </div>
        </div>
        <div className="replica-doc-illustration" aria-hidden="true">
          <span className="replica-doc-illustration-shelf" />
          <span className="replica-doc-illustration-person" />
          <span className="replica-doc-illustration-glass" />
        </div>
      </section>

      <section className="replica-doc-search-section" aria-label="文档检索">
        <form className="replica-doc-searchbar" onSubmit={submitSearch}>
          <label>
            <span className="sr-only">检索关键词</span>
            <input
              value={query}
              onChange={(event) => setQuery(event.target.value)}
              placeholder={DEFAULT_DOCUMENT_QUERY}
            />
          </label>
          <label className="replica-doc-title-only">
            <input
              type="checkbox"
              checked={titleOnly}
              onChange={(event) => setTitleOnly(event.target.checked)}
            />
            <span>仅标题</span>
          </label>
          <button type="submit" className="replica-doc-search-submit" disabled={searchRunning}>
            <span className="replica-doc-search-icon" aria-hidden="true" />
            {documentSearchState.kind === "searching" ? "搜索中" : "搜索"}
          </button>
        </form>
        <button
          type="button"
          className="replica-doc-ai-button"
          disabled={searchRunning}
          onClick={() => void runAiDocumentSearch(createSearchRequestSnapshot({
            query: query.trim() || DEFAULT_DOCUMENT_QUERY,
            titleOnly,
            sourceCollections: activeSourceCollections,
            categoryLabel: activeCategory
          }))}
        >
          <span aria-hidden="true">AI</span>
          检索AI+
        </button>
      </section>

      <section className="replica-doc-history" aria-label="搜索历史">
        <div className="replica-doc-section-title">
          <h2>搜索历史:</h2>
          <button type="button" aria-label="清空搜索历史" onClick={() => setHistoryVisible(false)}>
            <span aria-hidden="true" />
          </button>
        </div>
        {documentsData.status === "error" ? (
          <ReplicaNotice>搜索历史读取失败</ReplicaNotice>
        ) : historyVisible && searchHistory.length > 0 ? (
          <div className="replica-doc-history-chips">
            {searchHistory.slice(0, 5).map((history) => (
              <button key={history} type="button" onClick={() => {
                setQuery(history);
              }}>
                {history}
              </button>
            ))}
          </div>
        ) : historyVisible ? (
          <ReplicaNotice>暂无搜索历史</ReplicaNotice>
        ) : (
          <ReplicaNotice>
            {buildReplicaLocalGateNotice({
              action: "隐藏搜索历史",
              nextStep: "搜索历史写入 API"
            })}
          </ReplicaNotice>
        )}
      </section>

      <section className="replica-doc-library-band" aria-label="文档库分类">
        {documentsData.status === "empty" ? <ReplicaNotice>暂无可用文档目录</ReplicaNotice> : null}
        {documentsData.status === "error" ? <ReplicaNotice>文档目录读取失败</ReplicaNotice> : null}
        {libraryTiles.map((tile) => (
          <button
            key={tile.id}
            type="button"
            className={activeCategory === tile.label ? "is-active" : ""}
            onClick={() => {
              setActiveCategory(tile.label);
              setUrlSourceCollections([]);
            }}
          >
            <span className={`replica-doc-library-icon icon-${tile.icon}`} aria-hidden="true" />
            <strong>{tile.label}</strong>
            <em>({tile.count.toLocaleString()})</em>
          </button>
        ))}
      </section>

      <section className="replica-doc-results-panel" aria-labelledby="replica-doc-panel-title">
        <div className="replica-doc-results-head">
          <h2 id="replica-doc-panel-title">对话文档</h2>
          <button
            type="button"
            aria-label="查看全部对话文档"
            onClick={() => setActionNotice(buildReplicaLocalGateNotice({
              action: "查看全部对话文档",
              nextStep: "文档列表分页 API"
            }))}
          >
            查看全部
            <span aria-hidden="true">›</span>
          </button>
        </div>
        {actionNotice ? <ReplicaNotice>{actionNotice}</ReplicaNotice> : null}
        {documentSearchState.kind === "empty" ? (
          <div role="status" aria-live="polite" aria-label="文档检索空状态">
            <ReplicaNotice>未找到匹配文档</ReplicaNotice>
          </div>
        ) : null}
        {documentSearchState.kind === "error" ? (
          <div role="alert">
            <ReplicaNotice>{documentSearchState.message}</ReplicaNotice>
            <button
              type="button"
              disabled={searchRunning}
              onClick={() => void runDocumentSearch(documentSearchState.request)}
            >
              重试检索
            </button>
          </div>
        ) : null}
        {documentSearchResponse ? (
          <div role="status" aria-live="polite" aria-label="文档检索完成状态">
            <ReplicaNotice>
              文档检索 provider_call：{documentSearchResponse.boundaries.provider_call ? "是" : "否"}
            </ReplicaNotice>
          </div>
        ) : null}
        {aiSearchState.kind === "empty" ? (
          <div role="status" aria-live="polite" aria-label="AI+ 空状态">
            <ReplicaNotice>AI+ 已完成审证，但未返回可展示的引用文档。</ReplicaNotice>
          </div>
        ) : null}
        {aiSearchState.kind === "error" ? (
          <div role="alert">
            <ReplicaNotice>{aiSearchState.message}</ReplicaNotice>
          </div>
        ) : null}
        {aiSearchResponse ? (
          <div role="status" aria-live="polite" aria-label="AI+ 完成状态">
            <ReplicaNotice>AI+ provider_call：当前查询契约未独立提供</ReplicaNotice>
            <ReplicaNotice>AI+ generation_status：{aiSearchResponse.generation_status}</ReplicaNotice>
          </div>
        ) : null}
        <div className="replica-doc-results-shell">
          <div className="replica-doc-two-column-list">
            {shownFeaturedDocuments.map((item) => (
              <article key={item.id} className={`replica-doc-row ${selectedDocument?.id === item.id ? "is-selected" : ""}`}>
                <button type="button" onClick={() => recordDocumentAction(item, "查看文档")}>
                  <span>
                    <strong>{item.title}</strong>
                    <em>{item.source}</em>
                  </span>
                  <time>{item.updatedAt}</time>
                </button>
              </article>
            ))}
          </div>

          {selectedDocument && detailOpen ? (
            <aside className="replica-doc-detail" aria-label="文档详情预览">
              <div className="replica-detail-head">
                <span>{selectedDocument.previewType}</span>
                <button type="button" aria-label="关闭文档详情" onClick={() => setDetailOpen(false)}>×</button>
              </div>
              <h3>{selectedDocument.title}</h3>
              <p>{selectedDocument.excerpt}</p>
              <dl>
                <div>
                  <dt>来源</dt>
                  <dd>{selectedDocument.source}</dd>
                </div>
                <div>
                  <dt>类别</dt>
                  <dd>{selectedDocument.category}</dd>
                </div>
                <div>
                  <dt>更新时间</dt>
                  <dd>{selectedDocument.updatedAt}</dd>
                </div>
              </dl>
              <div className="replica-doc-detail-actions">
                {selectedDocument.previewUrl ? (
                  <Link href={selectedDocument.previewUrl}>打开文档</Link>
                ) : (
                  <button type="button" onClick={() => recordDocumentAction(selectedDocument, "打开文档")}>打开文档</button>
                )}
                <Link href={documentChatHref(selectedDocument, displayedQuery)}>加入对话</Link>
              </div>
            </aside>
          ) : null}
        </div>
      </section>

      <section className="replica-doc-statusline" aria-label="当前检索状态">
        <span>{displayedCategory}</span>
        <strong>{documentSearchStatusLabel(documentSearchState, aiSearchState, filteredResults.length)}</strong>
        <span>{displayedTitleOnly ? "仅标题" : "全文检索"}</span>
        <span>关键词：{displayedQuery}</span>
        <span>范围：{displayedScopeLabel}</span>
        {categories.length > 0 ? (
          <span>文档库：{categories.length} 类 / {categories.reduce((sum, item) => sum + item.count, 0).toLocaleString()} 份</span>
        ) : null}
      </section>

      <section className="replica-document-layout replica-doc-legacy-results" aria-label="检索命中明细">
        <aside className="replica-category-list" aria-label="文档分类">
          {categories.map((category) => (
            <button
              key={category.id}
              type="button"
              className={activeCategory === category.name ? "is-active" : ""}
              onClick={() => {
                setActiveCategory(category.name);
                setUrlSourceCollections([]);
              }}
            >
              <strong>{category.name}</strong>
              <span>{category.description}</span>
              <em>{category.count}</em>
            </button>
          ))}
        </aside>

        <section className="replica-panel replica-document-results">
          <div className="replica-results-head">
            <div>
              <p className="replica-kicker">{displayedCategory}</p>
              <h2>检索结果</h2>
            </div>
            <span>关键词：{displayedQuery}</span>
          </div>

          <div className="replica-result-list">
            {filteredResults.map((item) => (
              <article key={item.id} className="replica-result-card">
                <div className="replica-result-card-top">
                  <span>{item.category}</span>
                  <time>{item.updatedAt}</time>
                </div>
                <h3>{item.title}</h3>
                <p>{item.excerpt}</p>
                <div>
                  <strong>{item.source}</strong>
                  <span>{hasExplicitSearch ? "命中结果" : "fixture 文档"}</span>
                </div>
              </article>
            ))}
          </div>
        </section>
      </section>
    </main>
  );
}

function selectedSourceCollections(
  categories: readonly { readonly id: string; readonly name: string }[],
  activeCategory: string,
  urlSourceCollections: readonly SourceCollection[]
): readonly SourceCollection[] {
  const category = categories.find((item) => item.name === activeCategory);
  if (category?.id.startsWith("source-")) {
    return [category.id.slice("source-".length) as SourceCollection];
  }
  return activeCategory === ALL_DOCUMENTS_CATEGORY ? urlSourceCollections : [];
}

function createSearchRequestSnapshot(request: SearchRequestSnapshot): SearchRequestSnapshot {
  return Object.freeze({
    ...request,
    sourceCollections: Object.freeze([...request.sourceCollections])
  });
}

function documentSearchStatusLabel(
  documentState: DocumentSearchState,
  aiState: AiDocumentSearchState,
  resultCount: number
): string {
  if (documentState.kind === "searching" || aiState.kind === "searching") {
    return "检索中";
  }
  if (documentState.kind === "error" || aiState.kind === "error") {
    return "检索失败";
  }
  if (documentState.kind !== "idle" || aiState.kind !== "idle") {
    return `${resultCount} 条匹配`;
  }
  return "尚未检索";
}

function normalizeSourceCollectionParams(values: readonly string[]): readonly SourceCollection[] {
  return Array.from(
    new Set(
      values
        .flatMap((value) => value.split(","))
        .map((value) => value.trim())
        .filter(isSourceCollectionValue)
    )
  );
}

function sameSourceCollections(
  left: readonly SourceCollection[],
  right: readonly SourceCollection[]
): boolean {
  return left.length === right.length && left.every((item, index) => item === right[index]);
}

function sourceCollectionScopeLabel(
  categories: readonly { readonly id: string; readonly name: string }[],
  sourceCollections: readonly SourceCollection[]
): string {
  if (sourceCollections.length === 0) {
    return "全部可检索知识库";
  }
  const names = sourceCollections.map((sourceCollection) => {
    const category = categories.find((item) => item.id === `source-${sourceCollection}`);
    return category?.name ?? sourceCollectionFallbackLabelByValue.get(sourceCollection) ?? sourceCollection;
  });
  return names.slice(0, 2).join("、") + (names.length > 2 ? ` 等 ${names.length} 个` : "");
}

function categoryToDirectoryPreview(
  category: { readonly id: string; readonly name: string; readonly description: string; readonly count: number }
): DocumentPreview {
  const sourceCollection = category.id.startsWith("source-")
    ? category.id.slice("source-".length)
    : undefined;

  return {
    id: `directory-${category.id}`,
    title: `${category.name} 文档目录`,
    category: category.name,
    excerpt: category.description,
    source: `${category.count.toLocaleString()} 份文档`,
    updatedAt: "生产目录",
    previewType: "知识库目录",
    sourceCollection
  };
}

function documentChatHref(item: DocumentPreview, executedQuery: string): string {
  const params = new URLSearchParams();
  params.set("question", executedQuery || item.title);
  if (item.sourceCollection) {
    params.set("source_collection", item.sourceCollection);
  }
  return `/chat?${params.toString()}`;
}

function documentSearchResponseToDocumentResults(
  response: DocumentSearchResponse
): readonly DocumentPreview[] {
  return response.items.map((item) => ({
    id: item.id,
    title: item.title,
    category: item.source_label,
    excerpt: compactDocumentText(item.snippet, 120),
    source: item.source_collection,
    updatedAt: item.index_version_key || "检索命中",
    previewType: "检索命中",
    previewUrl: item.preview_url,
    sourceCollection: item.source_collection
  }));
}

function queryResponseToDocumentResults(response: QueryResponse): readonly DocumentPreview[] {
  const citations = response.citations.map((citation, index) => ({
    id: citation.citation_id || `query-citation-${index + 1}`,
    title: locatorText(citation.locator, ["title", "document_title", "file_name", "source_title", "name"]) ?? `引用文档 ${index + 1}`,
    category: citation.evidence_type || citation.source_collection,
    excerpt: compactDocumentText(citation.snippet, 96),
    source: citation.source_collection,
    updatedAt: locatorText(citation.locator, ["date", "published_at", "issued_at", "year"]) ?? "检索命中",
    previewType: "检索命中" as const,
    previewUrl: `/api/v1/preview/${citation.chunk_id}`,
    sourceCollection: citation.source_collection
  }));
  const uploads = response.personal_upload_matches.map((match, index) => ({
    id: match.id || `personal-match-${index + 1}`,
    title: match.name,
    category: "个人材料",
    excerpt: compactDocumentText(match.snippet, 96),
    source: match.created_by || "个人上传",
    updatedAt: match.indexed_at?.slice(0, 10) || "未索引",
    previewType: "检索命中" as const,
    sourceCollection: "personal-materials"
  }));
  return [...citations, ...uploads];
}

function locatorText(locator: Record<string, unknown>, keys: readonly string[]): string | null {
  for (const key of keys) {
    const value = locator[key];
    if (typeof value === "string" && value.trim()) {
      return value.trim();
    }
    if (typeof value === "number") {
      return String(value);
    }
  }
  return null;
}

function compactDocumentText(value: string, maxLength: number): string {
  const normalized = value.replace(/\s+/g, " ").trim();
  if (normalized.length <= maxLength) {
    return normalized;
  }
  return `${normalized.slice(0, Math.max(0, maxLength - 3))}...`;
}

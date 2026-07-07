"use client";

import { FormEvent, useMemo, useState } from "react";

import { buildReplicaLocalGateNotice, ReplicaNotice } from "@/components/replica/replica-page-kit";
import { useReplicaDocumentsData } from "@/components/replica/use-replica-runtime";
import { runKnowledgeQuery, searchDocuments } from "@/lib/api-client";
import type { DocumentSearchResponse, QueryResponse } from "@/lib/api-types";
import type { ReferenceDocumentResult } from "@/lib/reference-replica-data";

const documentLibraryTiles = [
  { id: "law", label: "法律法规库", count: 3833, icon: "gavel" },
  { id: "policy", label: "政策文件库", count: 0, icon: "badge" },
  { id: "research", label: "研究报告库", count: 0, icon: "report" },
  { id: "case", label: "审计案例库", count: 0, icon: "archive" },
  { id: "faq", label: "常见问题库", count: 10, icon: "help" },
  { id: "hot", label: "热点事件库", count: 0, icon: "target" },
  { id: "book", label: "书本期刊库", count: 0, icon: "book" }
] as const;

const featuredDocuments = [
  {
    id: "doc-ledger",
    title: "雨丰民生25年流水.xlsx",
    source: "项目材料",
    updatedAt: "2026-06-09 07:57:00"
  },
  {
    id: "doc-finance-report",
    title: "10.深圳雨丰农业科技有限公司-2026年2月财务报表.xlsx",
    source: "财务报表",
    updatedAt: "2026-06-09 07:56:51"
  },
  {
    id: "doc-reject",
    title: "18_投标被否决原因统计表.pdf",
    source: "招标人违法确定中标人V2",
    updatedAt: "2026-05-13 10:56:03"
  },
  {
    id: "doc-contract",
    title: "17_中标合同关键条款比对表.pdf",
    source: "招标人违法确定中标人V2",
    updatedAt: "2026-05-13 10:56:02"
  },
  {
    id: "doc-exception",
    title: "19_异常情况处理记录表.pdf",
    source: "招标人违法确定中标人V2",
    updatedAt: "2026-05-13 10:56:02"
  },
  {
    id: "doc-complaint",
    title: "20_投诉与质疑处理台账.pdf",
    source: "招标人违法确定中标人V2",
    updatedAt: "2026-05-13 10:56:02"
  },
  {
    id: "doc-qualification",
    title: "14_投标人资格审核表.pdf",
    source: "招标人违法确定中标人V2",
    updatedAt: "2026-05-13 10:55:57"
  },
  {
    id: "doc-members",
    title: "15_评标委员会成员信息表.pdf",
    source: "招标人违法确定中标人V2",
    updatedAt: "2026-05-13 10:55:57"
  },
  {
    id: "doc-timeline",
    title: "16_招标流程时间节点表.pdf",
    source: "招标人违法确定中标人V2",
    updatedAt: "2026-05-13 10:55:57"
  },
  {
    id: "doc-rules",
    title: "10_相关法律法规及管理制度.pdf",
    source: "招标人违法确定中标人V2",
    updatedAt: "2026-05-13 10:55:56"
  }
] as const;

const defaultSearchHistory = ["投标", "招标投标法", "集中采购目录", "审计", "智能科技的CEO是谁"];

type DocumentPreview = ReferenceDocumentResult & {
  readonly previewType: "对话文档" | "检索命中";
  readonly previewUrl?: string;
  readonly sourceCollection?: string;
};

export default function DocumentsPage() {
  const documentsData = useReplicaDocumentsData();
  const categories = documentsData.data.categories;
  const searchHistory =
    documentsData.data.searchHistory.length > 0 ? documentsData.data.searchHistory : defaultSearchHistory;
  const libraryTiles = categories.length > 0
    ? categories.slice(0, 7).map((category, index) => ({
      id: category.id,
      label: category.name,
      count: category.count,
      icon: documentLibraryTiles[index % documentLibraryTiles.length].icon
    }))
    : documentLibraryTiles;
  const [query, setQuery] = useState("劳动争议司法案件解释");
  const [submittedQuery, setSubmittedQuery] = useState("劳动争议司法案件解释");
  const [titleOnly, setTitleOnly] = useState(false);
  const [activeCategory, setActiveCategory] = useState("法律法规库");
  const [historyVisible, setHistoryVisible] = useState(true);
  const [notice, setNotice] = useState("");
  const [selectedDocumentId, setSelectedDocumentId] = useState("doc-ledger");
  const [detailOpen, setDetailOpen] = useState(true);
  const [liveResults, setLiveResults] = useState<readonly DocumentPreview[]>([]);
  const [hasLiveSearch, setHasLiveSearch] = useState(false);
  const [searching, setSearching] = useState(false);
  const documentResults = hasLiveSearch ? liveResults : documentsData.data.results;

  const filteredResults = useMemo(() => {
    if (hasLiveSearch) {
      return documentResults;
    }
    const normalizedQuery = submittedQuery.trim().toLowerCase();
    return documentResults.filter((item) => {
      const categoryMatched = item.category === activeCategory || normalizedQuery.length > 0;
      const text = titleOnly ? item.title : `${item.title} ${item.excerpt} ${item.source}`;
      const queryMatched = normalizedQuery.length === 0 || text.toLowerCase().includes(normalizedQuery);
      return categoryMatched && queryMatched;
    });
  }, [activeCategory, documentResults, hasLiveSearch, submittedQuery, titleOnly]);

  async function submitSearch(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    await runDocumentSearch(query.trim() || "劳动争议司法案件解释");
  }

  async function runDocumentSearch(nextQuery: string) {
    setSubmittedQuery(nextQuery);
    setSearching(true);
    setNotice("");
    try {
      const activeSourceCollection = activeCategorySourceCollection(categories, activeCategory);
      const response = await searchDocuments({
        query: nextQuery,
        limit: 10,
        titleOnly,
        sourceCollections: activeSourceCollection ? [activeSourceCollection] : []
      });
      const mappedResults = documentSearchResponseToDocumentResults(response);
      setLiveResults(mappedResults);
      setHasLiveSearch(true);
      if (mappedResults.length === 0) {
        setNotice("已完成检索，但未返回可展示的引用文档。");
      }
    } catch {
      setLiveResults([]);
      setHasLiveSearch(true);
      setNotice("检索未完成：请确认知识库检索服务可用后重试。");
    } finally {
      setSearching(false);
    }
  }

  async function runAiDocumentSearch(nextQuery: string) {
    setSubmittedQuery(nextQuery);
    setSearching(true);
    setNotice("");
    try {
      const response = await runKnowledgeQuery({
        question: nextQuery,
        top_k: 5,
        title_only: titleOnly
      });
      const mappedResults = queryResponseToDocumentResults(response);
      setLiveResults(mappedResults);
      setHasLiveSearch(true);
      if (mappedResults.length === 0) {
        setNotice("AI+ 已完成审证，但未返回可展示的引用文档。");
      }
    } catch {
      setNotice("AI+ 审证未完成：请确认问答服务可用后重试。");
    } finally {
      setSearching(false);
    }
  }

  const shownFeaturedDocuments: readonly DocumentPreview[] = filteredResults.length > 0
    ? ([
      ...featuredDocuments.slice(0, 5),
      ...filteredResults.map((item) => ({
        id: item.id,
        title: item.title,
        category: item.category,
        excerpt: item.excerpt,
        source: item.source,
        updatedAt: item.updatedAt,
        previewUrl: (item as DocumentPreview).previewUrl,
        sourceCollection: (item as DocumentPreview).sourceCollection,
        previewType: "检索命中" as const
      }))
    ].slice(0, 10) as readonly DocumentPreview[])
    : featuredDocuments.map((item) => ({
      ...item,
      category: "对话文档",
      excerpt: "来自历史对话和项目材料，可继续进入证据核验或加入 AI 对话上下文。",
      previewType: "对话文档" as const
    }));

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
    if (action === "加入对话") {
      const params = new URLSearchParams();
      params.set("question", submittedQuery || item.title);
      if (item.sourceCollection) {
        params.set("source_collection", item.sourceCollection);
      }
      window.location.assign(`/chat?${params.toString()}`);
      return;
    }
    setNotice(buildReplicaLocalGateNotice({
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
              placeholder="劳动争议司法案件解释"
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
          <button type="submit" className="replica-doc-search-submit">
            <span className="replica-doc-search-icon" aria-hidden="true" />
            {searching ? "搜索中" : "搜索"}
          </button>
        </form>
        <button
          type="button"
          className="replica-doc-ai-button"
          onClick={() => void runAiDocumentSearch(query.trim() || submittedQuery)}
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
        {historyVisible ? (
          <div className="replica-doc-history-chips">
            {searchHistory.slice(0, 5).map((history) => (
              <button key={history} type="button" onClick={() => {
                setQuery(history);
                setSubmittedQuery(history);
              }}>
                {history}
              </button>
            ))}
          </div>
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
        {libraryTiles.map((tile) => (
          <button
            key={tile.id}
            type="button"
            className={activeCategory === tile.label ? "is-active" : ""}
            onClick={() => setActiveCategory(tile.label)}
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
            onClick={() => setNotice(buildReplicaLocalGateNotice({
              action: "查看全部对话文档",
              nextStep: "文档列表分页 API"
            }))}
          >
            查看全部
            <span aria-hidden="true">›</span>
          </button>
        </div>
        {notice ? <ReplicaNotice>{notice}</ReplicaNotice> : null}
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
                <button type="button" onClick={() => recordDocumentAction(selectedDocument, "打开文档")}>打开文档</button>
                <button type="button" onClick={() => recordDocumentAction(selectedDocument, "加入对话")}>加入对话</button>
              </div>
            </aside>
          ) : null}
        </div>
      </section>

      <section className="replica-doc-statusline" aria-label="当前检索状态">
        <span>{activeCategory}</span>
        <strong>{filteredResults.length} 条匹配</strong>
        <span>{titleOnly ? "仅标题" : "全文检索"}</span>
        <span>关键词：{submittedQuery}</span>
        <span>文档库：{categories.length} 类 / {categories.reduce((sum, item) => sum + item.count, 0).toLocaleString()} 份</span>
      </section>

      <section className="replica-document-layout replica-doc-legacy-results" aria-label="检索命中明细">
        <aside className="replica-category-list" aria-label="文档分类">
          {categories.map((category) => (
            <button
              key={category.id}
              type="button"
              className={activeCategory === category.name ? "is-active" : ""}
              onClick={() => setActiveCategory(category.name)}
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
              <p className="replica-kicker">{activeCategory}</p>
              <h2>检索结果</h2>
            </div>
            <span>关键词：{submittedQuery}</span>
          </div>

          <div className="replica-result-list">
            {(filteredResults.length > 0 ? filteredResults : documentResults).map((item) => (
              <article key={item.id} className="replica-result-card">
                <div className="replica-result-card-top">
                  <span>{item.category}</span>
                  <time>{item.updatedAt}</time>
                </div>
                <h3>{item.title}</h3>
                <p>{item.excerpt}</p>
                <div>
                  <strong>{item.source}</strong>
                  <span>{filteredResults.length > 0 ? "命中结果" : "推荐文档"}</span>
                </div>
              </article>
            ))}
          </div>
        </section>
      </section>
    </main>
  );
}

function activeCategorySourceCollection(
  categories: readonly { readonly id: string; readonly name: string }[],
  activeCategory: string
): string | null {
  const category = categories.find((item) => item.name === activeCategory);
  if (!category?.id.startsWith("source-")) {
    return null;
  }
  return category.id.slice("source-".length);
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

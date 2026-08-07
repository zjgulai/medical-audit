"use client";

import { useMemo, useState } from "react";
import Link from "next/link";

import {
  ReplicaEmptyState,
  ReplicaFilterButton,
  ReplicaNotice,
  ReplicaPageHeader
} from "@/components/replica/replica-page-kit";
import { useReplicaKnowledgeBaseData } from "@/components/replica/use-replica-runtime";
import type { SourceCollection } from "@/lib/api-types";
import type { ReplicaKnowledgeBaseItem } from "@/lib/replica-adapters";
import { isAuditProductSourceCollection } from "@/lib/audit-knowledge-scope";
import { isSourceCollectionValue } from "@/lib/source-collection-catalog";

type ProductKnowledgeCategoryId =
  | "all"
  | "my"
  | "audit-laws"
  | "medical-laws"
  | "insurance-rules"
  | "risk-list";

type ProductKnowledgeCategory = {
  readonly id: ProductKnowledgeCategoryId;
  readonly title: string;
  readonly description: string;
  readonly tone: "blue" | "green" | "amber" | "rose" | "slate" | "cyan";
  readonly items: readonly ReplicaKnowledgeBaseItem[];
};

const productCategoryMeta: readonly Omit<ProductKnowledgeCategory, "items">[] = [
  {
    id: "my",
    title: "我的知识库",
    description: "个人上传材料、院内台账、访谈记录和仅本人可见的审计资料。",
    tone: "blue"
  },
  {
    id: "audit-laws",
    title: "审计通用法律法规",
    description: "审计程序、监督执法、项目复核和通用定性依据。",
    tone: "slate"
  },
  {
    id: "medical-laws",
    title: "医疗领域法律法规",
    description: "医疗、医保、药品和基金监管相关法律政策。",
    tone: "cyan"
  },
  {
    id: "insurance-rules",
    title: "医保相关规则制度",
    description: "监管两库、医保目录、诊疗项目、支付限制和规则口径。",
    tone: "amber"
  },
  {
    id: "risk-list",
    title: "医疗风险负面清单",
    description: "高风险问题、异常模式、案例线索和负面清单。",
    tone: "rose"
  }
];

const allCategory = "all" as const;
const releaseKnowledgeScope = {
  id: "core-5",
  label: "核心 5 个知识集合",
  requiredSourceCollections: [
    "medical-insurance-laws",
    "supervision-rules-knowledge",
    "medical-insurance-catalog",
    "risk-negative-list",
    "management-judicial-audit-procedure"
  ] satisfies readonly SourceCollection[]
} as const;
const knowledgeBaseSourceCollectionMap: Record<string, readonly SourceCollection[]> = {
  "kb-personal": ["personal-materials"],
  "kb-public-policy": [
    "policy-general-policy",
    "policy-finance-price-procurement",
    "policy-data-statistics-disclosure",
    "policy-reform-pilot",
    "policy-social-security-livelihood",
    "policy-industry-business-environment"
  ],
  "kb-system-medical-fund": [
    "medical-insurance-laws",
    "supervision-rules-knowledge",
    "medical-insurance-catalog",
    "risk-negative-list"
  ],
  "kb-system-audit": ["management-judicial-audit-procedure"],
  "kb-project-village": ["other-agriculture-water"]
};

function categoryForKnowledgeBase(item: ReplicaKnowledgeBaseItem): ProductKnowledgeCategoryId {
  const sources = sourceCollectionsFromKnowledgeBaseId(item.id);
  const text = `${sources.join(" ")} ${item.id} ${item.name} ${item.scope} ${item.description} ${item.tags.join(" ")}`;

  if (sources.includes("personal-materials") || item.scope === "个人知识库" || text.includes("个人")) {
    return "my";
  }
  if (sources.includes("risk-negative-list") || text.includes("风险清单") || text.includes("负面清单")) {
    return "risk-list";
  }
  if (sources.includes("supervision-rules-knowledge") || sources.includes("medical-insurance-catalog") || text.includes("监管两库") || text.includes("医保目录")) {
    return "insurance-rules";
  }
  if (sources.includes("medical-insurance-laws") || text.includes("医疗") || text.includes("医保")) {
    return "medical-laws";
  }
  if (sources.includes("management-judicial-audit-procedure") || text.includes("审计程序") || text.includes("司法审计")) {
    return "audit-laws";
  }
  return "audit-laws";
}

function isAuditKnowledgeBase(item: ReplicaKnowledgeBaseItem): boolean {
  return sourceCollectionsFromKnowledgeBaseId(item.id).some(isAuditProductSourceCollection);
}

function buildProductCategories(items: readonly ReplicaKnowledgeBaseItem[]): readonly ProductKnowledgeCategory[] {
  return productCategoryMeta.map((category) => ({
    ...category,
    items: items.filter((item) => categoryForKnowledgeBase(item) === category.id)
  }));
}

function matchesKnowledgeBase(item: ReplicaKnowledgeBaseItem, query: string) {
  const normalizedQuery = query.trim().toLowerCase();
  return normalizedQuery.length === 0 ||
    `${item.name} ${item.scope} ${item.owner} ${item.description} ${item.tags.join(" ")}`.toLowerCase().includes(normalizedQuery);
}

function documentCountForItem(item: ReplicaKnowledgeBaseItem): number | null {
  return typeof item.documentCount === "number" && item.documentCount >= 0
    ? item.documentCount
    : null;
}

function sumDocuments(items: readonly ReplicaKnowledgeBaseItem[]): number | null {
  if (items.length === 0) {
    return null;
  }
  let total = 0;
  for (const item of items) {
    const count = documentCountForItem(item);
    if (count === null) {
      return null;
    }
    total += count;
  }
  return total;
}

function knowledgeBaseSyncStatus(items: readonly ReplicaKnowledgeBaseItem[]): string {
  if (items.length === 0) return "待同步";
  const counts = items.map(documentCountForItem);
  if (counts.some((count) => count === null)) return "状态待确认";
  const populatedCount = counts.filter((count) => (count ?? 0) > 0).length;
  if (populatedCount === items.length) return "已同步";
  if (populatedCount > 0) return "部分同步";
  return "待同步";
}

function sourceCollectionsFromKnowledgeBases(items: readonly ReplicaKnowledgeBaseItem[]): readonly SourceCollection[] {
  return Array.from(
    new Set(
      items
        .flatMap((item) => sourceCollectionsFromKnowledgeBaseId(item.id))
    )
  );
}

function populatedKnowledgeBaseCount(items: readonly ReplicaKnowledgeBaseItem[]): number | null {
  if (
    items.length === 0
    || items.some((item) => documentCountForItem(item) === null)
  ) {
    return null;
  }
  return items.filter((item) => (
    (documentCountForItem(item) ?? 0) > 0
  )).length;
}

function hasPopulatedRequiredKnowledgeBases(items: readonly ReplicaKnowledgeBaseItem[]): boolean {
  return releaseKnowledgeScope.requiredSourceCollections.every((requiredSource) => (
    items.some((item) => (
      sourceCollectionsFromKnowledgeBaseId(item.id).includes(requiredSource)
      && (documentCountForItem(item) ?? 0) > 0
    ))
  ));
}

export default function KnowledgeBasePage() {
  const [query, setQuery] = useState("");
  const [activeCategory, setActiveCategory] = useState<ProductKnowledgeCategoryId>(allCategory);
  const [notice, setNotice] = useState("");
  const [selectedKnowledgeBaseId, setSelectedKnowledgeBaseId] = useState("");
  const [detailOpen, setDetailOpen] = useState(true);
  const knowledgeBaseData = useReplicaKnowledgeBaseData();
  const allKnowledgeBases = knowledgeBaseData.data.knowledgeBases;
  const knowledgeBases = useMemo(
    () => allKnowledgeBases.filter(isAuditKnowledgeBase),
    [allKnowledgeBases]
  );

  const productCategories = useMemo(() => buildProductCategories(knowledgeBases), [knowledgeBases]);
  const activeItems = useMemo(() => {
    const scopedItems = activeCategory === allCategory
      ? knowledgeBases
      : productCategories.find((category) => category.id === activeCategory)?.items ?? [];
    return scopedItems.filter((item) => matchesKnowledgeBase(item, query));
  }, [activeCategory, knowledgeBases, productCategories, query]);

  const totalDocuments = sumDocuments(knowledgeBases);
  const registeredKnowledgeBaseCount = knowledgeBases.length > 0 ? knowledgeBases.length : null;
  const populatedCount = knowledgeBaseData.data.metricsSource === "knowledge-base-catalog"
    ? populatedKnowledgeBaseCount(knowledgeBases)
    : null;
  const releaseCoverageStatus = populatedCount === null || registeredKnowledgeBaseCount === null
    ? "unknown"
    : hasPopulatedRequiredKnowledgeBases(knowledgeBases)
      ? "core-ready"
      : "core-incomplete";
  const selectedKnowledgeBase =
    knowledgeBases.find((item) => item.id === selectedKnowledgeBaseId) ??
    activeItems[0] ??
    knowledgeBases[0];
  const selectedCategory = selectedKnowledgeBase
    ? productCategories.find((category) => category.id === categoryForKnowledgeBase(selectedKnowledgeBase))
    : undefined;
  const activeCategoryItems = activeCategory === allCategory
    ? knowledgeBases
    : productCategories.find((category) => category.id === activeCategory)?.items ?? [];
  const activeCategorySourceCollections = sourceCollectionsFromKnowledgeBases(activeCategoryItems);
  const activeCategoryDocumentsHref = knowledgeBaseCategoryDocumentsHref(activeCategorySourceCollections);

  const unavailableState = knowledgeBaseData.status === "error"
    ? { title: "知识库读取失败", description: "当前无法读取知识库目录，请稍后重试。" }
    : knowledgeBaseData.status === "empty" || (knowledgeBaseData.status !== "loading" && knowledgeBases.length === 0)
      ? { title: "暂无可用知识库", description: "当前角色下没有可读取的知识库目录。" }
      : null;

  function recordKnowledgeBaseAction(item: ReplicaKnowledgeBaseItem, action: string) {
    setSelectedKnowledgeBaseId(item.id);
    setDetailOpen(true);
    setNotice(`${action}「${item.name}」已准备好，请在右侧查看分类、权限和可调用入口。`);
  }

  return (
    <main
      className="replica-page replica-page-standard"
      data-replica-source={knowledgeBaseData.source}
      data-replica-status={knowledgeBaseData.status}
    >
      <ReplicaPageHeader
        kicker="知识库"
        title="审计知识库"
        description="只保留审计工作需要的法规、监管规则、支付目录、风险清单和个人资料；每份原文都可追溯、预览和按权限下载。"
        actions={
          <button type="button" className="replica-primary-button" onClick={() => setActiveCategory("my")}>
            我的审计资料
          </button>
        }
      />

      <section className="replica-kb-summary-band" aria-label="知识库数据口径">
        <article>
          <span>审计知识库</span>
          <strong>{registeredKnowledgeBaseCount ?? "待同步"}</strong>
          <p>其他领域知识暂不进入产品前台</p>
        </article>
        <article>
          <span>文档数</span>
          <strong>{formatDocumentCount(totalDocuments, false)}</strong>
          <p>{knowledgeBaseData.source === "fixture" ? "本地静态目录" : "来自当前知识目录"}</p>
        </article>
        <article>
          <span>原文能力</span>
          <strong>可追溯</strong>
          <p>预览、下载和来源版本</p>
        </article>
        <article>
          <span>同步状态</span>
          <strong>{knowledgeBaseSyncStatus(knowledgeBases)}</strong>
          <p>按实际文档装载状态</p>
        </article>
      </section>

      <section
        className={`replica-kb-coverage-state is-${releaseCoverageStatus}`}
        aria-label="知识库发布覆盖"
        data-knowledge-release-scope={releaseKnowledgeScope.id}
        data-coverage-status={releaseCoverageStatus}
      >
        <div>
          <span>轻量发布范围</span>
          <strong>审计核心知识</strong>
        </div>
        {releaseCoverageStatus === "unknown" ? (
          <p>文档指标尚未同步；页面不会用空卡片冒充可用知识库。</p>
        ) : releaseCoverageStatus === "core-ready" ? (
          <p>
            五个核心审计来源已装载；其他领域继续保留在后台，但不进入当前产品前台。
          </p>
        ) : (
          <p>
            当前尚未达到五个核心审计来源的发布门槛，缺失来源不会以空数据冒充。
          </p>
        )}
      </section>

      <section className="replica-panel">
        <div className="replica-toolbar">
          <label className="replica-search">
            <span aria-hidden="true">⌕</span>
            <input
              value={query}
              onChange={(event) => setQuery(event.target.value)}
              placeholder="搜索知识库、规则或材料"
            />
          </label>
          <div className="replica-filter-group" aria-label="知识库分类">
            <ReplicaFilterButton value={allCategory} activeValue={activeCategory} onSelect={setActiveCategory}>
              <span>全部</span>
              <em>{knowledgeBases.length}</em>
            </ReplicaFilterButton>
            {productCategories.map((category) => (
              <ReplicaFilterButton key={category.id} value={category.id} activeValue={activeCategory} onSelect={setActiveCategory}>
                <span>{category.title}</span>
                <em>{category.items.length}</em>
              </ReplicaFilterButton>
            ))}
          </div>
        </div>

        <div className="replica-kb-category-grid" aria-label="知识库分类卡片">
          {productCategories.map((category) => (
            <button
              key={category.id}
              type="button"
              className={`replica-kb-category-card tone-${category.tone} ${activeCategory === category.id ? "is-active" : ""}`}
              onClick={() => setActiveCategory(category.id)}
            >
              <span>{category.title}</span>
              <strong>{category.items.length}</strong>
              <p>{category.description}</p>
              <small>{formatDocumentCount(sumDocuments(category.items))}</small>
            </button>
          ))}
        </div>

        <div className="replica-statebar" aria-label="知识库列表状态">
          <span>{activeCategory === allCategory ? "全部知识库" : productCategories.find((item) => item.id === activeCategory)?.title}</span>
          <strong>{activeItems.length} / {knowledgeBases.length}</strong>
          <span>{query.trim() ? `关键词：${query.trim()}` : "按产品分类展示"}</span>
          <span>{knowledgeBaseData.data.canUploadPersonal ? "支持我的知识库" : "个人上传待开通"}</span>
          <Link href={activeCategoryDocumentsHref}>
            {activeCategory === allCategory ? "查看全部原文档" : "查看分类原文档"}
          </Link>
        </div>

        {notice && <ReplicaNotice>{notice}</ReplicaNotice>}

        {knowledgeBaseData.status === "loading" ? (
          <div className="replica-kb-skeleton-grid" aria-label="知识库加载中" aria-busy="true">
            {Array.from({ length: 6 }).map((_, i) => (
              <div key={i} className="replica-kb-skeleton-card">
                <div className="replica-kb-skeleton-line replica-kb-skeleton-line--title" />
                <div className="replica-kb-skeleton-line" />
                <div className="replica-kb-skeleton-line replica-kb-skeleton-line--short" />
              </div>
            ))}
          </div>
        ) : unavailableState ? (
          <ReplicaEmptyState title={unavailableState.title} description={unavailableState.description} />
        ) : activeItems.length === 0 ? (
          <ReplicaEmptyState title="未找到知识库" description="调整关键词或切换分类后重试。" />
        ) : (
          <div className="replica-kb-workbench">
            <div className="replica-kb-grid">
              {activeItems.map((item) => (
                <article
                  key={item.id}
                  className={`replica-kb-card ${selectedKnowledgeBase?.id === item.id ? "is-selected" : ""}`}
                >
                  <div className="replica-kb-card-head">
                    <span>{productCategories.find((category) => category.id === categoryForKnowledgeBase(item))?.title ?? item.scope}</span>
                    <button type="button" aria-label={`查看知识库：${item.name}`} onClick={() => recordKnowledgeBaseAction(item, "查看")}>
                      查看
                    </button>
                  </div>
                  <h2>{item.name}</h2>
                  <div className="replica-kb-owner">权限：{item.scope === "个人知识库" ? "仅本人" : "按项目角色"}</div>
                  <p>{item.description}</p>
                  <dl className="replica-kb-stats">
                    <div>
                      <dt>文档数</dt>
                      <dd>{formatDocumentCount(documentCountForItem(item), false)}</dd>
                    </div>
                    <div>
                      <dt>同步状态</dt>
                      <dd>{knowledgeBaseSyncStatus([item])}</dd>
                    </div>
                    <div>
                      <dt>原文</dt>
                      <dd>可预览下载</dd>
                    </div>
                  </dl>
                </article>
              ))}
            </div>

            {selectedKnowledgeBase && detailOpen ? (
              <aside className="replica-kb-detail" aria-label="知识库详情">
                <div className="replica-detail-head">
                  <span>{selectedCategory?.title ?? selectedKnowledgeBase.scope}</span>
                  <button type="button" aria-label="关闭知识库详情" onClick={() => setDetailOpen(false)}>×</button>
                </div>
                <div className="replica-kb-scope-pill">{selectedKnowledgeBase.scope}</div>
                <h2>{selectedKnowledgeBase.name}</h2>
                <p>{selectedKnowledgeBase.description}</p>
                <dl>
                  <div>
                    <dt>权限</dt>
                    <dd>{selectedKnowledgeBase.scope === "个人知识库" ? "仅限本人" : "按角色读取"}</dd>
                  </div>
                  <div>
                    <dt>文档数</dt>
                    <dd>{formatDocumentCount(documentCountForItem(selectedKnowledgeBase), false)}</dd>
                  </div>
                  <div>
                    <dt>同步状态</dt>
                    <dd>{knowledgeBaseSyncStatus([selectedKnowledgeBase])}</dd>
                  </div>
                </dl>
                <section className="replica-kb-next-panel" aria-label="知识库权限说明">
                  <h3>{selectedKnowledgeBase.scope === "个人知识库" ? "我的资料权限" : "原文溯源"}</h3>
                  <p>
                    {selectedKnowledgeBase.scope === "个人知识库"
                      ? "个人知识库仅本人可见；需要纳入项目共享时，由管理员配置范围。"
                      : "原文档保留来源、版本与文件校验信息，可用于审计检索和 AI 审证。"}
                  </p>
                </section>
                <div className="replica-kb-detail-actions">
                  {sourceCollectionsFromKnowledgeBaseId(selectedKnowledgeBase.id).length > 0 ? (
                    <Link href={knowledgeBaseDocumentsHref(selectedKnowledgeBase)}>查看原文档</Link>
                  ) : (
                    <button type="button" onClick={() => recordKnowledgeBaseAction(selectedKnowledgeBase, "查看原文档")}>查看原文档</button>
                  )}
                  {sourceCollectionsFromKnowledgeBaseId(selectedKnowledgeBase.id).length > 0 ? (
                    <Link href={knowledgeBaseChatHref(selectedKnowledgeBase)}>进入 AI 对话</Link>
                  ) : (
                    <button type="button" onClick={() => recordKnowledgeBaseAction(selectedKnowledgeBase, "进入 AI 对话")}>进入 AI 对话</button>
                  )}
                </div>
              </aside>
            ) : null}
          </div>
        )}
      </section>
    </main>
  );
}

function formatDocumentCount(value: number | null, includeUnit = true): string {
  if (value === null) {
    return "待同步";
  }
  return `${value.toLocaleString()}${includeUnit ? " 份文档" : ""}`;
}

function sourceCollectionsFromKnowledgeBaseId(id: string): readonly SourceCollection[] {
  const mappedSources = knowledgeBaseSourceCollectionMap[id];
  if (mappedSources) {
    return mappedSources;
  }
  const sourceCollection = id.startsWith("kb-") ? id.slice("kb-".length) : "";
  return isSourceCollectionValue(sourceCollection) ? [sourceCollection] : [];
}

function knowledgeBaseDocumentsHref(item: ReplicaKnowledgeBaseItem): string {
  return knowledgeBaseCategoryDocumentsHref(sourceCollectionsFromKnowledgeBaseId(item.id));
}

function knowledgeBaseCategoryDocumentsHref(sourceCollections: readonly SourceCollection[]): string {
  return routeWithSourceCollections("/documents", sourceCollections);
}

function routeWithSourceCollections(route: "/documents", sourceCollections: readonly SourceCollection[]): string {
  if (sourceCollections.length === 0) {
    return route;
  }
  const params = new URLSearchParams();
  for (const sourceCollection of sourceCollections) {
    params.append("source_collection", sourceCollection);
  }
  return `${route}?${params.toString()}`;
}

function knowledgeBaseChatHref(item: ReplicaKnowledgeBaseItem): string {
  const params = new URLSearchParams();
  params.set("question", `请基于「${item.name}」回答审计问题`);
  for (const sourceCollection of sourceCollectionsFromKnowledgeBaseId(item.id)) {
    params.append("source_collection", sourceCollection);
  }
  return `/chat?${params.toString()}`;
}

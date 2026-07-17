"use client";

import { useMemo, useState } from "react";
import Link from "next/link";

import {
  ReplicaEmptyState,
  ReplicaFilterButton,
  ReplicaNotice,
  ReplicaPageHeader,
  ReplicaRuntimeBadge
} from "@/components/replica/replica-page-kit";
import { useReplicaKnowledgeBaseData } from "@/components/replica/use-replica-runtime";
import type { SourceCollection } from "@/lib/api-types";
import type { ReplicaKnowledgeBaseItem } from "@/lib/replica-adapters";
import { isSourceCollectionValue } from "@/lib/source-collection-catalog";

type ProductKnowledgeCategoryId =
  | "all"
  | "my"
  | "national"
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
    id: "national",
    title: "国家制度文档",
    description: "国家政策、综合制度、财政采购、公开披露和行业管理文件。",
    tone: "green"
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
    "personal-materials"
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
  return "national";
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

function chunkCountForItem(item: ReplicaKnowledgeBaseItem): number | null {
  return typeof item.chunkCount === "number" && item.chunkCount >= 0 ? item.chunkCount : null;
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

function sumChunks(items: readonly ReplicaKnowledgeBaseItem[]): number | null {
  if (items.length === 0) {
    return null;
  }
  let total = 0;
  for (const item of items) {
    const count = chunkCountForItem(item);
    if (count === null) {
      return null;
    }
    total += count;
  }
  return total;
}

function newestUpdatedAt(items: readonly ReplicaKnowledgeBaseItem[]) {
  return items.find((item) => (documentCountForItem(item) ?? 0) > 0)?.updatedAt ?? "待同步";
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
    || items.some((item) => documentCountForItem(item) === null || chunkCountForItem(item) === null)
  ) {
    return null;
  }
  return items.filter((item) => (
    (documentCountForItem(item) ?? 0) > 0 || (chunkCountForItem(item) ?? 0) > 0
  )).length;
}

function hasPopulatedRequiredKnowledgeBases(items: readonly ReplicaKnowledgeBaseItem[]): boolean {
  return releaseKnowledgeScope.requiredSourceCollections.every((requiredSource) => (
    items.some((item) => (
      sourceCollectionsFromKnowledgeBaseId(item.id).includes(requiredSource)
      && ((documentCountForItem(item) ?? 0) > 0 || (chunkCountForItem(item) ?? 0) > 0)
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
  const knowledgeBases = knowledgeBaseData.data.knowledgeBases;

  const productCategories = useMemo(() => buildProductCategories(knowledgeBases), [knowledgeBases]);
  const activeItems = useMemo(() => {
    const scopedItems = activeCategory === allCategory
      ? knowledgeBases
      : productCategories.find((category) => category.id === activeCategory)?.items ?? [];
    return scopedItems.filter((item) => matchesKnowledgeBase(item, query));
  }, [activeCategory, knowledgeBases, productCategories, query]);

  const totalDocuments = knowledgeBaseData.data.summary?.totalDocumentCount ??
    (knowledgeBaseData.source === "fixture" ? sumDocuments(knowledgeBases) : null);
  const totalChunks = knowledgeBaseData.data.summary?.currentSearchEmbeddingCount ??
    (knowledgeBaseData.source === "fixture"
      ? knowledgeBaseData.data.currentSearchEmbeddingCount ?? sumChunks(knowledgeBases)
      : null);
  const registeredKnowledgeBaseCount = knowledgeBaseData.data.summary?.sourceCollectionCount
    ?? (knowledgeBases.length > 0 ? knowledgeBases.length : null);
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
  const activeCategoryGraphHref = knowledgeBaseCategoryGraphHref(activeCategorySourceCollections);

  const unavailableState = knowledgeBaseData.status === "loading"
    ? { title: "知识库加载中", description: "正在读取当前可访问的知识库目录。" }
    : knowledgeBaseData.status === "error"
      ? { title: "知识库读取失败", description: "当前无法读取知识库目录，请稍后重试。" }
      : knowledgeBaseData.status === "empty" || knowledgeBases.length === 0
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
        title="知识库分类"
        description="按医院审计人员可理解的业务类别组织知识库，隐藏内部来源字段，只保留可检索、可引用、可授权的内容入口。"
        actions={
          <>
            <ReplicaRuntimeBadge
              source={knowledgeBaseData.source}
              status={knowledgeBaseData.status}
              issueCount={knowledgeBaseData.issues.length}
            />
            <button type="button" className="replica-primary-button" onClick={() => setActiveCategory("my")}>
              我的知识库
            </button>
          </>
        }
      />

      <section className="replica-kb-summary-band" aria-label="知识库数据口径">
        <article>
          <span>装载覆盖</span>
          <strong>{populatedCount === null || registeredKnowledgeBaseCount === null
            ? "待同步"
            : `${populatedCount} / ${registeredKnowledgeBaseCount}`}</strong>
          <p>发布口径：{releaseKnowledgeScope.label}</p>
        </article>
        <article>
          <span>文档数</span>
          <strong>{formatDocumentCount(totalDocuments, false)}</strong>
          <p>{knowledgeBaseData.source === "fixture" ? "本地静态目录" : "来自当前知识目录"}</p>
        </article>
        <article>
          <span>知识片段</span>
          <strong>{formatChunkCount(totalChunks, false)}</strong>
          <p>当前可用于检索的知识片段数量</p>
        </article>
        <article>
          <span>数据来源</span>
          <strong>{knowledgeBaseData.source === "fixture" ? "本地目录" : "知识目录"}</strong>
          <p>页面仅展示，不执行生产写入</p>
        </article>
      </section>

      <section
        className={`replica-kb-coverage-state is-${releaseCoverageStatus}`}
        aria-label="知识库发布覆盖"
        data-knowledge-release-scope={releaseKnowledgeScope.id}
        data-coverage-status={releaseCoverageStatus}
      >
        <div>
          <span>当前发布范围</span>
          <strong>{releaseKnowledgeScope.label}</strong>
        </div>
        {releaseCoverageStatus === "unknown" ? (
          <p>知识集合装载指标尚未同步，本页面不会把未知状态显示为全量可用。</p>
        ) : releaseCoverageStatus === "core-ready" ? (
          <p>
            已装载 {populatedCount} / {registeredKnowledgeBaseCount} 个注册集合；本次仅承诺核心范围，
            其余空集合继续标记为待激活。
          </p>
        ) : (
          <p>
            已装载 {populatedCount} / {registeredKnowledgeBaseCount} 个注册集合，尚未达到
            {releaseKnowledgeScope.label}的发布门槛。
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
              <small>{formatDocumentCount(sumDocuments(category.items))} · {formatChunkCount(sumChunks(category.items))}</small>
            </button>
          ))}
        </div>

        <div className="replica-statebar" aria-label="知识库列表状态">
          <span>{activeCategory === allCategory ? "全部知识库" : productCategories.find((item) => item.id === activeCategory)?.title}</span>
          <strong>{activeItems.length} / {knowledgeBases.length}</strong>
          <span>{query.trim() ? `关键词：${query.trim()}` : "按产品分类展示"}</span>
          <span>{knowledgeBaseData.data.canUploadPersonal ? "支持我的知识库" : "个人上传待开通"}</span>
          <Link href={activeCategoryDocumentsHref}>
            {activeCategory === allCategory ? "检索全部目录" : "检索当前分类"}
          </Link>
          <Link href={activeCategoryGraphHref}>
            {activeCategory === allCategory ? "查看全部图谱" : "查看当前图谱"}
          </Link>
        </div>

        {notice && <ReplicaNotice>{notice}</ReplicaNotice>}

        {unavailableState ? (
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
                      <dt>知识片段</dt>
                      <dd>{formatChunkCount(chunkCountForItem(item), false)}</dd>
                    </div>
                    <div>
                      <dt>同步</dt>
                      <dd>{item.updatedAt}</dd>
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
                    <dt>知识片段</dt>
                    <dd>{formatChunkCount(chunkCountForItem(selectedKnowledgeBase), false)}</dd>
                  </div>
                  <div>
                    <dt>最后同步</dt>
                    <dd>{newestUpdatedAt([selectedKnowledgeBase])}</dd>
                  </div>
                </dl>
                <div className="replica-kb-tags">
                  {selectedKnowledgeBase.tags.slice(0, 4).map((tag) => (
                    <span key={tag}>{tag.replace(" chunks", " 片段")}</span>
                  ))}
                </div>
                <section className="replica-kb-next-panel" aria-label="知识库权限说明">
                  <h3>{selectedKnowledgeBase.scope === "个人知识库" ? "我的知识库权限" : "可调用入口"}</h3>
                  <p>
                    {selectedKnowledgeBase.scope === "个人知识库"
                      ? "个人知识库仅本人可见；需要纳入项目共享时，由管理员配置范围。"
                      : "该知识库可用于文档检索、AI 对话和审计专题核验。"}
                  </p>
                </section>
                <div className="replica-kb-detail-actions">
                  {sourceCollectionsFromKnowledgeBaseId(selectedKnowledgeBase.id).length > 0 ? (
                    <Link href={knowledgeBaseDocumentsHref(selectedKnowledgeBase)}>打开目录</Link>
                  ) : (
                    <button type="button" onClick={() => recordKnowledgeBaseAction(selectedKnowledgeBase, "打开目录")}>打开目录</button>
                  )}
                  {sourceCollectionsFromKnowledgeBaseId(selectedKnowledgeBase.id).length > 0 ? (
                    <Link href={knowledgeBaseChatHref(selectedKnowledgeBase)}>进入 AI 对话</Link>
                  ) : (
                    <button type="button" onClick={() => recordKnowledgeBaseAction(selectedKnowledgeBase, "进入 AI 对话")}>进入 AI 对话</button>
                  )}
                  {sourceCollectionsFromKnowledgeBaseId(selectedKnowledgeBase.id).length > 0 ? (
                    <Link href={knowledgeBaseGraphHref(selectedKnowledgeBase)}>查看图谱</Link>
                  ) : (
                    <button type="button" onClick={() => recordKnowledgeBaseAction(selectedKnowledgeBase, "查看图谱")}>查看图谱</button>
                  )}
                  <button type="button" onClick={() => recordKnowledgeBaseAction(selectedKnowledgeBase, "权限设置")}>权限设置</button>
                </div>
              </aside>
            ) : null}
          </div>
        )}
      </section>
    </main>
  );
}

function formatChunkCount(value: number | null, includeUnit = true): string {
  if (value === null) {
    return "待同步";
  }
  return `${value.toLocaleString()}${includeUnit ? " 个片段" : ""}`;
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

function knowledgeBaseGraphHref(item: ReplicaKnowledgeBaseItem): string {
  return knowledgeBaseCategoryGraphHref(sourceCollectionsFromKnowledgeBaseId(item.id));
}

function knowledgeBaseCategoryGraphHref(sourceCollections: readonly SourceCollection[]): string {
  return routeWithSourceCollections("/graph", sourceCollections);
}

function routeWithSourceCollections(route: "/documents" | "/graph", sourceCollections: readonly SourceCollection[]): string {
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

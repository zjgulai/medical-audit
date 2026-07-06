import Link from "next/link";

import {
  conversationDocuments,
  documentSearchHistory,
  knowledgeDocuments,
  type DocumentCategoryStat,
  type PortalDocumentItem
} from "@/lib/portal-data";

const DEFAULT_QUERY = "劳动争议司法案件解释";
const resultDocuments = [...knowledgeDocuments, ...conversationDocuments];
const workspaceDocumentCategoryStats: readonly DocumentCategoryStat[] = [
  {
    id: "workspace-doc-laws",
    name: "法律法规库",
    scope: "公开知识库",
    sourceCollection: "legal-regulations",
    documentCount: 1362,
    description: "法律、法规、规章、司法解释"
  },
  {
    id: "workspace-doc-policy",
    name: "政策文件库",
    scope: "公开知识库",
    sourceCollection: "policy-documents",
    documentCount: 945,
    description: "政策通知、管理办法、专项方案"
  },
  {
    id: "workspace-doc-case",
    name: "审计案例库",
    scope: "系统知识库",
    sourceCollection: "audit-cases",
    documentCount: 842,
    description: "典型问题、案例摘要、处理口径"
  },
  {
    id: "workspace-doc-faq",
    name: "常见问题库",
    scope: "系统知识库",
    sourceCollection: "faq",
    documentCount: 286,
    description: "常用问答、复核口径、操作提示"
  },
  {
    id: "workspace-doc-research",
    name: "研究报告库",
    scope: "公开知识库",
    sourceCollection: "research-reports",
    documentCount: 193,
    description: "研究资料、行业报告、专题分析"
  },
  {
    id: "workspace-doc-events",
    name: "热点事件库",
    scope: "公开知识库",
    sourceCollection: "hot-events",
    documentCount: 75,
    description: "热点事件、舆情材料、风险线索"
  },
  {
    id: "workspace-doc-books",
    name: "书本期刊库",
    scope: "公开知识库",
    sourceCollection: "books-journals",
    documentCount: 214,
    description: "教材、期刊、专著和参考资料"
  }
];

function searchHref(query = DEFAULT_QUERY) {
  return `/documents?q=${encodeURIComponent(query)}`;
}

function chatHref(query = DEFAULT_QUERY) {
  return `/chat?question=${encodeURIComponent(query)}`;
}

export function DocumentSearchHome() {
  const totalDocuments = workspaceDocumentCategoryStats.reduce((sum, item) => sum + item.documentCount, 0);

  return (
    <main className="mx-auto grid max-w-[78rem] gap-5">
      <section className="relative overflow-hidden rounded-[var(--audit-radius-lg)] border border-[var(--audit-line)] bg-gradient-to-br from-white via-sky-50/60 to-blue-50/70 p-5 shadow-[0_18px_46px_rgb(23_62_105/0.08)] sm:p-7">
        <div className="absolute right-6 top-5 hidden h-24 w-32 rounded-[18px] border border-blue-200/80 bg-white/70 shadow-[0_18px_36px_rgb(29_117_201/0.12)] md:block">
          <div className="absolute left-5 top-5 h-10 w-10 rounded-full border-[5px] border-[var(--audit-primary)]" />
          <div className="absolute left-[4.25rem] top-[3.75rem] h-1.5 w-10 rotate-45 rounded-full bg-[var(--audit-primary)]" />
          <div className="absolute inset-y-0 left-3 w-px bg-blue-100" />
          <div className="absolute inset-y-0 right-5 w-px bg-blue-100" />
        </div>

        <div className="max-w-2xl">
          <p className="audit-kicker">文档检索</p>
          <h1 className="audit-page-title mt-2">文档检索</h1>
          <p className="audit-copy mt-2">快速检索系统内的相关文档，先找到依据，再进入审计问答和底稿处理。</p>
        </div>

        <div className="mt-8 flex flex-col gap-3 lg:flex-row lg:items-center">
          <label className="sr-only" htmlFor="workspace-document-search">
            文档检索关键词
          </label>
          <div className="flex min-h-14 flex-1 overflow-hidden rounded-[var(--audit-radius-md)] border-2 border-[var(--audit-primary)] bg-white shadow-[0_14px_28px_rgb(29_117_201/0.12)]">
            <input
              aria-label="文档检索关键词"
              className="min-w-0 flex-1 px-4 text-base font-semibold text-[var(--audit-ink)] outline-none"
              defaultValue={DEFAULT_QUERY}
              id="workspace-document-search"
            />
            <label className="flex shrink-0 items-center gap-2 border-l border-[var(--audit-line)] px-3 text-sm font-medium text-[var(--audit-ink-muted)]">
              <input aria-label="仅标题" className="h-4 w-4 accent-[var(--audit-primary)]" type="checkbox" />
              仅标题
            </label>
            <Link
              className="audit-focus-ring flex min-w-28 shrink-0 items-center justify-center bg-[var(--audit-primary)] px-5 text-sm font-semibold text-white"
              href={searchHref()}
            >
              搜索
            </Link>
          </div>
          <Link
            className="audit-focus-ring inline-flex min-h-12 items-center justify-center rounded-full bg-[var(--audit-primary)] px-6 text-sm font-semibold text-white shadow-[0_14px_30px_rgb(29_117_201/0.2)]"
            href={chatHref()}
          >
            检索AI+
          </Link>
        </div>
      </section>

      <section className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h2 className="audit-section-title">搜索历史</h2>
          <div className="mt-3 flex flex-wrap gap-2">
            {documentSearchHistory.map((item) => (
              <Link
                className="audit-focus-ring rounded-[var(--audit-radius-md)] bg-[var(--audit-surface-muted)] px-4 py-2 text-sm font-semibold text-[var(--audit-ink-muted)] hover:bg-[var(--audit-primary-soft)] hover:text-[var(--audit-primary)]"
                href={searchHref(item)}
                key={item}
              >
                {item}
              </Link>
            ))}
          </div>
        </div>
        <Link className="audit-focus-ring audit-btn audit-btn-secondary" href="/documents">
          查看全部文档
        </Link>
      </section>

      <section className="rounded-[var(--audit-radius-lg)] border border-blue-100 bg-[linear-gradient(110deg,rgb(219_235_255/.9),rgb(238_246_255/.96))] p-4 shadow-[0_16px_34px_rgb(23_62_105/0.08)]">
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
          {workspaceDocumentCategoryStats.map((category) => (
            <LibraryTile category={category} key={category.id} />
          ))}
        </div>
      </section>

      <section className="grid gap-5 xl:grid-cols-[1fr_1.25fr]">
        <DocumentList title="对话文档" documents={conversationDocuments} />
        <DocumentList title="知识库文档" documents={knowledgeDocuments} />
      </section>

      <section className="grid gap-5 lg:grid-cols-[16rem_1fr]">
        <aside className="grid gap-3">
          <div className="rounded-full border border-[var(--audit-line)] bg-white px-3 py-2 text-sm font-semibold text-[var(--audit-ink-muted)]">
            文档库：7 类 / {totalDocuments.toLocaleString()} 份
          </div>
          {workspaceDocumentCategoryStats.map((category) => (
            <Link
              className="audit-focus-ring rounded-[var(--audit-radius-md)] border border-[var(--audit-line)] bg-white p-3 shadow-[0_8px_18px_rgb(23_62_105/0.04)] hover:border-[var(--audit-primary-line)] hover:bg-[var(--audit-primary-soft)]"
              href={`/documents?source=${encodeURIComponent(category.sourceCollection)}`}
              key={category.id}
            >
              <span className="block text-sm font-semibold text-[var(--audit-ink)]">{category.name}</span>
              <span className="audit-meta mt-1 block">{category.description}</span>
              <span className="mt-2 block text-sm font-semibold text-[var(--audit-primary)]">{category.documentCount.toLocaleString()}</span>
            </Link>
          ))}
        </aside>

        <section className="audit-panel p-5 sm:p-6">
          <div className="flex flex-wrap items-start justify-between gap-3">
            <div>
              <p className="audit-kicker">检索结果</p>
              <h2 className="audit-section-title mt-1">检索结果</h2>
            </div>
            <span className="rounded-full bg-[var(--audit-primary-soft)] px-3 py-1 text-xs font-semibold text-[var(--audit-primary)]">
              关键词：{DEFAULT_QUERY}
            </span>
          </div>
          <div className="mt-4 grid gap-3">
            {resultDocuments.map((document) => (
              <ResultCard document={document} key={document.id} />
            ))}
          </div>
        </section>
      </section>
    </main>
  );
}

function LibraryTile({ category }: { readonly category: DocumentCategoryStat }) {
  return (
    <Link
      className="audit-focus-ring flex min-h-28 flex-col items-center justify-center rounded-[var(--audit-radius-md)] border border-blue-200/80 bg-white/60 p-4 text-center shadow-[0_10px_24px_rgb(29_117_201/0.08)] hover:bg-white"
      href={`/documents?source=${encodeURIComponent(category.sourceCollection)}`}
    >
      <span className="grid size-12 place-items-center rounded-[var(--audit-radius-md)] bg-white text-lg font-bold text-[var(--audit-primary)] shadow-[0_10px_20px_rgb(29_117_201/0.1)]">
        {category.name.slice(0, 1)}
      </span>
      <span className="mt-3 text-sm font-semibold text-[var(--audit-ink)]">{category.name}</span>
      <span className="audit-meta mt-1">{category.documentCount.toLocaleString()}</span>
    </Link>
  );
}

function DocumentList({ title, documents }: { readonly title: string; readonly documents: readonly PortalDocumentItem[] }) {
  return (
    <section className="audit-panel p-5 sm:p-6">
      <div className="flex items-center justify-between gap-3">
        <h2 className="audit-section-title">{title}</h2>
        <Link className="text-sm font-semibold text-[var(--audit-primary)]" href="/documents">
          查看全部
        </Link>
      </div>
      <div className="mt-4 grid gap-3 md:grid-cols-2">
        {documents.map((document) => (
          <Link
            className="audit-focus-ring rounded-[var(--audit-radius-md)] border border-[var(--audit-line)] bg-white p-4 hover:border-[var(--audit-primary-line)] hover:bg-[var(--audit-surface-muted)]"
            href={document.href}
            key={document.id}
          >
            <span className="block truncate text-sm font-semibold text-[var(--audit-ink)]">{document.title}</span>
            <span className="audit-meta mt-1 block">{document.libraryName}</span>
            <span className="audit-meta mt-3 block">{document.updatedAt}</span>
          </Link>
        ))}
      </div>
    </section>
  );
}

function ResultCard({ document }: { readonly document: PortalDocumentItem }) {
  return (
    <article className="rounded-[var(--audit-radius-md)] border border-[var(--audit-line)] bg-white p-4">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0">
          <span className="rounded-full bg-[var(--audit-primary-soft)] px-2.5 py-1 text-xs font-semibold text-[var(--audit-primary)]">
            {document.libraryName}
          </span>
          <h3 className="mt-3 text-base font-semibold text-[var(--audit-ink)]">{document.title}</h3>
          <p className="audit-copy mt-2">{document.summary}</p>
        </div>
        <span className="audit-meta shrink-0">{document.updatedAt}</span>
      </div>
      <div className="mt-4 flex flex-wrap justify-end gap-2">
        <Link className="audit-focus-ring audit-btn audit-btn-secondary" href={document.href}>
          推荐文档
        </Link>
        <Link className="audit-focus-ring audit-btn audit-btn-primary" href={document.chatHref}>
          转入对话
        </Link>
      </div>
    </article>
  );
}

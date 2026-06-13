import { StatusPill } from "@/components/ui/status-pill";
import {
  conversationDocuments,
  documentCategoryStats,
  documentSearchHistory,
  knowledgeDocuments,
  PortalDocumentItem
} from "@/lib/portal-data";

export default function DocumentsPage() {
  const totalDocuments = documentCategoryStats.reduce((sum, category) => sum + category.documentCount, 0);

  return (
    <main className="grid min-w-0 gap-4 xl:grid-cols-[17rem_minmax(0,1fr)_18rem]">
      <aside className="audit-panel-rail min-w-0 p-5">
        <h2 className="audit-section-title">文档源</h2>
        <p className="audit-copy mt-2">按审计材料来源组织检索范围，首期只读展示来源覆盖。</p>
        <div className="mt-5 space-y-3">
          {documentCategoryStats.map((category) => (
            <DocumentSourceCard key={category.id} category={category} />
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
          <StatusPill tone="success">引用优先</StatusPill>
        </div>

        <form className="audit-panel-muted mt-6 p-5" action="/knowledge-query">
          <div className="grid gap-4 lg:grid-cols-[minmax(0,1fr)_8rem]">
            <label className="block">
              <span className="audit-label">审计问题或文档关键词</span>
              <input
                className="audit-focus-ring audit-input mt-2 px-3 py-2.5"
                name="q"
                placeholder="例如：重复收费、目录限制、超量开药"
              />
            </label>
            <label className="audit-focus-ring mt-7 flex items-center gap-2 rounded-[var(--audit-radius-md)] border border-[var(--audit-line)] bg-white px-3 py-2.5 text-sm text-[var(--audit-ink-muted)]">
              <input className="size-4" type="checkbox" name="title_only" value="1" />
              仅标题
            </label>
          </div>
          <div className="mt-4 flex flex-wrap gap-3">
            <button className="audit-focus-ring audit-btn audit-btn-primary" type="submit">
              执行检索
            </button>
            <a
              className="audit-focus-ring audit-btn audit-btn-secondary"
              href="/chat"
            >
              转入 AI 对话
            </a>
          </div>
        </form>

        <div className="mt-5 grid gap-3 sm:grid-cols-3">
          <Metric label="可检索材料" value={totalDocuments.toLocaleString()} />
          <Metric label="结果分组" value="2" />
          <Metric label="引用入口" value="已开启" />
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
              <a
                key={item}
                className="audit-focus-ring block rounded-[var(--audit-radius-md)] bg-[var(--audit-surface-muted)] px-3 py-2 text-sm text-[var(--audit-ink-muted)] hover:bg-[var(--audit-surface-subtle)] hover:text-[var(--audit-ink)]"
                href={`/knowledge-query?q=${encodeURIComponent(item)}`}
              >
                {item}
              </a>
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

function DocumentSourceCard({ category }: { readonly category: (typeof documentCategoryStats)[number] }) {
  return (
    <article className="rounded-[var(--audit-radius-md)] border border-[var(--audit-line)] bg-white p-3">
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <h3 className="truncate text-sm font-semibold text-[var(--audit-ink)]">{category.name}</h3>
          <p className="audit-meta mt-1 truncate">{category.sourceCollection}</p>
        </div>
        <StatusPill tone={category.scope === "公开知识库" ? "neutral" : "info"}>{category.scope}</StatusPill>
      </div>
      <p className="audit-metric-value-sm mt-3">{category.documentCount.toLocaleString()}</p>
      <p className="audit-copy mt-2">{category.description}</p>
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

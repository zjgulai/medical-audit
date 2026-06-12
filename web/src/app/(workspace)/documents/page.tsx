import { StatusPill } from "@/components/ui/status-pill";
import {
  conversationDocuments,
  documentCategoryStats,
  documentSearchHistory,
  knowledgeDocuments,
  PortalDocumentItem
} from "@/lib/portal-data";

export default function DocumentsPage() {
  return (
    <main className="grid gap-5 xl:grid-cols-[minmax(0,1fr)_22rem]">
      <section className="rounded-2xl border border-slate-200 bg-white p-6 shadow-[var(--audit-shadow-card)]">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div>
            <p className="text-sm font-semibold text-blue-700">文档检索</p>
            <h1 className="mt-2 text-3xl font-semibold text-slate-950">材料与知识库统一检索</h1>
          </div>
          <StatusPill tone="success">引用优先</StatusPill>
        </div>

        <form className="mt-6 rounded-2xl border border-slate-200 bg-slate-50 p-4" action="/knowledge-query">
          <div className="grid gap-4 lg:grid-cols-[minmax(0,1fr)_9rem]">
            <label className="block">
              <span className="text-sm font-semibold text-slate-700">审计问题或文档关键词</span>
              <input
                className="audit-focus-ring mt-2 w-full rounded-xl border border-slate-200 bg-white px-3 py-2.5 text-sm"
                name="q"
                placeholder="例如：重复收费、目录限制、超量开药"
              />
            </label>
            <label className="mt-7 flex items-center gap-2 rounded-xl border border-slate-200 bg-white px-3 py-2.5 text-sm text-slate-700">
              <input className="size-4" type="checkbox" name="title_only" value="1" />
              仅标题
            </label>
          </div>
          <div className="mt-4 flex flex-wrap gap-3">
            <button className="audit-focus-ring rounded-xl bg-blue-600 px-4 py-2.5 text-sm font-semibold text-white hover:bg-blue-700" type="submit">
              执行检索
            </button>
            <a
              className="audit-focus-ring rounded-xl border border-blue-200 bg-white px-4 py-2.5 text-sm font-semibold text-blue-700 hover:bg-blue-50"
              href="/chat"
            >
              转入 AI 对话
            </a>
          </div>
        </form>

        <div className="mt-5 grid gap-4 lg:grid-cols-4">
          {documentCategoryStats.map((category) => (
            <article key={category.id} className="rounded-2xl border border-slate-200 bg-slate-50 p-4">
              <div className="flex items-start justify-between gap-3">
                <h2 className="text-base font-semibold text-slate-950">{category.name}</h2>
                <StatusPill tone={category.scope === "公开知识库" ? "neutral" : "info"}>{category.scope}</StatusPill>
              </div>
              <p className="mt-4 text-2xl font-semibold text-slate-950">{category.documentCount.toLocaleString()}</p>
              <p className="mt-1 text-xs text-slate-500">{category.sourceCollection}</p>
              <p className="mt-3 text-sm leading-6 text-slate-600">{category.description}</p>
            </article>
          ))}
        </div>

        <div className="mt-6 grid gap-5 lg:grid-cols-2">
          <DocumentList title="对话文档" documents={conversationDocuments} />
          <DocumentList title="知识库文档" documents={knowledgeDocuments} />
        </div>
      </section>

      <aside className="space-y-4">
        <section className="rounded-2xl border border-slate-200 bg-white p-5 shadow-[var(--audit-shadow-card)]">
          <h2 className="text-lg font-semibold text-slate-950">搜索历史</h2>
          <div className="mt-4 space-y-2">
            {documentSearchHistory.map((item) => (
              <a
                key={item}
                className="audit-focus-ring block rounded-xl bg-slate-50 px-3 py-2 text-sm text-slate-700 hover:bg-slate-100"
                href={`/knowledge-query?q=${encodeURIComponent(item)}`}
              >
                {item}
              </a>
            ))}
          </div>
        </section>

        <a className="audit-focus-ring block rounded-2xl border border-blue-100 bg-blue-50 p-5 shadow-[var(--audit-shadow-card)]" href="/chat">
          <p className="text-sm font-semibold text-blue-700">AI 对话</p>
          <h2 className="mt-2 text-lg font-semibold text-slate-950">带着材料进入审证</h2>
          <p className="mt-2 text-sm leading-6 text-slate-600">检索不到充分引用时，转入 AI 对话继续限定来源、补充问题和形成复核清单。</p>
        </a>
      </aside>
    </main>
  );
}

function DocumentList({ title, documents }: { readonly title: string; readonly documents: readonly PortalDocumentItem[] }) {
  return (
    <section className="rounded-2xl border border-slate-200 bg-slate-50 p-4">
      <h2 className="text-lg font-semibold text-slate-950">{title}</h2>
      <div className="mt-4 space-y-3">
        {documents.map((document) => (
          <article key={document.id} className="rounded-xl border border-slate-200 bg-white p-4">
            <div className="flex flex-wrap items-start justify-between gap-3">
              <div>
                <h3 className="text-base font-semibold text-slate-950">{document.title}</h3>
                <p className="mt-1 text-xs text-slate-500">
                  {document.libraryName} · {document.owner} · {document.updatedAt}
                </p>
              </div>
              <StatusPill tone={document.status === "可审证" ? "success" : document.status === "待补引用" ? "warning" : "neutral"}>
                {document.status}
              </StatusPill>
            </div>
            <p className="mt-3 text-sm leading-6 text-slate-600">{document.summary}</p>
            <div className="mt-4 flex flex-wrap gap-2">
              <a className="audit-focus-ring rounded-xl bg-blue-600 px-3 py-2 text-sm font-semibold text-white hover:bg-blue-700" href={document.href}>
                查看引用
              </a>
              <a
                className="audit-focus-ring rounded-xl border border-blue-200 bg-white px-3 py-2 text-sm font-semibold text-blue-700 hover:bg-blue-50"
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

import { SearchBackendStatusPill } from "@/components/portal/search-backend-status-pill";
import { StatusPill } from "@/components/ui/status-pill";
import { KnowledgeBaseCard, knowledgeBases } from "@/lib/portal-data";

const totalDocumentCount = knowledgeBases.reduce((sum, kb) => sum + kb.documentCount, 0);
const totalCharacterCount = knowledgeBases.reduce((sum, kb) => sum + kb.characterCount, 0);
const totalLinkedAppCount = knowledgeBases.reduce((sum, kb) => sum + kb.linkedAppCount, 0);

export default function KnowledgeBasePage() {
  return (
    <main className="grid min-w-0 gap-4 xl:grid-cols-[17rem_minmax(0,1fr)_18rem]">
      <aside className="audit-panel-rail min-w-0 p-5">
        <h2 className="audit-section-title">知识库目录</h2>
        <p className="audit-copy mt-2">首期不在前台变更索引，只展示范围、负责人和可检索状态。</p>
        <div className="mt-3">
          <SearchBackendStatusPill />
        </div>
        <div className="mt-5 space-y-3">
          {knowledgeBases.map((kb) => (
            <KnowledgeBaseDirectoryItem key={kb.id} kb={kb} />
          ))}
        </div>
      </aside>

      <section className="audit-panel min-w-0 p-6">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div className="min-w-0">
            <p className="audit-kicker">知识库</p>
            <h1 className="audit-page-title">个人、系统、公开知识库</h1>
            <p className="audit-copy mt-2 max-w-3xl">查看当前项目可引用的知识资产，不在门户中直接发布或回滚索引。</p>
          </div>
          <StatusPill tone="info">首期只读</StatusPill>
        </div>

        <div className="mt-6 grid gap-4">
          {knowledgeBases.map((kb) => (
            <article key={kb.id} className="audit-panel-muted min-w-0 p-4">
              <div className="flex items-start justify-between gap-3">
                <div className="min-w-0">
                  <h2 className="audit-card-title">{kb.name}</h2>
                  <p className="audit-meta mt-1">{kb.scope}</p>
                </div>
                <StatusPill tone={kb.status === "可检索" ? "success" : "neutral"}>{kb.status}</StatusPill>
              </div>
              <p className="audit-copy mt-4">{kb.description}</p>
              <div className="mt-5 grid grid-cols-3 gap-2">
                <Metric label="文档数" value={kb.documentCount.toLocaleString()} />
                <Metric label="字符数" value={`${Math.round(kb.characterCount / 10000).toLocaleString()}万`} />
                <Metric label="应用数" value={String(kb.linkedAppCount)} />
              </div>
              <p className="audit-meta mt-4">负责人：{kb.owner}</p>
            </article>
          ))}
        </div>

        <section className="audit-panel-muted mt-6 p-4">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <h2 className="audit-section-title">知识资产明细</h2>
            <StatusPill tone="neutral">{knowledgeBases.length} 个知识库</StatusPill>
          </div>
          <div className="audit-table-shell mt-4 max-w-full overflow-x-auto">
            <table className="audit-table min-w-[52rem]">
            <thead>
              <tr>
                <th>知识库</th>
                <th>类型</th>
                <th>文档数</th>
                <th>字符数</th>
                <th>关联应用数</th>
                <th>描述</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-[var(--audit-line-soft)]">
              {knowledgeBases.map((kb) => (
                <tr key={kb.id}>
                  <td className="font-semibold text-[var(--audit-ink)]">{kb.name}</td>
                  <td className="text-[var(--audit-ink-muted)]">{kb.scope}</td>
                  <td className="text-[var(--audit-ink-muted)]">{kb.documentCount.toLocaleString()}</td>
                  <td className="text-[var(--audit-ink-muted)]">{kb.characterCount.toLocaleString()}</td>
                  <td className="text-[var(--audit-ink-muted)]">{kb.linkedAppCount}</td>
                  <td className="text-[var(--audit-ink-muted)]">{kb.description}</td>
                </tr>
              ))}
            </tbody>
            </table>
          </div>
        </section>
      </section>

      <aside className="min-w-0 space-y-4">
        <section className="audit-panel-rail p-5">
          <h2 className="audit-section-title">知识资产概览</h2>
          <div className="mt-4 space-y-3">
            <SummaryMetric label="总文档数" value={totalDocumentCount.toLocaleString()} />
            <SummaryMetric label="总字符数" value={totalCharacterCount.toLocaleString()} />
            <SummaryMetric label="关联应用数" value={totalLinkedAppCount.toLocaleString()} />
          </div>
        </section>
        <a className="audit-focus-ring audit-action-card p-5" href="/documents">
          <p className="audit-kicker">文档检索</p>
          <h2 className="audit-section-title mt-2">进入统一检索首页</h2>
          <p className="audit-copy mt-2">按知识库分类、搜索历史和引用结果组织材料。</p>
        </a>
        <a className="audit-focus-ring audit-action-card p-5" href="/pages/index-admin">
          <p className="audit-kicker">索引管理</p>
          <h2 className="audit-section-title mt-2">进入运维控制台</h2>
          <p className="audit-copy mt-2">发布、回滚、重载和验收仍在受控后台执行。</p>
        </a>
      </aside>
    </main>
  );
}

function KnowledgeBaseDirectoryItem({ kb }: { readonly kb: KnowledgeBaseCard }) {
  return (
    <article className="rounded-[var(--audit-radius-md)] border border-[var(--audit-line)] bg-white p-3">
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <h3 className="truncate text-sm font-semibold text-[var(--audit-ink)]">{kb.name}</h3>
          <p className="audit-meta mt-1">{kb.scope}</p>
        </div>
        <StatusPill tone={kb.status === "可检索" ? "success" : "neutral"}>{kb.status}</StatusPill>
      </div>
      <div className="mt-3 flex items-center justify-between gap-3 text-sm">
        <span className="text-[var(--audit-ink-muted)]">文档数</span>
        <span className="font-semibold text-[var(--audit-ink)]">{kb.documentCount.toLocaleString()}</span>
      </div>
      <p className="audit-meta mt-2">负责人：{kb.owner}</p>
    </article>
  );
}

function Metric({ label, value }: { readonly label: string; readonly value: string }) {
  return (
    <div className="rounded-[var(--audit-radius-md)] border border-[var(--audit-line)] bg-white px-3 py-2">
      <p className="audit-meta font-semibold">{label}</p>
      <p className="audit-metric-value-sm mt-1">{value}</p>
    </div>
  );
}

function SummaryMetric({ label, value }: { readonly label: string; readonly value: string }) {
  return (
    <div className="flex items-center justify-between gap-4 rounded-[var(--audit-radius-md)] bg-[var(--audit-surface-muted)] px-3 py-2">
      <span className="text-sm text-[var(--audit-ink-muted)]">{label}</span>
      <span className="text-sm font-semibold text-[var(--audit-ink)]">{value}</span>
    </div>
  );
}

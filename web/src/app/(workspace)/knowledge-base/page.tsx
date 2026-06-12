import { StatusPill } from "@/components/ui/status-pill";
import { knowledgeBases } from "@/lib/portal-data";

const totalDocumentCount = knowledgeBases.reduce((sum, kb) => sum + kb.documentCount, 0);
const totalCharacterCount = knowledgeBases.reduce((sum, kb) => sum + kb.characterCount, 0);
const totalLinkedAppCount = knowledgeBases.reduce((sum, kb) => sum + kb.linkedAppCount, 0);

export default function KnowledgeBasePage() {
  return (
    <main className="grid min-w-0 gap-5 xl:grid-cols-[minmax(0,1fr)_22rem]">
      <section className="min-w-0 rounded-2xl border border-slate-200 bg-white p-6 shadow-[var(--audit-shadow-card)]">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div className="min-w-0">
            <p className="text-sm font-semibold text-blue-700">知识库</p>
            <h1 className="mt-2 text-3xl font-semibold text-slate-950">个人、系统、公开知识库</h1>
          </div>
          <StatusPill tone="info">首期只读</StatusPill>
        </div>

        <div className="mt-6 grid gap-4 lg:grid-cols-3">
          {knowledgeBases.map((kb) => (
            <article key={kb.id} className="min-w-0 rounded-2xl border border-slate-200 bg-slate-50 p-4">
              <div className="flex items-start justify-between gap-3">
                <div className="min-w-0">
                  <h2 className="text-base font-semibold text-slate-950">{kb.name}</h2>
                  <p className="mt-1 text-xs text-slate-500">{kb.scope}</p>
                </div>
                <StatusPill tone={kb.status === "可检索" ? "success" : "neutral"}>{kb.status}</StatusPill>
              </div>
              <p className="mt-4 text-sm leading-6 text-slate-600">{kb.description}</p>
              <div className="mt-5 grid grid-cols-3 gap-2">
                <Metric label="文档数" value={kb.documentCount.toLocaleString()} />
                <Metric label="字符数" value={`${Math.round(kb.characterCount / 10000).toLocaleString()}万`} />
                <Metric label="应用数" value={String(kb.linkedAppCount)} />
              </div>
              <p className="mt-4 text-xs text-slate-500">负责人：{kb.owner}</p>
            </article>
          ))}
        </div>

        <div className="mt-6 max-w-full overflow-x-auto rounded-2xl border border-slate-200">
          <table className="w-full min-w-[52rem] text-left text-sm">
            <thead className="bg-slate-50 text-slate-500">
              <tr>
                <th className="px-4 py-3 font-semibold">知识库</th>
                <th className="px-4 py-3 font-semibold">类型</th>
                <th className="px-4 py-3 font-semibold">文档数</th>
                <th className="px-4 py-3 font-semibold">字符数</th>
                <th className="px-4 py-3 font-semibold">关联应用数</th>
                <th className="px-4 py-3 font-semibold">描述</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-200">
              {knowledgeBases.map((kb) => (
                <tr key={kb.id}>
                  <td className="px-4 py-3 font-semibold text-slate-950">{kb.name}</td>
                  <td className="px-4 py-3 text-slate-700">{kb.scope}</td>
                  <td className="px-4 py-3 text-slate-700">{kb.documentCount.toLocaleString()}</td>
                  <td className="px-4 py-3 text-slate-700">{kb.characterCount.toLocaleString()}</td>
                  <td className="px-4 py-3 text-slate-700">{kb.linkedAppCount}</td>
                  <td className="px-4 py-3 text-slate-600">{kb.description}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>

      <aside className="min-w-0 space-y-4">
        <section className="rounded-2xl border border-slate-200 bg-white p-5 shadow-[var(--audit-shadow-card)]">
          <h2 className="text-lg font-semibold text-slate-950">知识资产概览</h2>
          <div className="mt-4 space-y-3">
            <SummaryMetric label="总文档数" value={totalDocumentCount.toLocaleString()} />
            <SummaryMetric label="总字符数" value={totalCharacterCount.toLocaleString()} />
            <SummaryMetric label="关联应用数" value={totalLinkedAppCount.toLocaleString()} />
          </div>
        </section>
        <a className="audit-focus-ring block rounded-2xl border border-slate-200 bg-white p-5 shadow-[var(--audit-shadow-card)]" href="/documents">
          <p className="text-sm font-semibold text-blue-700">文档检索</p>
          <h2 className="mt-2 text-lg font-semibold text-slate-950">进入统一检索首页</h2>
          <p className="mt-2 text-sm leading-6 text-slate-600">按知识库分类、搜索历史和引用结果组织材料。</p>
        </a>
        <a className="audit-focus-ring block rounded-2xl border border-slate-200 bg-white p-5 shadow-[var(--audit-shadow-card)]" href="/pages/index-admin">
          <p className="text-sm font-semibold text-blue-700">索引管理</p>
          <h2 className="mt-2 text-lg font-semibold text-slate-950">进入运维控制台</h2>
          <p className="mt-2 text-sm leading-6 text-slate-600">发布、回滚、重载和验收仍在受控后台执行。</p>
        </a>
      </aside>
    </main>
  );
}

function Metric({ label, value }: { readonly label: string; readonly value: string }) {
  return (
    <div className="rounded-xl border border-slate-200 bg-white px-3 py-2">
      <p className="text-xs font-semibold text-slate-500">{label}</p>
      <p className="mt-1 text-base font-semibold text-slate-950">{value}</p>
    </div>
  );
}

function SummaryMetric({ label, value }: { readonly label: string; readonly value: string }) {
  return (
    <div className="flex items-center justify-between gap-4 rounded-xl bg-slate-50 px-3 py-2">
      <span className="text-sm text-slate-600">{label}</span>
      <span className="text-sm font-semibold text-slate-950">{value}</span>
    </div>
  );
}

export default function DocumentsPage() {
  return <ModulePreview title="材料与文档检索" stage="源文档、上传材料、全文检索、向量检索和引用定位" />;
}

function ModulePreview({ title, stage }: { readonly title: string; readonly stage: string }) {
  return (
    <main className="rounded-[28px] border border-slate-200 bg-white p-7 shadow-[var(--audit-shadow-card)]">
      <p className="text-sm font-medium text-blue-700">Plan 05 接入真实功能</p>
      <h1 className="mt-2 text-3xl font-semibold tracking-tight text-slate-950">{title}</h1>
      <p className="mt-3 text-sm leading-6 text-slate-600">{stage}</p>
    </main>
  );
}

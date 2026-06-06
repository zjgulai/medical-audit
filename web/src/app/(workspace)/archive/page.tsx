export default function ArchivePage() {
  return <ModulePreview title="项目档案" stage="项目画像、会话、材料、疑点、任务、报告和操作日志" />;
}

function ModulePreview({ title, stage }: { readonly title: string; readonly stage: string }) {
  return (
    <main className="rounded-[28px] border border-slate-200 bg-white p-7 shadow-[var(--audit-shadow-card)]">
      <p className="text-sm font-medium text-blue-700">Plan 11 接入真实功能</p>
      <h1 className="mt-2 text-3xl font-semibold tracking-tight text-slate-950">{title}</h1>
      <p className="mt-3 text-sm leading-6 text-slate-600">{stage}</p>
    </main>
  );
}

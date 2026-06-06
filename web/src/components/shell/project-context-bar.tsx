import { StatusPill } from "@/components/ui/status-pill";

export function ProjectContextBar() {
  return (
    <header className="sticky top-0 z-20 border-b border-slate-200/80 bg-white/82 px-8 py-4 backdrop-blur-xl">
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div>
          <p className="text-xs font-medium uppercase tracking-[0.18em] text-slate-500">当前自查项目</p>
          <h1 className="mt-1 text-xl font-semibold tracking-tight text-slate-950">默认自查项目</h1>
        </div>
        <div className="flex items-center gap-2">
          <StatusPill tone="info">医保基金使用合规</StatusPill>
          <StatusPill tone="warning">证据待补充</StatusPill>
          <StatusPill tone="success">索引在线</StatusPill>
        </div>
      </div>
    </header>
  );
}

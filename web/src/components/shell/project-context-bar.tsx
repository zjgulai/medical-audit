import { StatusPill } from "@/components/ui/status-pill";
import { currentSelfCheckProject } from "@/lib/projects";

export function ProjectContextBar() {
  const project = currentSelfCheckProject;

  return (
    <header className="sticky top-0 z-20 border-b border-slate-200/80 bg-white/82 px-4 py-4 backdrop-blur-xl sm:px-6 md:px-8">
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div>
          <p className="text-xs font-medium uppercase tracking-[0.18em] text-slate-500">当前自查项目</p>
          <div className="mt-1 text-xl font-semibold tracking-tight text-slate-950">{project.name}</div>
          <p className="mt-1 text-xs text-slate-500">{project.organizationName}</p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <StatusPill tone="info">{project.auditTopic}</StatusPill>
          <StatusPill tone="success">项目进行中</StatusPill>
          <StatusPill tone="warning">AI 结论需人工确认</StatusPill>
        </div>
      </div>
    </header>
  );
}

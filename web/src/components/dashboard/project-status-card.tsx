import { StatusPill } from "@/components/ui/status-pill";
import type { SelfCheckProject } from "@/lib/projects";

type ProjectStatusCardProps = {
  readonly project: SelfCheckProject;
};

export function ProjectStatusCard({ project }: ProjectStatusCardProps) {
  return (
    <section className="rounded-[32px] border border-slate-200 bg-white p-7 shadow-[var(--audit-shadow-card)]">
      <div className="flex flex-wrap items-start justify-between gap-5">
        <div className="max-w-3xl">
          <p className="text-sm font-medium text-blue-700">今日工作台</p>
          <h1 className="mt-2 text-3xl font-semibold tracking-tight text-slate-950">{project.name}</h1>
          <div className="mt-3 flex flex-wrap gap-x-3 gap-y-1 text-sm leading-6 text-slate-600">
            <p>{project.organizationName}</p>
            <p>{project.dateRange}</p>
          </div>
          <p className="mt-3 max-w-2xl text-sm leading-6 text-slate-600">{project.evidencePolicy}</p>
        </div>
        <div className="flex flex-wrap gap-2">
          <StatusPill tone="info">{project.auditTopic}</StatusPill>
          <StatusPill tone="success">项目进行中</StatusPill>
          <StatusPill tone="warning">禁止无引用定论</StatusPill>
        </div>
      </div>
    </section>
  );
}

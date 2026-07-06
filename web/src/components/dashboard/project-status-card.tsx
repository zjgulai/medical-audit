import { StatusPill } from "@/components/ui/status-pill";
import type { SelfCheckProject } from "@/lib/projects";

type ProjectStatusCardProps = {
  readonly project: SelfCheckProject;
};

export function ProjectStatusCard({ project }: ProjectStatusCardProps) {
  return (
    <section className="audit-panel p-6">
      <div className="flex flex-wrap items-start justify-between gap-5">
        <div className="max-w-3xl">
          <p className="audit-kicker">今日工作台</p>
          <h1 className="audit-page-title">{project.name}</h1>
          <div className="mt-3 flex flex-wrap gap-x-3 gap-y-1 audit-copy">
            <p>{project.organizationName}</p>
            <p>{project.dateRange}</p>
          </div>
          <p className="mt-3 max-w-2xl audit-copy">{project.evidencePolicy}</p>
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

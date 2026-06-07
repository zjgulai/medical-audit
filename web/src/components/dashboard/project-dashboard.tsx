import { BackendStatusCard } from "./backend-status-card";
import { ProjectActivityList } from "./project-activity-list";
import { ProjectMetricCard } from "./project-metric-card";
import { ProjectQueueCard } from "./project-queue-card";
import { ProjectStatusCard } from "./project-status-card";
import { WorkflowProgressCard } from "./workflow-progress-card";
import type { SelfCheckProject } from "@/lib/projects";

type ProjectDashboardProps = {
  readonly project: SelfCheckProject;
};

export function ProjectDashboard({ project }: ProjectDashboardProps) {
  return (
    <main className="space-y-6">
      <ProjectStatusCard project={project} />
      <BackendStatusCard />
      <section className="grid gap-4 md:grid-cols-2 xl:grid-cols-4" aria-label="项目关键指标">
        {project.metrics.map((metric) => (
          <ProjectMetricCard key={metric.key} metric={metric} />
        ))}
      </section>
      <section className="grid gap-6 xl:grid-cols-[1.05fr_0.95fr]">
        <WorkflowProgressCard project={project} />
        <ProjectQueueCard project={project} />
      </section>
      <ProjectActivityList activities={project.activities} />
    </main>
  );
}

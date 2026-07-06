"use client";

import { useEffect, useMemo, useState } from "react";

import { BackendStatusCard } from "./backend-status-card";
import { ProjectActivityList } from "./project-activity-list";
import { ProjectMetricCard } from "./project-metric-card";
import { ProjectQueueCard } from "./project-queue-card";
import { ProjectStatusCard } from "./project-status-card";
import { WorkflowProgressCard } from "./workflow-progress-card";
import { fetchProjectDashboard } from "@/lib/api-client";
import type { SelfCheckProject } from "@/lib/projects";
import type { ProjectDashboardResponse, ProjectSummaryApiItem } from "@/lib/api-types";

type ProjectDashboardProps = {
  readonly project: SelfCheckProject;
};

export function ProjectDashboard({ project }: ProjectDashboardProps) {
  const [dashboard, setDashboard] = useState<ProjectDashboardResponse | null>(null);

  useEffect(() => {
    let mounted = true;

    fetchProjectDashboard(project.id)
      .then((response) => {
        if (mounted) {
          setDashboard(response);
        }
      })
      .catch(() => {
        if (mounted) {
          setDashboard(null);
        }
      });

    return () => {
      mounted = false;
    };
  }, [project.id]);

  const visibleProject = useMemo(
    () => (dashboard ? mergeDashboardProject(project, dashboard) : project),
    [dashboard, project]
  );

  return (
    <main className="space-y-6">
      <ProjectStatusCard project={visibleProject} />
      <BackendStatusCard />
      <section className="grid gap-4 md:grid-cols-2 xl:grid-cols-4" aria-label="项目关键指标">
        {visibleProject.metrics.map((metric) => (
          <ProjectMetricCard key={metric.key} metric={metric} />
        ))}
      </section>
      <section className="grid gap-6 xl:grid-cols-[1.05fr_0.95fr]">
        <WorkflowProgressCard project={visibleProject} />
        <ProjectQueueCard project={visibleProject} />
      </section>
      <ProjectActivityList activities={visibleProject.activities} />
    </main>
  );
}

function mergeDashboardProject(
  fallback: SelfCheckProject,
  dashboard: ProjectDashboardResponse
): SelfCheckProject {
  return {
    ...fallback,
    name: dashboard.project.name,
    organizationName: dashboard.project.organization_name,
    auditTopic: dashboard.project.audit_topic,
    status: apiProjectStatusToDashboardStatus(dashboard.project),
    metrics: dashboard.metrics,
    queue: dashboard.queue,
    activities: dashboard.activities
  };
}

function apiProjectStatusToDashboardStatus(project: ProjectSummaryApiItem): SelfCheckProject["status"] {
  if (project.status === "已归档") {
    return "closed";
  }
  if (project.status === "待启动") {
    return "paused";
  }
  return "active";
}

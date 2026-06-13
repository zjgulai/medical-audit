import { StatusPill } from "@/components/ui/status-pill";
import type { ProjectMetric } from "@/lib/projects";

type ProjectMetricCardProps = {
  readonly metric: ProjectMetric;
};

export function ProjectMetricCard({ metric }: ProjectMetricCardProps) {
  return (
    <article className="audit-panel p-5">
      <div className="flex items-start justify-between gap-3">
        <p className="audit-label">{metric.label}</p>
        <StatusPill tone={metric.tone}>{metric.tone === "danger" ? "高风险" : "状态"}</StatusPill>
      </div>
      <p className="mt-4 audit-metric-value">{metric.value}</p>
      <p className="mt-2 audit-meta">{metric.helper}</p>
    </article>
  );
}

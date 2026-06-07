import { StatusPill } from "@/components/ui/status-pill";
import type { ProjectMetric } from "@/lib/projects";

type ProjectMetricCardProps = {
  readonly metric: ProjectMetric;
};

export function ProjectMetricCard({ metric }: ProjectMetricCardProps) {
  return (
    <article className="rounded-[24px] border border-slate-200 bg-white p-5 shadow-[var(--audit-shadow-card)]">
      <div className="flex items-start justify-between gap-3">
        <p className="text-sm font-medium text-slate-600">{metric.label}</p>
        <StatusPill tone={metric.tone}>{metric.tone === "danger" ? "高风险" : "状态"}</StatusPill>
      </div>
      <p className="mt-4 text-3xl font-semibold tracking-tight text-slate-950">{metric.value}</p>
      <p className="mt-2 text-xs leading-5 text-slate-500">{metric.helper}</p>
    </article>
  );
}

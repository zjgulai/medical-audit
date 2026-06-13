import { getProjectStageProgress, projectStageLabels, type SelfCheckProject } from "@/lib/projects";

type WorkflowProgressCardProps = {
  readonly project: SelfCheckProject;
};

export function WorkflowProgressCard({ project }: WorkflowProgressCardProps) {
  const progress = getProjectStageProgress(project);

  return (
    <section className="audit-panel p-5">
      <p className="audit-kicker">AI 自查状态机</p>
      <h2 className="mt-2 audit-section-title">当前阶段：{projectStageLabels[project.stage]}</h2>
      <div className="mt-5">
        <div className="h-2 rounded-full bg-[var(--audit-surface-subtle)]">
          <div className="h-2 rounded-full bg-[var(--audit-primary)]" style={{ width: `${progress.percent}%` }} />
        </div>
        <p className="mt-3 audit-copy">
          {projectStageLabels[project.stage]} · {progress.currentIndex}/{progress.total} · {progress.percent}%
        </p>
      </div>
      <div className="mt-5 grid gap-2 sm:grid-cols-2">
        {Object.entries(projectStageLabels).map(([stage, label]) => (
          <div
            key={stage}
            className={`rounded-[var(--audit-radius-md)] border px-3 py-2 text-sm ${
              stage === project.stage
                ? "border-[var(--audit-primary-line)] bg-[var(--audit-primary-soft)] font-semibold text-[var(--audit-primary)]"
                : "border-[var(--audit-line-soft)] bg-[var(--audit-surface-muted)] text-[var(--audit-ink-muted)]"
            }`}
          >
            {label}
          </div>
        ))}
      </div>
    </section>
  );
}

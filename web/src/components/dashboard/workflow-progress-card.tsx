import { getProjectStageProgress, projectStageLabels, type SelfCheckProject } from "@/lib/projects";

type WorkflowProgressCardProps = {
  readonly project: SelfCheckProject;
};

export function WorkflowProgressCard({ project }: WorkflowProgressCardProps) {
  const progress = getProjectStageProgress(project);

  return (
    <section className="rounded-[28px] border border-slate-200 bg-white p-6 shadow-[var(--audit-shadow-card)]">
      <p className="text-sm font-medium text-blue-700">AI 自查状态机</p>
      <h2 className="mt-2 text-xl font-semibold tracking-tight text-slate-950">当前阶段：{projectStageLabels[project.stage]}</h2>
      <div className="mt-5">
        <div className="h-2 rounded-full bg-slate-100">
          <div className="h-2 rounded-full bg-blue-600" style={{ width: `${progress.percent}%` }} />
        </div>
        <p className="mt-3 text-sm text-slate-600">
          {projectStageLabels[project.stage]} · {progress.currentIndex}/{progress.total} · {progress.percent}%
        </p>
      </div>
      <div className="mt-5 grid gap-2 sm:grid-cols-2">
        {Object.entries(projectStageLabels).map(([stage, label]) => (
          <div
            key={stage}
            className={`rounded-2xl border px-3 py-2 text-sm ${
              stage === project.stage ? "border-blue-200 bg-blue-50 text-blue-700" : "border-slate-200 bg-slate-50 text-slate-600"
            }`}
          >
            {label}
          </div>
        ))}
      </div>
    </section>
  );
}

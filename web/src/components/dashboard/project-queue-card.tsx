import { StatusPill } from "@/components/ui/status-pill";
import { getOpenProjectQueueItems, type ProjectQueueItem, type SelfCheckProject } from "@/lib/projects";

type ProjectQueueCardProps = {
  readonly project: SelfCheckProject;
};

const riskTone: Record<ProjectQueueItem["risk"], "danger" | "warning" | "neutral"> = {
  high: "danger",
  medium: "warning",
  low: "neutral"
};

export function ProjectQueueCard({ project }: ProjectQueueCardProps) {
  const items = getOpenProjectQueueItems(project);

  return (
    <section className="rounded-[28px] border border-slate-200 bg-white p-6 shadow-[var(--audit-shadow-card)]">
      <div className="flex items-start justify-between gap-4">
        <div>
          <p className="text-sm font-medium text-blue-700">待办队列</p>
          <h2 className="mt-2 text-xl font-semibold tracking-tight text-slate-950">需要人工处理</h2>
        </div>
        <StatusPill tone="warning">{items.length} 项打开</StatusPill>
      </div>
      <div className="mt-5 space-y-3">
        {items.map((item) => (
          <article key={item.id} className="rounded-2xl border border-slate-200 bg-slate-50 p-4">
            <div className="flex flex-wrap items-start justify-between gap-3">
              <div>
                <p className="text-sm font-semibold text-slate-950">{item.title}</p>
                <p className="mt-1 text-xs text-slate-500">
                  {item.owner} · {item.dueLabel}
                </p>
              </div>
              <StatusPill tone={riskTone[item.risk]}>{item.status === "blocked" ? "待外部资料" : "待处理"}</StatusPill>
            </div>
          </article>
        ))}
      </div>
    </section>
  );
}

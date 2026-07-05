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
    <section className="audit-panel p-5">
      <div className="flex items-start justify-between gap-4">
        <div>
          <p className="audit-kicker">待办队列</p>
          <h2 className="mt-2 audit-section-title">需要人工处理</h2>
        </div>
        <StatusPill tone="warning">{items.length} 项打开</StatusPill>
      </div>
      <div className="mt-5 space-y-3">
        {items.map((item) => (
          <article key={item.id} className="audit-panel-muted p-4">
            <div className="flex flex-wrap items-start justify-between gap-3">
              <div>
                <p className="audit-compact-title">{item.title}</p>
                <p className="mt-1 audit-meta">
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

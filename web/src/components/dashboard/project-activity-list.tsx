import type { ProjectActivity } from "@/lib/projects";

type ProjectActivityListProps = {
  readonly activities: readonly ProjectActivity[];
};

export function ProjectActivityList({ activities }: ProjectActivityListProps) {
  return (
    <section className="audit-panel p-5">
      <p className="audit-kicker">最近进展</p>
      <h2 className="mt-2 audit-section-title">项目审计链动态</h2>
      <div className="mt-5 divide-y divide-[var(--audit-line-soft)]">
        {activities.map((activity) => (
          <article key={activity.id} className="py-4 first:pt-0 last:pb-0">
            <div className="flex flex-wrap items-start justify-between gap-3">
              <div>
                <p className="audit-compact-title">{activity.title}</p>
                <p className="mt-1 audit-copy">{activity.description}</p>
              </div>
              <p className="audit-meta">{activity.timeLabel}</p>
            </div>
          </article>
        ))}
      </div>
    </section>
  );
}

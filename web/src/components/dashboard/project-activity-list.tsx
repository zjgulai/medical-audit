import type { ProjectActivity } from "@/lib/projects";

type ProjectActivityListProps = {
  readonly activities: readonly ProjectActivity[];
};

export function ProjectActivityList({ activities }: ProjectActivityListProps) {
  return (
    <section className="rounded-[28px] border border-slate-200 bg-white p-6 shadow-[var(--audit-shadow-card)]">
      <p className="text-sm font-medium text-blue-700">最近进展</p>
      <h2 className="mt-2 text-xl font-semibold tracking-tight text-slate-950">项目审计链动态</h2>
      <div className="mt-5 divide-y divide-slate-200">
        {activities.map((activity) => (
          <article key={activity.id} className="py-4 first:pt-0 last:pb-0">
            <div className="flex flex-wrap items-start justify-between gap-3">
              <div>
                <p className="text-sm font-semibold text-slate-950">{activity.title}</p>
                <p className="mt-1 text-sm leading-6 text-slate-600">{activity.description}</p>
              </div>
              <p className="text-xs text-slate-500">{activity.timeLabel}</p>
            </div>
          </article>
        ))}
      </div>
    </section>
  );
}

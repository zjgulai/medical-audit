import Link from "next/link";

type ModuleCardProps = {
  readonly title: string;
  readonly description: string;
  readonly href: string;
  readonly badge: string;
};

export function ModuleCard({ title, description, href, badge }: ModuleCardProps) {
  return (
    <Link
      href={href}
      className="audit-focus-ring block rounded-[var(--audit-radius-lg)] border border-slate-200 bg-white p-5 shadow-[var(--audit-shadow-card)] transition hover:-translate-y-0.5 hover:border-blue-200"
    >
      <span className="inline-flex rounded-full border border-blue-100 bg-blue-50 px-2.5 py-1 text-xs font-medium text-blue-700">
        {badge}
      </span>
      <h2 className="mt-4 text-lg font-semibold tracking-tight text-slate-950">{title}</h2>
      <p className="mt-2 text-sm leading-6 text-slate-600">{description}</p>
    </Link>
  );
}

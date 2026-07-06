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
      className="audit-focus-ring audit-action-card p-5"
    >
      <span className="audit-chip audit-chip-info">
        {badge}
      </span>
      <h2 className="audit-card-title mt-4">{title}</h2>
      <p className="audit-copy mt-2">{description}</p>
    </Link>
  );
}

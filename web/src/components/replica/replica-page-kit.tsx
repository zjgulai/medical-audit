import type { ReactNode } from "react";

type ReplicaPageHeaderProps = {
  readonly kicker: string;
  readonly title: string;
  readonly description: string;
  readonly actions?: ReactNode;
};

type ReplicaMetricProps = {
  readonly label: string;
  readonly value: string;
  readonly tone?: "blue" | "green" | "amber" | "rose" | "slate";
};

type ReplicaFilterButtonProps<T extends string> = {
  readonly value: T;
  readonly activeValue: T;
  readonly onSelect: (value: T) => void;
  readonly children: ReactNode;
};

type ReplicaLocalGateNoticeOptions = {
  readonly action: string;
  readonly nextStep: string;
};

export function buildReplicaLocalGateNotice({ action }: ReplicaLocalGateNoticeOptions) {
  return `${action}已生成预览。请复核内容后再进入正式处理。`;
}

export function ReplicaPageHeader({ kicker, title, description, actions }: ReplicaPageHeaderProps) {
  return (
    <section className="replica-page-header">
      <div>
        <p className="replica-kicker">{kicker}</p>
        <h1>{title}</h1>
        <p>{description}</p>
      </div>
      {actions && <div className="replica-header-actions">{actions}</div>}
    </section>
  );
}

export function ReplicaMetric({ label, value, tone = "blue" }: ReplicaMetricProps) {
  return (
    <article className={`replica-metric tone-${tone}`}>
      <span>{label}</span>
      <strong>{value}</strong>
    </article>
  );
}

export function ReplicaFilterButton<T extends string>({
  value,
  activeValue,
  onSelect,
  children
}: ReplicaFilterButtonProps<T>) {
  return (
    <button
      type="button"
      className={`replica-filter-button ${activeValue === value ? "is-active" : ""}`}
      onClick={() => onSelect(value)}
    >
      {children}
    </button>
  );
}

export function ReplicaNotice({ children }: { readonly children: ReactNode }) {
  return <div className="replica-notice">{children}</div>;
}

export function ReplicaEmptyState({ title, description }: { readonly title: string; readonly description: string }) {
  return (
    <div className="replica-empty">
      <span aria-hidden="true">∅</span>
      <strong>{title}</strong>
      <p>{description}</p>
    </div>
  );
}

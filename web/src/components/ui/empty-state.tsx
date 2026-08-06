import type { ReactNode } from "react";

type EmptyStateTone = "neutral" | "info" | "warning";

type EmptyStateProps = {
  readonly title: string;
  readonly description?: string;
  readonly tone?: EmptyStateTone;
  readonly action?: ReactNode;
  readonly compact?: boolean;
};

const TONE_ICON: Record<EmptyStateTone, string> = {
  neutral: "○",
  info: "ⓘ",
  warning: "⚠"
};

export function EmptyState({
  title,
  description,
  tone = "neutral",
  action,
  compact = false
}: EmptyStateProps) {
  return (
    <div
      className={`audit-empty-state ${compact ? "audit-empty-state--compact" : ""} audit-empty-state--${tone}`}
      role="status"
      aria-live="polite"
    >
      <span className="audit-empty-state-icon" aria-hidden="true">
        {TONE_ICON[tone]}
      </span>
      <p className="audit-empty-state-title">{title}</p>
      {description && <p className="audit-empty-state-desc">{description}</p>}
      {action && <div className="audit-empty-state-action">{action}</div>}
    </div>
  );
}

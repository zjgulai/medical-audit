type StatusTone = "neutral" | "info" | "warning" | "danger" | "success";

type StatusPillProps = {
  readonly children: React.ReactNode;
  readonly tone?: StatusTone;
};

const toneClassName: Record<StatusTone, string> = {
  neutral: "border-[var(--audit-line)] bg-[var(--audit-surface-muted)] text-[var(--audit-ink-muted)]",
  info: "border-[var(--audit-primary-line)] bg-[var(--audit-primary-soft)] text-[var(--audit-primary)]",
  warning: "border-amber-200 bg-amber-50 text-amber-800",
  danger: "border-red-200 bg-red-50 text-red-700",
  success: "border-emerald-200 bg-emerald-50 text-emerald-700"
};

export function StatusPill({ children, tone = "neutral" }: StatusPillProps) {
  return (
    <span className={`inline-flex items-center rounded-full border px-2.5 py-1 text-xs font-semibold leading-4 ${toneClassName[tone]}`}>
      {children}
    </span>
  );
}

type StatusTone = "neutral" | "info" | "warning" | "danger" | "success";

type StatusPillProps = {
  readonly children: React.ReactNode;
  readonly tone?: StatusTone;
};

const toneClassName: Record<StatusTone, string> = {
  neutral: "border-slate-200 bg-slate-50 text-slate-700",
  info: "border-blue-200 bg-blue-50 text-blue-700",
  warning: "border-amber-200 bg-amber-50 text-amber-800",
  danger: "border-red-200 bg-red-50 text-red-700",
  success: "border-emerald-200 bg-emerald-50 text-emerald-700"
};

export function StatusPill({ children, tone = "neutral" }: StatusPillProps) {
  return (
    <span className={`inline-flex items-center rounded-full border px-2.5 py-1 text-xs font-medium ${toneClassName[tone]}`}>
      {children}
    </span>
  );
}

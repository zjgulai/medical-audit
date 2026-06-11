type BackendFeatureBridgeProps = {
  readonly title: string;
  readonly targetHref: string;
  readonly targetLabel: string;
  readonly reason: string;
};

export function BackendFeatureBridge({
  title,
  targetHref,
  targetLabel,
  reason
}: BackendFeatureBridgeProps) {
  return (
    <main className="rounded-[28px] border border-slate-200 bg-white p-7 shadow-[var(--audit-shadow-card)]">
      <p className="text-sm font-medium text-blue-700">已接入真实功能入口</p>
      <h1 className="mt-2 text-3xl font-semibold tracking-tight text-slate-950">{title}</h1>
      <p className="mt-3 max-w-3xl text-sm leading-6 text-slate-600">{reason}</p>
      <a
        className="audit-focus-ring mt-6 inline-flex rounded-2xl bg-blue-600 px-4 py-2.5 text-sm font-semibold text-white shadow-lg shadow-blue-600/20 transition hover:bg-blue-700"
        href={targetHref}
      >
        打开{targetLabel}
      </a>
    </main>
  );
}

import Link from "next/link";

import { primaryNavigation } from "@/lib/navigation";

export function AppSidebar() {
  return (
    <aside className="flex min-h-screen w-72 flex-col border-r border-slate-200/80 bg-white/92 px-5 py-6 shadow-[12px_0_40px_rgb(16_24_40/0.04)]">
      <Link href="/workspace" className="audit-focus-ring rounded-2xl">
        <div className="flex items-center gap-3">
          <div className="grid size-10 place-items-center rounded-2xl bg-blue-600 text-sm font-semibold text-white shadow-lg shadow-blue-600/20">
            AI
          </div>
          <div>
            <p className="text-base font-semibold tracking-tight text-slate-950">医保自查 OS</p>
            <p className="text-xs text-slate-500">Medical Audit Self-Check</p>
          </div>
        </div>
      </Link>

      <nav className="mt-8 flex flex-1 flex-col gap-1.5" aria-label="主导航">
        {primaryNavigation.map((item) => (
          <Link
            key={item.href}
            href={item.href}
            className={`audit-focus-ring rounded-2xl px-3 py-3 text-sm transition ${
              item.emphasis === "primary"
                ? "bg-blue-50 text-blue-700 shadow-sm ring-1 ring-blue-100"
                : "text-slate-700 hover:bg-slate-50 hover:text-slate-950"
            }`}
          >
            <span className="block font-medium">{item.label}</span>
            <span className="mt-0.5 block truncate text-xs text-slate-500">{item.description}</span>
          </Link>
        ))}
      </nav>
    </aside>
  );
}

"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

import { primaryNavigation } from "@/lib/navigation";

function isActivePath(pathname: string, href: string) {
  return pathname === href || pathname.startsWith(`${href}/`);
}

export function AppSidebar() {
  const pathname = usePathname();

  return (
    <aside className="flex w-full flex-col border-b border-slate-200/80 bg-white/92 px-4 py-4 shadow-[0_12px_40px_rgb(16_24_40/0.04)] sm:px-5 md:min-h-screen md:w-72 md:border-r md:border-b-0 md:py-6 md:shadow-[12px_0_40px_rgb(16_24_40/0.04)]">
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

      <nav
        className="mt-5 flex gap-2 overflow-x-auto pb-1 md:mt-8 md:flex-1 md:flex-col md:gap-1.5 md:overflow-x-visible md:pb-0"
        aria-label="主导航"
      >
        {primaryNavigation.map((item) => {
          const isActive = isActivePath(pathname, item.href);

          return (
            <Link
              key={item.href}
              href={item.href}
              aria-current={isActive ? "page" : undefined}
              className={`audit-focus-ring min-w-40 rounded-2xl px-3 py-3 text-sm transition md:min-w-0 ${
                isActive
                  ? "bg-blue-50 text-blue-700 shadow-sm ring-1 ring-blue-100"
                  : "text-slate-700 hover:bg-slate-50 hover:text-slate-950"
              }`}
            >
              <span className="block font-medium">{item.label}</span>
              <span className="mt-0.5 hidden truncate text-xs text-slate-500 md:block">{item.description}</span>
            </Link>
          );
        })}
      </nav>
    </aside>
  );
}

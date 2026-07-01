"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

import {
  fundComplianceNavigation,
  primaryNavigation,
  secondaryNavigation,
  systemNavigation,
  type NavigationItem
} from "@/lib/navigation";
import { currentSelfCheckProject } from "@/lib/projects";

import { BrandLogo } from "./brand-logo";

function isActivePath(pathname: string, href: string) {
  return pathname === href || pathname.startsWith(`${href}/`);
}

function NavigationLink({
  item,
  pathname,
  collapsed
}: {
  readonly item: NavigationItem;
  readonly pathname: string;
  readonly collapsed: boolean;
}) {
  const isActive = isActivePath(pathname, item.href);
  const className = `audit-focus-ring audit-sidebar-link flex min-w-11 items-center justify-center gap-0 rounded-[var(--audit-radius-md)] px-1.5 py-1.5 text-sm transition sm:min-w-28 sm:justify-start sm:gap-2 sm:px-2 md:min-w-0 md:gap-2.5 md:px-2.5 md:py-2 ${
    collapsed ? "md:justify-center md:px-0" : ""
  } ${
    isActive
      ? "bg-[var(--audit-primary)] text-white shadow-[0_8px_18px_rgb(29_117_201/0.18)]"
      : "text-[var(--audit-ink-muted)] hover:bg-white hover:text-[var(--audit-ink)]"
  }`;
  const content = (
    <>
      <span
        aria-hidden="true"
        className={`grid size-7 shrink-0 place-items-center rounded-[var(--audit-radius-sm)] text-[11px] font-semibold ${
          isActive ? "bg-white/18 text-white" : "bg-[var(--audit-surface-subtle)] text-[var(--audit-primary)]"
        }`}
      >
        {item.symbol}
      </span>
      <span className={`hidden min-w-0 flex-1 truncate text-xs font-medium sm:inline sm:text-sm ${collapsed ? "md:hidden" : ""}`}>{item.label}</span>
      {item.target === "backend" && (
        <span
          className={`hidden rounded-full px-1.5 py-0.5 text-[10px] font-semibold sm:inline ${collapsed ? "md:hidden" : ""} ${
            isActive ? "bg-white/20 text-white" : "bg-white text-[var(--audit-ink-subtle)]"
          }`}
        >
          管理页
        </span>
      )}
    </>
  );

  if (item.target === "backend") {
    return (
      <a
        href={item.href}
        title={item.description}
        aria-label={item.label}
        aria-current={isActive ? "page" : undefined}
        className={className}
      >
        {content}
      </a>
    );
  }

  return (
    <Link
      href={item.href}
      title={item.description}
      aria-label={item.label}
      aria-current={isActive ? "page" : undefined}
      className={className}
    >
      {content}
    </Link>
  );
}

export function AppSidebar({ collapsed = false }: { readonly collapsed?: boolean }) {
  const pathname = usePathname();
  const currentTopic = currentSelfCheckProject.auditTopic;

  return (
    <aside
      className={`audit-sidebar-shell flex w-full flex-col border-b border-[var(--audit-line)] px-3 py-2 shadow-[0_10px_24px_rgb(23_62_105/0.05)] transition-[width] sm:px-4 md:min-h-screen md:border-r md:border-b-0 md:py-5 md:shadow-[8px_0_24px_rgb(23_62_105/0.05)] ${
        collapsed ? "md:w-[4.75rem] md:px-2" : "md:w-[16rem] xl:w-[17rem]"
      }`}
    >
      <Link href="/workspace" className="audit-focus-ring rounded-[var(--audit-radius-lg)]" aria-label="打开门户首页">
        <div className={`flex items-center gap-3 ${collapsed ? "md:justify-center md:gap-0" : ""}`}>
          <div className="grid size-10 shrink-0 place-items-center rounded-[var(--audit-radius-md)] border border-[var(--audit-line)] bg-white shadow-[0_8px_18px_rgb(35_45_84/0.08)]">
            <BrandLogo priority />
          </div>
          <div className={`min-w-0 ${collapsed ? "md:hidden" : ""}`}>
            <p className="truncate text-sm font-semibold text-[var(--audit-ink)]">AI智能审计管理系统</p>
            <p className="audit-meta">医保基金审计专题</p>
          </div>
        </div>
      </Link>

      <Link
        href={fundComplianceNavigation.href}
        aria-label={`打开当前审计专题：${currentTopic}`}
        className={`audit-focus-ring mt-3 items-center gap-2.5 rounded-[var(--audit-radius-md)] border border-[var(--audit-primary-line)] bg-[var(--audit-primary-soft)] px-3 py-2.5 text-left transition hover:border-[var(--audit-primary)] hover:bg-white ${
          collapsed ? "hidden" : "hidden md:flex"
        }`}
      >
        <span
          aria-hidden="true"
          className="grid size-7 shrink-0 place-items-center rounded-[var(--audit-radius-sm)] bg-white text-[11px] font-semibold text-[var(--audit-primary)]"
        >
          专
        </span>
        <span className="min-w-0">
          <span className="block truncate text-xs font-semibold text-[var(--audit-ink)]">{currentTopic}</span>
          <span className="audit-meta block">打开当前专题</span>
        </span>
      </Link>

      <nav
        className="mt-2 flex gap-1.5 overflow-x-auto pb-1 md:mt-5 md:flex-col md:gap-1 md:overflow-x-visible md:pb-0"
        aria-label="主导航"
      >
        {primaryNavigation.map((item) => (
          <NavigationLink key={item.id} item={item} pathname={pathname} collapsed={collapsed} />
        ))}
      </nav>

      <div className={`mt-4 border-t border-[var(--audit-line)] pt-3 ${collapsed ? "hidden" : "hidden md:block"}`}>
        <nav className="flex flex-col gap-1" aria-label="更多功能">
          {[...secondaryNavigation, ...systemNavigation].map((item) => (
            <NavigationLink key={item.id} item={item} pathname={pathname} collapsed={false} />
          ))}
        </nav>
      </div>
    </aside>
  );
}

"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

import {
  sidebarUtilityNavigation,
  visiblePrimaryNavigation,
  type NavigationItem
} from "@/lib/navigation";
import { AUDIT_PLATFORM_NAME, AUDIT_PLATFORM_SUBTITLE } from "@/lib/brand";

import { BrandLogo } from "./brand-logo";

function isActivePath(pathname: string, href: string) {
  return pathname === href || pathname.startsWith(`${href}/`);
}

const SIDEBAR_PINNED_UTILITY_IDS = new Set(["agent-market", "knowledge-base", "analytics"]);

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
  const utilityHasActiveItem = sidebarUtilityNavigation.some((item) => isActivePath(pathname, item.href));
  const pinnedUtilityItems = sidebarUtilityNavigation.filter(
    (item) => SIDEBAR_PINNED_UTILITY_IDS.has(item.id) || isActivePath(pathname, item.href)
  );
  const remainingUtilityItems = sidebarUtilityNavigation.filter(
    (item) => !pinnedUtilityItems.some((visibleItem) => visibleItem.id === item.id)
  );

  return (
    <aside
      className={`audit-sidebar-shell flex w-full flex-col border-b border-[var(--audit-line)] px-3 py-2 shadow-[0_8px_18px_rgb(23_62_105/0.04)] transition-[width] sm:px-4 md:min-h-screen md:border-r md:border-b-0 md:py-5 md:shadow-[6px_0_18px_rgb(23_62_105/0.04)] ${
        collapsed ? "md:w-[4.75rem] md:px-2" : "md:w-[14.5rem] xl:w-[15rem]"
      }`}
    >
      <Link href="/workspace" className="audit-focus-ring rounded-[var(--audit-radius-lg)]" aria-label="打开门户首页">
        <div className={`flex items-center gap-3 ${collapsed ? "md:justify-center md:gap-0" : ""}`}>
          <div className="grid size-10 shrink-0 place-items-center rounded-[var(--audit-radius-md)] border border-[var(--audit-line)] bg-white shadow-[0_8px_18px_rgb(35_45_84/0.08)]">
            <BrandLogo priority />
          </div>
          <div className={`min-w-0 ${collapsed ? "md:hidden" : ""}`}>
            <p className="truncate text-sm font-semibold text-[var(--audit-ink)]">{AUDIT_PLATFORM_NAME}</p>
            <p className="audit-meta">{AUDIT_PLATFORM_SUBTITLE}</p>
          </div>
        </div>
      </Link>

      <nav
        className="mt-2 grid grid-cols-5 gap-1.5 md:mt-5 md:flex md:flex-col md:gap-1 md:overflow-x-visible md:pb-0"
        aria-label="主导航"
      >
        {visiblePrimaryNavigation.map((item) => (
          <NavigationLink key={item.id} item={item} pathname={pathname} collapsed={collapsed} />
        ))}
      </nav>

      <div className={`mt-4 border-t border-[var(--audit-line)] pt-3 ${collapsed ? "hidden" : "hidden md:block"}`}>
        <details className="group" open={utilityHasActiveItem}>
          <summary className="audit-focus-ring flex cursor-pointer list-none items-center gap-2 rounded-[var(--audit-radius-md)] px-2.5 py-2 text-xs font-semibold text-[var(--audit-ink-muted)] hover:bg-[var(--audit-surface-muted)] [&::-webkit-details-marker]:hidden">
            <span aria-hidden="true" className="grid size-7 place-items-center rounded-[var(--audit-radius-sm)] bg-[var(--audit-surface-subtle)] text-[var(--audit-primary)]">
              ...
            </span>
            <span className="flex-1">更多</span>
            <span aria-hidden="true" className="text-[var(--audit-ink-subtle)] group-open:rotate-90">&gt;</span>
          </summary>
          <nav className="mt-2 flex flex-col gap-1" aria-label="更多功能">
            {pinnedUtilityItems.map((item) => (
              <NavigationLink key={item.id} item={item} pathname={pathname} collapsed={false} />
            ))}
            {remainingUtilityItems.length > 0 ? (
              <details className="group/utility mt-1">
                <summary className="audit-focus-ring flex cursor-pointer list-none items-center gap-2 rounded-[var(--audit-radius-md)] px-2.5 py-1.5 text-xs font-semibold text-[var(--audit-ink-subtle)] hover:bg-[var(--audit-surface-muted)] [&::-webkit-details-marker]:hidden">
                  <span className="flex-1">全部</span>
                  <span aria-hidden="true" className="group-open/utility:rotate-90">&gt;</span>
                </summary>
                <div className="mt-1 flex flex-col gap-1">
                  {remainingUtilityItems.map((item) => (
                    <NavigationLink key={item.id} item={item} pathname={pathname} collapsed={false} />
                  ))}
                </div>
              </details>
            ) : null}
          </nav>
        </details>
      </div>
    </aside>
  );
}

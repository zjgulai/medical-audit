"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { MouseEvent, useEffect, useMemo, useState } from "react";

import { StatusPill } from "@/components/ui/status-pill";
import { findNavigationItemById, findNavigationItemForPath } from "@/lib/navigation";
import { currentSelfCheckProject } from "@/lib/projects";

const defaultTabIds = ["ai-chat", "documents", "analytics"] as const;

export function ProjectContextBar() {
  const project = currentSelfCheckProject;
  const pathname = usePathname();
  const router = useRouter();
  const activeItem = useMemo(() => findNavigationItemForPath(pathname), [pathname]);
  const [openTabIds, setOpenTabIds] = useState<readonly string[]>(() => {
    if (activeItem) {
      return [activeItem.id];
    }
    return defaultTabIds;
  });

  useEffect(() => {
    if (!activeItem) {
      return;
    }

    setOpenTabIds((current) => (current.includes(activeItem.id) ? current : [...current, activeItem.id]));
  }, [activeItem]);

  const openTabs = openTabIds
    .map((id) => findNavigationItemById(id))
    .filter((item): item is NonNullable<typeof item> => item !== undefined);

  const pageTitle = activeItem?.label ?? "今日工作台";

  function navigateToTab(tabId: string) {
    const target = findNavigationItemById(tabId);
    if (!target) {
      router.push("/workspace");
      return;
    }

    if (target.target === "backend") {
      window.location.href = target.href;
      return;
    }

    router.push(target.href);
  }

  function closeTab(event: MouseEvent<HTMLButtonElement>, tabId: string) {
    event.preventDefault();
    event.stopPropagation();

    setOpenTabIds((current) => {
      const next = current.filter((id) => id !== tabId);
      if (activeItem?.id === tabId) {
        navigateToTab(next[0] ?? "documents");
      }
      return next.length > 0 ? next : ["documents"];
    });
  }

  return (
    <header className="sticky top-0 z-20 border-b border-[var(--audit-line)] bg-white/90 px-4 py-3 backdrop-blur-xl sm:px-6 md:px-8">
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div className="min-w-0">
          <p className="audit-meta font-semibold">当前模块</p>
          <div className="audit-section-title mt-1">{pageTitle}</div>
          <p className="audit-meta mt-1 truncate">
            {project.name} · {project.organizationName}
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <StatusPill tone="info">{project.auditTopic}</StatusPill>
          <StatusPill tone="success">项目进行中</StatusPill>
          <StatusPill tone="warning">AI 结论需人工确认</StatusPill>
          <div className="ml-1 flex items-center gap-2 rounded-full border border-[var(--audit-line)] bg-[var(--audit-surface-muted)] px-2 py-1">
            <span className="grid size-6 place-items-center rounded-full bg-[var(--audit-ink)] text-xs font-semibold text-white">
              审
            </span>
            <span className="text-xs font-semibold text-[var(--audit-ink-muted)]">审计员</span>
          </div>
        </div>
      </div>

      <div className="mt-3 flex gap-2 overflow-x-auto pb-1" role="tablist" aria-label="已打开模块">
        {openTabs.map((tab) => {
          const isActive = activeItem?.id === tab.id;
          const tabClassName = `audit-focus-ring inline-flex h-9 shrink-0 items-center gap-2 rounded-lg border px-3 text-sm ${
            isActive
              ? "border-[var(--audit-primary-line)] bg-[var(--audit-primary-soft)] text-[var(--audit-primary)]"
              : "border-[var(--audit-line)] bg-white text-[var(--audit-ink-muted)] hover:bg-[var(--audit-surface-muted)] hover:text-[var(--audit-ink)]"
          }`;
          const label = (
            <>
              <span className="font-medium">{tab.label}</span>
              <button
                className="audit-focus-ring -mr-1 grid size-5 place-items-center rounded-md text-xs hover:bg-white"
                type="button"
                aria-label={`关闭${tab.label}`}
                onClick={(event) => closeTab(event, tab.id)}
              >
                ×
              </button>
            </>
          );

          if (tab.target === "backend") {
            return (
              <a
                key={tab.id}
                href={tab.href}
                role="tab"
                aria-selected={isActive}
                className={tabClassName}
              >
                {label}
              </a>
            );
          }

          return (
            <Link
              key={tab.id}
              href={tab.href}
              role="tab"
              aria-selected={isActive}
              className={tabClassName}
            >
              {label}
            </Link>
          );
        })}
      </div>
    </header>
  );
}

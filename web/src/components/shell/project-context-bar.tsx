"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { MouseEvent, useEffect, useMemo, useState } from "react";

import { StatusPill } from "@/components/ui/status-pill";
import { fetchAuthSession } from "@/lib/api-client";
import type { AuthSessionResponse } from "@/lib/api-types";
import { auditClientRoleDetail, auditClientRoleLabel, auditRoleOptions } from "@/lib/audit-user";
import { findNavigationItemById, findNavigationItemForPath } from "@/lib/navigation";
import { currentSelfCheckProject } from "@/lib/projects";

import { useAuditUser } from "./audit-user-context";

const defaultTabIds = ["workspace", "ai-chat", "analytics"] as const;

type ProjectContextBarProps = {
  readonly sidebarCollapsed?: boolean;
  readonly onToggleSidebar?: () => void;
};

export function ProjectContextBar({ sidebarCollapsed = false, onToggleSidebar }: ProjectContextBarProps = {}) {
  const project = currentSelfCheckProject;
  const pathname = usePathname();
  const router = useRouter();
  const auditUser = useAuditUser();
  const [authSession, setAuthSession] = useState<AuthSessionResponse | null>(null);
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

  useEffect(() => {
    let isMounted = true;

    fetchAuthSession()
      .then((session) => {
        if (isMounted) {
          setAuthSession(session);
        }
      })
      .catch(() => {
        if (isMounted) {
          setAuthSession(null);
        }
      });

    return () => {
      isMounted = false;
    };
  }, [auditUser.role]);

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
        navigateToTab(next[0] ?? "workspace");
      }
      return next.length > 0 ? next : ["workspace"];
    });
  }

  return (
    <header className="sticky top-0 z-20 border-b border-[var(--audit-line)] bg-white/92 px-4 py-3 backdrop-blur-xl sm:px-6 md:px-8">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex min-w-0 flex-1 items-start gap-3">
          {onToggleSidebar ? (
            <button
              type="button"
              onClick={onToggleSidebar}
              aria-label={sidebarCollapsed ? "展开侧栏" : "收起侧栏"}
              title={sidebarCollapsed ? "展开侧栏" : "收起侧栏"}
              className="audit-focus-ring mt-0.5 hidden size-9 shrink-0 place-items-center rounded-[var(--audit-radius-md)] border border-[var(--audit-line)] bg-white text-base text-[var(--audit-ink-muted)] hover:bg-[var(--audit-surface-muted)] md:grid"
            >
              <span aria-hidden="true" className="leading-none">☰</span>
            </button>
          ) : null}
          <div className="min-w-0">
            <div className="flex flex-wrap items-center gap-2">
              <p className="audit-meta font-semibold">当前模块</p>
              <StatusPill tone="info">{project.auditTopic}</StatusPill>
              <StatusPill tone="neutral">连接检测中</StatusPill>
            </div>
            <div className="mt-1 flex flex-wrap items-end gap-x-3 gap-y-1">
              <div className="audit-section-title">{pageTitle}</div>
              <p className="audit-meta pb-0.5">
                {project.name} / {project.organizationName}
              </p>
            </div>
          </div>
        </div>
        <div className="flex min-w-0 flex-wrap items-center justify-end gap-2">
          <label className="relative min-w-56 flex-1 sm:flex-none" aria-label="全局搜索">
            <span className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-xs font-semibold text-[var(--audit-primary)]">
              搜
            </span>
            <input
              className="audit-focus-ring audit-topbar-input h-9 w-full pl-9 pr-3 text-sm"
              placeholder="检索文档、规则、底稿"
              type="search"
            />
          </label>
          {activeItem?.id !== "workspace" && (
            <Link className="audit-focus-ring audit-btn audit-btn-neutral min-h-8 px-3 py-1.5 text-xs" href="/workspace">
              返回工作台
            </Link>
          )}
          <StatusPill tone="success">项目进行中</StatusPill>
          <StatusPill tone="warning">AI 草稿需人工确认</StatusPill>
          <StatusPill tone={authSession?.store.ready ? "success" : "neutral"}>
            {authSession?.store.ready ? "权限已连接" : "权限头模式"}
          </StatusPill>
          {authSession ? (
            <StatusPill tone={authSession.auth_scope_type === "project" ? "info" : "neutral"}>
              生效：{authSession.role_label}
            </StatusPill>
          ) : null}
          <div className="ml-1 flex items-center gap-2 rounded-full border border-[var(--audit-line)] bg-[var(--audit-surface-muted)] px-2 py-1">
            <span className="grid size-6 place-items-center rounded-full bg-[var(--audit-ink)] text-xs font-semibold text-white">
              {auditClientRoleLabel(auditUser.role).slice(0, 1)}
            </span>
            <span className="text-xs font-semibold text-[var(--audit-ink-muted)]">
              {auditClientRoleLabel(auditUser.role)}视图
            </span>
            {authSession?.profile?.display_name ? (
              <span className="audit-meta hidden sm:inline">{authSession.profile.display_name}</span>
            ) : null}
          </div>
        </div>
      </div>

      <div className="mt-3 flex flex-nowrap gap-2 overflow-x-auto pb-1" aria-label="角色权限视图">
        {auditRoleOptions.map((role) => (
          <button
            key={role.id}
            className={`shrink-0 rounded-full border px-3 py-1 text-xs ${
              role.id === auditUser.role
                ? "border-[var(--audit-primary-line)] bg-[var(--audit-primary-soft)] font-semibold text-[var(--audit-primary)]"
                : "border-[var(--audit-line)] bg-white text-[var(--audit-ink-muted)]"
            }`}
            type="button"
            aria-pressed={role.id === auditUser.role}
            onClick={() => auditUser.setRole(role.id)}
          >
            {role.label}
            <span className="ml-1 text-[var(--audit-ink-subtle)]">
              {role.id === auditUser.role ? auditClientRoleDetail(role.id) : role.detail}
            </span>
          </button>
        ))}
      </div>

      <div className="mt-2 flex flex-nowrap gap-2 overflow-x-auto pb-1" role="tablist" aria-label="已打开模块">
        {openTabs.map((tab) => {
          const isActive = activeItem?.id === tab.id;
          const tabClassName = `audit-focus-ring inline-flex h-8 shrink-0 items-center gap-2 rounded-[var(--audit-radius-md)] border px-3 text-sm ${
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

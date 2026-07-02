"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useMemo, useState } from "react";

import { StatusPill } from "@/components/ui/status-pill";
import { fetchAuthSession } from "@/lib/api-client";
import type { AuthSessionResponse } from "@/lib/api-types";
import { auditClientRoleDetail, auditClientRoleLabel, auditRoleOptions } from "@/lib/audit-user";
import { findNavigationItemForPath } from "@/lib/navigation";
import { currentSelfCheckProject } from "@/lib/projects";

import { useAuditUser } from "./audit-user-context";

type ProjectContextBarProps = {
  readonly sidebarCollapsed?: boolean;
  readonly onToggleSidebar?: () => void;
};

export function ProjectContextBar({ sidebarCollapsed = false, onToggleSidebar }: ProjectContextBarProps = {}) {
  const project = currentSelfCheckProject;
  const pathname = usePathname();
  const auditUser = useAuditUser();
  const [authSession, setAuthSession] = useState<AuthSessionResponse | null>(null);
  const activeItem = useMemo(() => findNavigationItemForPath(pathname), [pathname]);

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

  const pageTitle = activeItem?.label ?? "工作台";

  return (
    <header className="sticky top-0 z-20 border-b border-[var(--audit-line)] bg-white px-3 py-2 sm:px-5 md:px-8">
      <div className="flex min-w-0 items-center justify-between gap-2">
        <div className="flex min-w-0 flex-1 items-center gap-2 sm:gap-3">
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
            <div className="truncate text-sm font-semibold leading-6 text-[var(--audit-ink)] sm:text-base">{pageTitle}</div>
          </div>
        </div>
        <div className="flex min-w-0 shrink-0 items-center justify-end gap-2">
          <label className="relative hidden min-w-0 md:block md:w-56 lg:w-64" aria-label="全局搜索">
            <span className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-xs font-semibold text-[var(--audit-primary)]">
              搜
            </span>
            <input
              className="audit-focus-ring audit-topbar-input h-9 w-full pl-9 pr-3 text-sm"
              name="globalSearch"
              autoComplete="off"
              placeholder="搜索"
              type="search"
            />
          </label>
          {activeItem?.id !== "workspace" && (
            <Link className="audit-focus-ring audit-btn audit-btn-neutral hidden min-h-8 px-3 py-1.5 text-xs lg:inline-flex" href="/workspace">
              工作台
            </Link>
          )}
          <details className="relative shrink-0">
            <summary className="audit-focus-ring flex h-9 cursor-pointer list-none items-center gap-2 rounded-[var(--audit-radius-md)] border border-[var(--audit-line)] bg-[var(--audit-surface-muted)] px-1.5 text-xs font-semibold text-[var(--audit-ink-muted)] hover:bg-white sm:px-2 [&::-webkit-details-marker]:hidden">
              <span className="grid size-6 place-items-center rounded-[var(--audit-radius-sm)] bg-[var(--audit-blue-deep)] text-xs font-semibold text-white" aria-hidden="true">
                {auditClientRoleLabel(auditUser.role).slice(0, 1)}
              </span>
              <span className="hidden lg:inline">权限</span>
            </summary>
            <div className="absolute right-0 mt-2 w-72 max-w-[calc(100vw-1.5rem)] rounded-[var(--audit-radius-lg)] border border-[var(--audit-line)] bg-white p-3 shadow-[0_16px_36px_rgb(23_62_105/0.16)]">
              <div className="flex items-start justify-between gap-3">
                <div>
                  <p className="text-sm font-semibold text-[var(--audit-ink)]">{auditClientRoleLabel(auditUser.role)}</p>
                  <p className="audit-meta mt-1">{project.name}</p>
                </div>
                {authSession?.store.ready ? <StatusPill tone="success">已连接</StatusPill> : null}
              </div>

              <dl className="mt-3 grid gap-2 border-t border-[var(--audit-line-soft)] pt-3 text-xs">
                <div className="flex items-center justify-between gap-3">
                  <dt className="text-[var(--audit-ink-muted)]">草稿</dt>
                  <dd className="font-semibold text-amber-700">待确认</dd>
                </div>
                <div className="flex items-center justify-between gap-3">
                  <dt className="text-[var(--audit-ink-muted)]">权限</dt>
                  <dd className="font-semibold text-[var(--audit-ink)]">{authSession?.role_label ?? "前端视图"}</dd>
                </div>
              </dl>

              <div className="mt-3 grid gap-2 border-t border-[var(--audit-line-soft)] pt-3" aria-label="角色权限视图">
                {auditRoleOptions.map((role) => (
                  <button
                    key={role.id}
                    className={`audit-focus-ring rounded-[var(--audit-radius-sm)] border px-3 py-2 text-left text-xs ${
                      role.id === auditUser.role
                        ? "border-[var(--audit-primary-line)] bg-[var(--audit-primary-soft)] font-semibold text-[var(--audit-primary)]"
                        : "border-[var(--audit-line-soft)] bg-white text-[var(--audit-ink-muted)] hover:bg-[var(--audit-surface-muted)]"
                    }`}
                    type="button"
                    aria-pressed={role.id === auditUser.role}
                    onClick={() => auditUser.setRole(role.id)}
                  >
                    <span className="block">{role.label}</span>
                    <span className="mt-0.5 block text-[var(--audit-ink-subtle)]">
                      {role.id === auditUser.role ? auditClientRoleDetail(role.id) : role.detail}
                    </span>
                  </button>
                ))}
              </div>
            </div>
          </details>
        </div>
      </div>
    </header>
  );
}

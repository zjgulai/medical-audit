"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useState, type ReactNode } from "react";

import { BrandLogo } from "@/components/shell/brand-logo";
import { useReplicaShellData } from "./use-replica-runtime";
import type { ReferenceNavigationItem } from "@/lib/reference-replica-data";

type ReplicaShellProps = {
  readonly children: ReactNode;
};

function isActivePath(pathname: string, href: string) {
  return pathname === href || pathname.startsWith(`${href}/`);
}

function navIcon(type: ReferenceNavigationItem["icon"]) {
  const common = "replica-menu-glyph";
  return <span className={`${common} replica-menu-glyph-${type}`} aria-hidden="true" />;
}

export function ReplicaShell({ children }: ReplicaShellProps) {
  const pathname = usePathname();
  const [collapsed, setCollapsed] = useState(false);
  const [closedTagPath, setClosedTagPath] = useState<string | null>(null);
  const shellData = useReplicaShellData();
  const activeItem = shellData.data.navigation.find((item) => isActivePath(pathname, item.href));
  const activeTagLabel = activeItem?.id === "chat" ? "新对话" : activeItem?.label ?? "新对话";
  const isActiveTagClosed = closedTagPath === pathname;
  const isChatRoute = isActivePath(pathname, "/chat");

  return (
    <div
      className={`replica-app-shell ${collapsed ? "replica-sidebar-collapsed" : ""} ${isChatRoute ? "replica-chat-shell" : ""}`}
      data-replica-source={shellData.source}
      data-replica-status={shellData.status}
    >
      <aside className="replica-sidebar" aria-label="医疗AI审计平台导航">
        <Link href="/chat" className="replica-brand" aria-label="医疗AI审计平台">
          <span className="replica-brand-mark">
            <BrandLogo height={28} priority width={28} />
          </span>
          <span className="replica-brand-text">医疗AI审计平台</span>
        </Link>

        <nav className="replica-main-nav" aria-label="主导航">
          {shellData.data.navigation.map((item) => {
            const active = isActivePath(pathname, item.href);
            return (
              <Link
                key={item.id}
                href={item.href}
                aria-current={active ? "page" : undefined}
                className={`replica-nav-item ${active ? "is-active" : ""}`}
              >
                {navIcon(item.icon)}
                <span>{item.label}</span>
              </Link>
            );
          })}
        </nav>

        <section className="replica-history" aria-labelledby="replica-history-title">
          <div className="replica-history-header">
            <h2 id="replica-history-title">历史对话</h2>
            <span aria-hidden="true">◷</span>
          </div>
          <div className="replica-history-list">
            {shellData.data.historyItems.map((item) => (
              <Link
                key={item.id}
                className="replica-history-item"
                href={`/chat?history=${encodeURIComponent(item.id)}`}
                aria-label={`打开历史对话：${item.title}`}
              >
                <span aria-hidden="true" className="replica-history-dot">✦</span>
                <span>{item.title}</span>
              </Link>
            ))}
          </div>
        </section>
      </aside>

      <div className="replica-workspace">
        {!isChatRoute ? (
          <>
            <header className="replica-topbar">
              <button
                type="button"
                aria-label={collapsed ? "展开侧栏" : "收起侧栏"}
                className="replica-icon-button"
                onClick={() => setCollapsed((value) => !value)}
              >
                ☰
              </button>
              <div className="replica-topbar-title">{activeItem?.label ?? "AI 对话"}</div>
              <div className="replica-user">
                <span className="replica-avatar" aria-hidden="true">{shellData.data.user.avatarLabel}</span>
                <span>{shellData.data.user.displayName}</span>
              </div>
            </header>

            <div className="replica-tagsbar" aria-label="打开页面">
              {!isActiveTagClosed ? (
                <span className="replica-page-tag">
                  <span aria-hidden="true" className="replica-page-tag-dot" />
                  {activeTagLabel}
                  <button
                    type="button"
                    className="replica-page-tag-close"
                    aria-label={`关闭${activeTagLabel}页签`}
                    onClick={() => setClosedTagPath(pathname)}
                  >
                    ×
                  </button>
                </span>
              ) : null}
            </div>
          </>
        ) : null}

        <div className="replica-page-scroll">{children}</div>
      </div>
    </div>
  );
}

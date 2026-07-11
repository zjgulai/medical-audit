"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useState, type ReactNode } from "react";

import { BrandLogo } from "@/components/shell/brand-logo";
import { AUDIT_PLATFORM_NAME } from "@/lib/brand";
import { referenceTopicNavigation, type ReferenceNavigationItem } from "@/lib/reference-replica-data";
import { useReplicaShellData } from "./use-replica-runtime";

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
  const [historyOpen, setHistoryOpen] = useState(false);
  const shellData = useReplicaShellData();
  const isTopicActive = isActivePath(pathname, referenceTopicNavigation.href);
  const activeItem = isTopicActive
    ? referenceTopicNavigation
    : shellData.data.navigation.find((item) => isActivePath(pathname, item.href));
  const activeTagLabel = activeItem?.id === "chat" ? "新对话" : activeItem?.label ?? "新对话";
  const isActiveTagClosed = closedTagPath === pathname;
  const isChatRoute = isActivePath(pathname, "/chat");

  return (
    <div
      className={`replica-app-shell ${collapsed ? "replica-sidebar-collapsed" : ""} ${isChatRoute ? "replica-chat-shell" : ""}`}
      data-replica-source={shellData.source}
      data-replica-status={shellData.status}
    >
      <aside className="replica-sidebar" aria-label={`${AUDIT_PLATFORM_NAME}导航`}>
        <Link href="/chat" className="replica-brand" aria-label={AUDIT_PLATFORM_NAME}>
          <span className="replica-brand-mark">
            <BrandLogo height={28} priority width={28} />
          </span>
          <span className="replica-brand-copy">
            <strong className="replica-brand-text">{AUDIT_PLATFORM_NAME}</strong>
          </span>
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

        <Link
          className={`replica-topic-entry ${isTopicActive ? "is-active" : ""}`}
          href={referenceTopicNavigation.href}
          aria-current={isTopicActive ? "page" : undefined}
          aria-label={`打开${referenceTopicNavigation.label}`}
        >
          {navIcon(referenceTopicNavigation.icon)}
          <strong>{referenceTopicNavigation.label}</strong>
        </Link>
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
      <button
        type="button"
        className="replica-history-fab"
        aria-expanded={historyOpen}
        aria-label="打开历史对话"
        onClick={() => setHistoryOpen((open) => !open)}
      >
        <span className="replica-history-fab-icon" aria-hidden="true">◷</span>
        <span>历史对话</span>
      </button>
      {historyOpen ? (
        <section className="replica-history-drawer" aria-labelledby="replica-history-title">
          <div className="replica-history-header">
            <h2 id="replica-history-title">历史对话</h2>
            <button type="button" aria-label="关闭历史对话" onClick={() => setHistoryOpen(false)}>×</button>
          </div>
          <div className="replica-history-list">
            {shellData.data.historyItems.map((item) => (
              <Link
                key={item.id}
                className="replica-history-item"
                href={`/chat?history=${encodeURIComponent(item.id)}`}
                aria-label={`打开历史对话：${item.title}`}
                onClick={() => setHistoryOpen(false)}
              >
                <span aria-hidden="true" className="replica-history-dot">✦</span>
                <span>{item.title}</span>
              </Link>
            ))}
          </div>
        </section>
      ) : null}
    </div>
  );
}

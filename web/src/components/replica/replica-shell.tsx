"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useRef, useState, type ReactNode } from "react";

import { BrandLogo } from "@/components/shell/brand-logo";
import { useAuditUser } from "@/components/shell/audit-user-context";
import {
  createQueryHistoryReviewTask,
  fetchProjects,
  isBackendRequestError
} from "@/lib/api-client";
import type { ProjectsResponse, QueryHistoryReviewTaskResponse } from "@/lib/api-types";
import { AUDIT_PLATFORM_NAME } from "@/lib/brand";
import {
  referenceTopicNavigation,
  type ReferenceHistoryItem,
  type ReferenceNavigationItem
} from "@/lib/reference-replica-data";
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
  const auditUser = useAuditUser();
  const [collapsed, setCollapsed] = useState(false);
  const [closedTagPath, setClosedTagPath] = useState<string | null>(null);
  const [historyOpen, setHistoryOpen] = useState(false);
  const [historyTaskItem, setHistoryTaskItem] = useState<ReferenceHistoryItem | null>(null);
  const [projects, setProjects] = useState<ProjectsResponse | null>(null);
  const [projectsLoading, setProjectsLoading] = useState(false);
  const [selectedProjectKey, setSelectedProjectKey] = useState("");
  const [historyTaskSaving, setHistoryTaskSaving] = useState(false);
  const [historyTaskError, setHistoryTaskError] = useState<string | null>(null);
  const [historyTaskResult, setHistoryTaskResult] = useState<QueryHistoryReviewTaskResponse | null>(null);
  const historyTaskGeneration = useRef(0);
  const historyTaskSubmission = useRef(false);
  const shellData = useReplicaShellData();
  const isTopicActive = isActivePath(pathname, referenceTopicNavigation.href);
  const activeItem = isTopicActive
    ? referenceTopicNavigation
    : shellData.data.navigation.find((item) => isActivePath(pathname, item.href));
  const activeTagLabel = activeItem?.id === "chat" ? "新对话" : activeItem?.label ?? "新对话";
  const isActiveTagClosed = closedTagPath === pathname;
  const isChatRoute = isActivePath(pathname, "/chat");
  const isProjectRoute = isActivePath(pathname, "/projects");
  const canCreateHistoryTask = auditUser.can("create_review_task");
  const selectedProjectVisible = Boolean(
    projects?.store.ready === true
      && projects.store.history_review_task_writes_ready === true
      && projects.items.some((project) => project.id === selectedProjectKey)
  );

  useEffect(() => {
    historyTaskGeneration.current += 1;
    historyTaskSubmission.current = false;
    setHistoryTaskItem(null);
    setProjects(null);
    setProjectsLoading(false);
    setSelectedProjectKey("");
    setHistoryTaskSaving(false);
    setHistoryTaskError(null);
    setHistoryTaskResult(null);
  }, [auditUser.role]);

  function closeHistory() {
    historyTaskGeneration.current += 1;
    historyTaskSubmission.current = false;
    setHistoryOpen(false);
    setHistoryTaskItem(null);
    setProjects(null);
    setProjectsLoading(false);
    setSelectedProjectKey("");
    setHistoryTaskSaving(false);
    setHistoryTaskError(null);
    setHistoryTaskResult(null);
  }

  function openHistoryTask(item: ReferenceHistoryItem) {
    if (!item.taskConvertible || !canCreateHistoryTask) {
      return;
    }
    const generation = historyTaskGeneration.current + 1;
    historyTaskGeneration.current = generation;
    historyTaskSubmission.current = false;
    setHistoryTaskItem(item);
    setProjects(null);
    setProjectsLoading(true);
    setSelectedProjectKey("");
    setHistoryTaskSaving(false);
    setHistoryTaskError(null);
    setHistoryTaskResult(null);

    void fetchProjects()
      .then((response) => {
        if (historyTaskGeneration.current !== generation) {
          return;
        }
        setProjects(response);
        if (!response.store.ready) {
          setHistoryTaskError("项目存储未就绪，暂不能创建复核任务。");
        } else if (response.store.history_review_task_writes_ready !== true) {
          setHistoryTaskError("复核任务持久化写入未就绪，暂不能创建复核任务。");
        }
      })
      .catch((error: unknown) => {
        if (historyTaskGeneration.current !== generation) {
          return;
        }
        setHistoryTaskError(historyTaskErrorMessage(error, "项目列表读取失败，请稍后重试。"));
      })
      .finally(() => {
        if (historyTaskGeneration.current === generation) {
          setProjectsLoading(false);
        }
      });
  }

  function confirmHistoryTask() {
    if (
      historyTaskItem === null ||
      !historyTaskItem.taskConvertible ||
      !canCreateHistoryTask ||
      !selectedProjectVisible ||
      historyTaskSubmission.current
    ) {
      return;
    }
    const generation = historyTaskGeneration.current;
    historyTaskSubmission.current = true;
    setHistoryTaskSaving(true);
    setHistoryTaskError(null);

    void createQueryHistoryReviewTask(historyTaskItem.id, { project_key: selectedProjectKey })
      .then((response) => {
        if (historyTaskGeneration.current === generation) {
          setHistoryTaskResult(response);
        }
      })
      .catch((error: unknown) => {
        if (historyTaskGeneration.current === generation) {
          setHistoryTaskError(historyTaskErrorMessage(error, "复核任务创建失败，请稍后重试。"));
        }
      })
      .finally(() => {
        if (historyTaskGeneration.current === generation) {
          historyTaskSubmission.current = false;
          setHistoryTaskSaving(false);
        }
      });
  }

  return (
    <div
      className={`replica-app-shell ${collapsed ? "replica-sidebar-collapsed" : ""} ${isChatRoute ? "replica-chat-shell" : ""} ${isProjectRoute ? "replica-project-shell" : ""}`}
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
        aria-label={historyOpen ? "收起历史对话" : "打开历史对话"}
        onClick={() => {
          if (historyOpen) {
            closeHistory();
          } else {
            setHistoryOpen(true);
          }
        }}
      >
        <span className="replica-history-fab-icon" aria-hidden="true">◷</span>
        <span>历史对话</span>
      </button>
      {historyOpen ? (
        <section className="replica-history-drawer" aria-labelledby="replica-history-title">
          <div className="replica-history-header">
            <h2 id="replica-history-title">历史对话</h2>
            <button type="button" aria-label="关闭历史对话" onClick={closeHistory}>×</button>
          </div>
          <div className="replica-history-list">
            {shellData.data.historyItems.map((item) => (
              <div key={item.id} className="replica-history-entry">
                <Link
                  className="replica-history-item"
                  href={`/chat?history=${encodeURIComponent(item.id)}`}
                  aria-label={`打开历史对话：${item.title}`}
                  onClick={closeHistory}
                >
                  <span aria-hidden="true" className="replica-history-dot">✦</span>
                  <span>{item.title}</span>
                </Link>
                {item.taskConvertible && canCreateHistoryTask ? (
                  <button
                    type="button"
                    className="replica-secondary-button"
                    aria-label={`转为任务：${item.title}`}
                    onClick={() => openHistoryTask(item)}
                  >
                    转为任务
                  </button>
                ) : null}
              </div>
            ))}
          </div>
          {historyTaskItem ? (
            <section
              aria-labelledby="replica-history-task-title"
              className="replica-history-task-panel"
            >
              <h3 id="replica-history-task-title">
                创建人工复核任务
              </h3>
              <p className="replica-history-task-question">{historyTaskItem.title}</p>
              {projectsLoading ? <p role="status">正在读取可见项目…</p> : null}
              {projects?.store.ready ? (
                <label className="replica-history-task-field">
                  <span>选择目标项目</span>
                  <select
                    aria-label="选择目标项目"
                    value={selectedProjectKey}
                    onChange={(event) => setSelectedProjectKey(event.target.value)}
                  >
                    <option value="">请选择</option>
                    {projects.items.map((project) => (
                      <option key={project.id} value={project.id}>{project.name}</option>
                    ))}
                  </select>
                </label>
              ) : null}
              {historyTaskError ? <p role="alert">{historyTaskError}</p> : null}
              {historyTaskResult ? (
                <div aria-live="polite">
                  <p>{historyTaskResult.task_id}</p>
                  {historyTaskAuditWarning(historyTaskResult) ? (
                    <p role="alert">{historyTaskAuditWarning(historyTaskResult)}</p>
                  ) : null}
                  <Link href={historyTaskResult.review_queue_href}>前往复核任务</Link>
                </div>
              ) : (
                <button
                  type="button"
                  aria-label="确认转为任务"
                  disabled={!selectedProjectVisible || historyTaskSaving || !canCreateHistoryTask}
                  onClick={confirmHistoryTask}
                  className="replica-primary-button replica-history-task-submit"
                >
                  {historyTaskSaving ? "正在创建…" : "确认转为任务"}
                </button>
              )}
            </section>
          ) : null}
        </section>
      ) : null}
    </div>
  );
}

function historyTaskErrorMessage(error: unknown, fallback: string): string {
  if (!isBackendRequestError(error)) return fallback;
  if (error.status === 401) return "登录状态已失效，请重新登录后再试。";
  if (error.status === 403) return "当前角色没有创建复核任务的权限。";
  if (error.status === 404) return "历史记录或目标项目不可见，请刷新后重试。";
  if (error.status === 409) return "该历史记录已存在冲突的复核任务，请前往任务队列核查。";
  if (error.status === 422) return "目标项目选择无效，请检查后重试。";
  if (error.status === 503) return "复核任务服务暂不可用，请稍后重试。";
  return fallback;
}

function historyTaskAuditWarning(result: QueryHistoryReviewTaskResponse): string | null {
  if (result.audit.status === "degraded") {
    return "任务已创建，但完成审计记录未写入；请联系管理员核查。";
  }
  if (result.audit.status === "local-only") {
    return "任务已创建，但当前仅有本地操作记录，不得作为生产审计证据。";
  }
  return null;
}

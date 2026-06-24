"use client";

import { useEffect, useState } from "react";

import { fetchDocumentPermissions, fetchSearchBackendStatus } from "@/lib/api-client";
import { DataSourceBadge } from "@/components/ui/data-source-badge";
import { SearchBackendStatusPill } from "@/components/portal/search-backend-status-pill";
import { StatusPill } from "@/components/ui/status-pill";
import type {
  DocumentPermissionsResponse,
  SearchBackendStatusResponse
} from "@/lib/api-types";
import { knowledgeBases } from "@/lib/portal-data";

type LoadStatus = "loading" | "ready" | "error";

export default function KnowledgeBasePage() {
  const [permissions, setPermissions] = useState<DocumentPermissionsResponse | null>(null);
  const [permissionStatus, setPermissionStatus] = useState<LoadStatus>("loading");
  const [backend, setBackend] = useState<SearchBackendStatusResponse | null>(null);
  const [backendStatus, setBackendStatus] = useState<LoadStatus>("loading");

  useEffect(() => {
    let cancelled = false;

    fetchDocumentPermissions()
      .then((result) => {
        if (cancelled) {
          return;
        }
        setPermissions(result);
        setPermissionStatus("ready");
      })
      .catch(() => {
        if (!cancelled) {
          setPermissionStatus("error");
        }
      });

    fetchSearchBackendStatus()
      .then((result) => {
        if (cancelled) {
          return;
        }
        setBackend(result);
        setBackendStatus("ready");
      })
      .catch(() => {
        if (!cancelled) {
          setBackendStatus("error");
        }
      });

    return () => {
      cancelled = true;
    };
  }, []);

  const sourceCollections = permissions?.source_collections ?? [];
  const matchingEmbeddingCount = backend?.details?.matching_embedding_count;

  return (
    <main className="grid min-w-0 gap-4 xl:grid-cols-[17rem_minmax(0,1fr)_18rem]">
      <aside className="audit-panel-rail min-w-0 p-5">
        <h2 className="audit-section-title">知识库来源</h2>
        <p className="audit-copy mt-2">来源集合与读权限来自后端 `/documents/permissions`，不在前台变更索引。</p>
        <div className="mt-3">
          <SearchBackendStatusPill />
        </div>
        <div className="mt-5 space-y-3">
          {permissionStatus === "loading" && <p className="audit-meta">来源集合加载中…</p>}
          {permissionStatus === "error" && (
            <p className="audit-meta text-amber-700">来源集合加载失败，请稍后刷新。</p>
          )}
          {permissionStatus === "ready" && sourceCollections.length === 0 && (
            <p className="audit-meta">当前角色无可读来源集合。</p>
          )}
          {sourceCollections.map((item) => (
            <article
              key={item.source_collection}
              className="rounded-[var(--audit-radius-md)] border border-[var(--audit-line)] bg-white p-3"
            >
              <div className="flex items-start justify-between gap-3">
                <div className="min-w-0">
                  <h3 className="truncate text-sm font-semibold text-[var(--audit-ink)]">{item.label}</h3>
                  <p className="audit-meta mt-1">{item.scope}</p>
                </div>
                <StatusPill tone="success">可读</StatusPill>
              </div>
            </article>
          ))}
        </div>
      </aside>

      <section className="audit-panel min-w-0 p-6">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div className="min-w-0">
            <p className="audit-kicker">知识库</p>
            <h1 className="audit-page-title">个人、系统、公开知识库</h1>
            <p className="audit-copy mt-2 max-w-3xl">
              当前角色可引用的来源集合来自后端实时权限；下方示例编目暂未接入真实逐库统计。
            </p>
          </div>
          <div className="flex flex-col items-end gap-2">
            <StatusPill tone="info">首期只读</StatusPill>
            <DataSourceBadge source="hybrid" />
          </div>
        </div>

        <section className="audit-panel-muted mt-6 p-4">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <h2 className="audit-section-title">可检索来源集合（实时）</h2>
            <StatusPill tone={permissionStatus === "error" ? "warning" : "neutral"}>
              {permissionStatus === "ready"
                ? `${sourceCollections.length} 个来源集合`
                : permissionStatus === "error"
                  ? "加载失败"
                  : "加载中"}
            </StatusPill>
          </div>
          {permissionStatus === "ready" && permissions && (
            <p className="audit-meta mt-2">当前角色：{permissions.role}</p>
          )}
          <div className="mt-4 grid gap-3">
            {permissionStatus === "loading" && <p className="audit-copy">正在从后端读取来源集合…</p>}
            {permissionStatus === "error" && (
              <p className="audit-copy text-amber-700">
                无法读取来源集合权限，请确认已登录并具备读取权限后刷新。
              </p>
            )}
            {permissionStatus === "ready" &&
              sourceCollections.map((item) => (
                <article key={item.source_collection} className="audit-panel-muted min-w-0 p-4">
                  <div className="flex items-start justify-between gap-3">
                    <div className="min-w-0">
                      <h3 className="audit-card-title">{item.label}</h3>
                      <p className="audit-meta mt-1">{item.scope}</p>
                    </div>
                    <StatusPill tone="success">可读</StatusPill>
                  </div>
                  <p className="audit-meta mt-3">来源标识：{item.source_collection}</p>
                </article>
              ))}
          </div>
        </section>

        <section className="audit-panel-muted mt-6 p-4">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <h2 className="audit-section-title">示例编目（待接入真实统计）</h2>
            <DataSourceBadge source="static" />
          </div>
          <p className="audit-meta mt-2">以下逐库文档/字符/应用数仍为示例数据，真实统计待后端编目接口接入。</p>
          <div className="audit-table-shell mt-4 max-w-full overflow-x-auto">
            <table className="audit-table min-w-[52rem]">
              <thead>
                <tr>
                  <th>知识库</th>
                  <th>类型</th>
                  <th>文档数</th>
                  <th>字符数</th>
                  <th>关联应用数</th>
                  <th>描述</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-[var(--audit-line-soft)]">
                {knowledgeBases.map((kb) => (
                  <tr key={kb.id}>
                    <td className="font-semibold text-[var(--audit-ink)]">{kb.name}</td>
                    <td className="text-[var(--audit-ink-muted)]">{kb.scope}</td>
                    <td className="text-[var(--audit-ink-muted)]">{kb.documentCount.toLocaleString()}</td>
                    <td className="text-[var(--audit-ink-muted)]">{kb.characterCount.toLocaleString()}</td>
                    <td className="text-[var(--audit-ink-muted)]">{kb.linkedAppCount}</td>
                    <td className="text-[var(--audit-ink-muted)]">{kb.description}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      </section>

      <aside className="min-w-0 space-y-4">
        <section className="audit-panel-rail p-5">
          <h2 className="audit-section-title">检索索引状态（实时）</h2>
          <div className="mt-4 space-y-3">
            <SummaryMetric
              label="检索后端"
              value={backendStatus === "ready" && backend ? backend.backend : backendStatus === "error" ? "异常" : "检测中"}
            />
            <SummaryMetric
              label="索引就绪"
              value={
                backendStatus === "ready" && backend
                  ? backend.ready
                    ? "就绪"
                    : "待初始化"
                  : backendStatus === "error"
                    ? "异常"
                    : "检测中"
              }
            />
            <SummaryMetric
              label="匹配 embedding"
              value={typeof matchingEmbeddingCount === "number" ? matchingEmbeddingCount.toLocaleString() : "—"}
            />
            <SummaryMetric
              label="可读来源集合"
              value={permissionStatus === "ready" ? String(sourceCollections.length) : permissionStatus === "error" ? "异常" : "检测中"}
            />
          </div>
        </section>
        <a className="audit-focus-ring audit-action-card p-5" href="/documents">
          <p className="audit-kicker">文档检索</p>
          <h2 className="audit-section-title mt-2">进入统一检索首页</h2>
          <p className="audit-copy mt-2">按来源集合、搜索历史和引用结果组织材料。</p>
        </a>
        <a className="audit-focus-ring audit-action-card p-5" href="/pages/index-admin">
          <p className="audit-kicker">索引管理</p>
          <h2 className="audit-section-title mt-2">进入运维控制台</h2>
          <p className="audit-copy mt-2">发布、回滚、重载和验收仍在受控后台执行。</p>
        </a>
      </aside>
    </main>
  );
}

function SummaryMetric({ label, value }: { readonly label: string; readonly value: string }) {
  return (
    <div className="flex items-center justify-between gap-4 rounded-[var(--audit-radius-md)] bg-[var(--audit-surface-muted)] px-3 py-2">
      <span className="text-sm text-[var(--audit-ink-muted)]">{label}</span>
      <span className="text-sm font-semibold text-[var(--audit-ink)]">{value}</span>
    </div>
  );
}

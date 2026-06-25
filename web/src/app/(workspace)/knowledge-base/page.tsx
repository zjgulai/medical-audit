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
        if (!cancelled) {
          setPermissions(result);
          setPermissionStatus("ready");
        }
      })
      .catch(() => {
        if (!cancelled) {
          setPermissionStatus("error");
        }
      });

    fetchSearchBackendStatus()
      .then((result) => {
        if (!cancelled) {
          setBackend(result);
          setBackendStatus("ready");
        }
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
    <main className="space-y-5">
      <section className="audit-panel p-6">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div className="min-w-0">
            <p className="audit-kicker">知识库</p>
            <h1 className="audit-page-title">个人、系统、公开知识库</h1>
          </div>
          <SearchBackendStatusPill />
        </div>

        <div className="mt-5 grid gap-2 sm:grid-cols-2 xl:grid-cols-4">
          <Metric
            label="检索后端"
            value={backendStatus === "ready" && backend ? backend.backend : backendStatus === "error" ? "异常" : "检测中"}
          />
          <Metric
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
          <Metric
            label="匹配 embedding"
            value={typeof matchingEmbeddingCount === "number" ? matchingEmbeddingCount.toLocaleString() : "—"}
          />
          <Metric
            label="可读来源集合"
            value={permissionStatus === "ready" ? String(sourceCollections.length) : permissionStatus === "error" ? "异常" : "检测中"}
          />
        </div>
      </section>

      <section className="audit-panel p-6">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <h2 className="audit-section-title">可检索来源集合</h2>
          <StatusPill tone={permissionStatus === "error" ? "warning" : "neutral"}>
            {permissionStatus === "ready"
              ? `${sourceCollections.length} 个来源集合`
              : permissionStatus === "error"
                ? "加载失败"
                : "加载中"}
          </StatusPill>
        </div>

        {permissionStatus === "loading" && <p className="audit-copy mt-4">正在读取来源集合…</p>}
        {permissionStatus === "error" && (
          <p className="audit-copy mt-4 text-amber-700">无法读取来源集合权限，请登录后刷新。</p>
        )}
        {permissionStatus === "ready" && sourceCollections.length === 0 && (
          <p className="audit-copy mt-4">当前角色无可读来源集合。</p>
        )}
        {permissionStatus === "ready" && sourceCollections.length > 0 && (
          <div className="mt-4 grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
            {sourceCollections.map((item) => (
              <article key={item.source_collection} className="audit-panel-muted min-w-0 p-4">
                <div className="flex items-start justify-between gap-2">
                  <h3 className="audit-card-title min-w-0 truncate">{item.label}</h3>
                  <StatusPill tone="success">可读</StatusPill>
                </div>
                <p className="audit-meta mt-2">{item.scope}</p>
              </article>
            ))}
          </div>
        )}
      </section>

      <section className="audit-panel p-6">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <h2 className="audit-section-title">逐库编目</h2>
          <DataSourceBadge source="static" />
        </div>
        <p className="audit-meta mt-2">示例数据，真实逐库统计待编目接口接入。</p>
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

      <section className="grid gap-3 sm:grid-cols-2">
        <a className="audit-focus-ring audit-action-card p-5" href="/documents">
          <p className="audit-kicker">文档检索</p>
          <h2 className="audit-section-title mt-2">统一检索首页</h2>
        </a>
        <a className="audit-focus-ring audit-action-card p-5" href="/pages/index-admin">
          <p className="audit-kicker">索引管理</p>
          <h2 className="audit-section-title mt-2">运维控制台</h2>
        </a>
      </section>
    </main>
  );
}

function Metric({ label, value }: { readonly label: string; readonly value: string }) {
  return (
    <div className="flex items-center justify-between gap-3 rounded-[var(--audit-radius-md)] bg-[var(--audit-surface-muted)] px-3 py-2.5">
      <span className="text-sm text-[var(--audit-ink-muted)]">{label}</span>
      <span className="text-sm font-semibold text-[var(--audit-ink)]">{value}</span>
    </div>
  );
}

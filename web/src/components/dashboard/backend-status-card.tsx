"use client";

import { useEffect, useState } from "react";

import { StatusPill } from "@/components/ui/status-pill";
import { fetchBackendHealth, fetchSearchBackendStatus } from "@/lib/api-client";

type StatusState =
  | { readonly status: "loading" }
  | {
      readonly status: "ready";
      readonly backendVersion: string;
      readonly searchBackend: string;
      readonly searchReady: boolean;
      readonly matchingEmbeddingCount?: number;
    }
  | { readonly status: "error" };

export function BackendStatusCard() {
  const [state, setState] = useState<StatusState>({ status: "loading" });

  useEffect(() => {
    let active = true;

    async function loadStatus() {
      try {
        const [health, search] = await Promise.all([fetchBackendHealth(), fetchSearchBackendStatus()]);

        if (!active) {
          return;
        }

        setState({
          status: "ready",
          backendVersion: health.version,
          searchBackend: search.backend,
          searchReady: search.ready,
          matchingEmbeddingCount: search.details?.matching_embedding_count
        });
      } catch {
        if (active) {
          setState({ status: "error" });
        }
      }
    }

    void loadStatus();

    return () => {
      active = false;
    };
  }, []);

  return (
    <section
      aria-label="系统健康"
      className="rounded-[28px] border border-slate-200 bg-white p-6 shadow-[var(--audit-shadow-card)]"
    >
      <div className="flex items-start justify-between gap-4">
        <div>
          <p className="text-sm font-medium text-blue-700">系统健康</p>
          <h2 className="mt-2 text-xl font-semibold tracking-tight text-slate-950">后端与索引联通</h2>
        </div>
        {state.status === "ready" && (
          <StatusPill tone={state.searchReady ? "success" : "warning"}>
            {state.searchReady ? "可检索" : "待初始化"}
          </StatusPill>
        )}
        {state.status === "loading" && <StatusPill tone="neutral">检测中</StatusPill>}
        {state.status === "error" && <StatusPill tone="warning">只读失败</StatusPill>}
      </div>

      {state.status === "loading" && (
        <p className="mt-5 text-sm text-slate-600">正在通过 Next.js 代理检查 FastAPI 和搜索后端。</p>
      )}
      {state.status === "error" && (
        <div className="mt-5 space-y-1 text-sm text-slate-600">
          <p>后端状态无法确认</p>
          <p>当前页面不会生成疑点或正式底稿。</p>
        </div>
      )}
      {state.status === "ready" && (
        <div className="mt-5 grid gap-3 sm:grid-cols-3">
          <div className="rounded-2xl bg-slate-50 p-4">
            <p className="text-xs text-slate-500">API</p>
            <p className="mt-1 text-sm font-semibold text-slate-950">FastAPI 正常</p>
            <p className="mt-1 text-xs text-slate-500">v{state.backendVersion}</p>
          </div>
          <div className="rounded-2xl bg-slate-50 p-4">
            <p className="text-xs text-slate-500">Search</p>
            <p className="mt-1 text-sm font-semibold text-slate-950">
              {state.searchBackend} {state.searchReady ? "已就绪" : "未就绪"}
            </p>
          </div>
          <div className="rounded-2xl bg-slate-50 p-4">
            <p className="text-xs text-slate-500">Embeddings</p>
            <p className="mt-1 text-sm font-semibold text-slate-950">
              {state.matchingEmbeddingCount ?? 0} vectors
            </p>
          </div>
        </div>
      )}
    </section>
  );
}

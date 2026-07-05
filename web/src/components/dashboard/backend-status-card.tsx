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
  const headline =
    state.status === "ready"
      ? "知识库连接正常"
      : state.status === "loading"
        ? "正在检测知识库"
        : "知识库暂未连接";

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
      aria-label="知识库状态"
      className="audit-panel p-5"
    >
      <div className="flex items-start justify-between gap-4">
        <div>
          <p className="audit-kicker">服务状态</p>
          <h2 className="mt-2 audit-section-title">{headline}</h2>
        </div>
        {state.status === "ready" && (
          <StatusPill tone={state.searchReady ? "success" : "warning"}>
            {state.searchReady ? "可检索" : "待初始化"}
          </StatusPill>
        )}
        {state.status === "loading" && <StatusPill tone="neutral">检测中</StatusPill>}
        {state.status === "error" && <StatusPill tone="warning">本地样例</StatusPill>}
      </div>

      {state.status === "loading" && (
        <p className="mt-5 audit-copy">正在检查知识库和检索服务。</p>
      )}
      {state.status === "error" && (
        <div className="mt-5 space-y-1 audit-copy">
          <p>当前展示演示数据，可先体验检索、审证和底稿路径。</p>
          <p>正式生成疑点和底稿前，请先完成数据同步。</p>
        </div>
      )}
      {state.status === "ready" && (
        <div className="mt-5 grid gap-3 sm:grid-cols-3">
          <div className="audit-panel-muted p-4">
            <p className="audit-meta">工作台</p>
            <p className="mt-1 audit-compact-title">工作台可用</p>
            <p className="mt-1 audit-meta">版本 {state.backendVersion}</p>
          </div>
          <div className="audit-panel-muted p-4">
            <p className="audit-meta">检索服务</p>
            <p className="mt-1 audit-compact-title">
              {state.searchReady ? "材料可检索" : "等待初始化"}
            </p>
          </div>
          <div className="audit-panel-muted p-4">
            <p className="audit-meta">可引用资料</p>
            <p className="mt-1 audit-compact-title">
              {(state.matchingEmbeddingCount ?? 0).toLocaleString("zh-CN")} 条
            </p>
          </div>
        </div>
      )}
    </section>
  );
}

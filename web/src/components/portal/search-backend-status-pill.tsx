"use client";

import { useEffect, useState } from "react";

import { fetchSearchBackendStatus } from "@/lib/api-client";
import { StatusPill } from "@/components/ui/status-pill";

type SearchBackendLoadState =
  | { readonly status: "checking" }
  | { readonly status: "ready"; readonly backend: string; readonly ready: boolean }
  | { readonly status: "error" };

export function SearchBackendStatusPill() {
  const [searchBackendState, setSearchBackendState] = useState<SearchBackendLoadState>({
    status: "checking"
  });

  useEffect(() => {
    let cancelled = false;

    fetchSearchBackendStatus()
      .then((status) => {
        if (cancelled) {
          return;
        }

        setSearchBackendState({
          status: "ready",
          backend: status.backend,
          ready: status.ready
        });
      })
      .catch(() => {
        if (!cancelled) {
          setSearchBackendState({ status: "error" });
        }
      });

    return () => {
      cancelled = true;
    };
  }, []);

  const searchBackendTag =
    searchBackendState.status === "ready"
      ? `检索索引：${searchBackendState.ready ? "就绪" : "待初始化"}（${searchBackendState.backend}）`
      : searchBackendState.status === "error"
        ? "检索索引：异常"
        : "检索索引：检测中";

  return (
    <StatusPill tone={searchBackendState.status === "error" ? "warning" : "info"}>
      {searchBackendTag}
    </StatusPill>
  );
}

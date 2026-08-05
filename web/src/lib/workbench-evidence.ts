type StatusTone = "neutral" | "info" | "warning" | "danger" | "success";

type WorkbenchStore = {
  readonly ready: boolean;
  readonly backend: string;
};

export type WorkbenchTransportStatus = "loading" | "ready" | "fallback";

export type WorkbenchEvidenceState = {
  readonly tone: StatusTone;
  readonly label: string;
  readonly isSeed: boolean;
  readonly isFallback: boolean;
  readonly isPersistent: boolean;
};

export function classifyWorkbenchEvidence(
  status: WorkbenchTransportStatus,
  store: WorkbenchStore
): WorkbenchEvidenceState {
  if (status === "loading") {
    return {
      tone: "info",
      label: "连接中",
      isSeed: false,
      isFallback: false,
      isPersistent: false
    };
  }

  if (!store.ready || isStaticFallbackBackend(store.backend)) {
    return {
      tone: "warning",
      label: "本地样例兜底",
      isSeed: false,
      isFallback: true,
      isPersistent: false
    };
  }

  if (isReadonlySeedBackend(store.backend)) {
    return {
      tone: "warning",
      label: "后端种子数据",
      isSeed: true,
      isFallback: false,
      isPersistent: false
    };
  }

  return {
    tone: "success",
    label: "持久后端",
    isSeed: false,
    isFallback: false,
    isPersistent: true
  };
}

export function isReadonlySeedBackend(backend: string): boolean {
  return backend.startsWith("Readonly") && backend.endsWith("Seed");
}

function isStaticFallbackBackend(backend: string): boolean {
  return backend === "portal-data-static-fallback";
}

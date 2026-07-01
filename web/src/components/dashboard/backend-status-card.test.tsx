import { render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { BackendStatusCard } from "./backend-status-card";

describe("BackendStatusCard", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
    vi.restoreAllMocks();
  });

  it("shows backend and search backend readiness", async () => {
    vi.stubGlobal(
      "fetch",
      vi
        .fn()
        .mockResolvedValueOnce({
          ok: true,
          json: async () => ({ status: "ok", version: "0.1.0", data_root: "/data" })
        })
        .mockResolvedValueOnce({
          ok: true,
          json: async () => ({
            backend: "postgres",
            ready: true,
            details: { matching_embedding_count: 48985 }
          })
        })
    );

    render(<BackendStatusCard />);

    await waitFor(() => {
      expect(screen.getByText("工作台可用")).toBeInTheDocument();
    });
    expect(screen.getByText("材料可检索")).toBeInTheDocument();
    expect(screen.getByText("48,985 条")).toBeInTheDocument();
  });

  it("shows a conservative failure state", async () => {
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new Error("network failed")));

    render(<BackendStatusCard />);

    await waitFor(() => {
      expect(screen.getByText("服务状态暂不可用")).toBeInTheDocument();
    });
  });
});

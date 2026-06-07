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
      expect(screen.getByText("FastAPI 正常")).toBeInTheDocument();
    });
    expect(screen.getByText("postgres 已就绪")).toBeInTheDocument();
    expect(screen.getByText("48985 vectors")).toBeInTheDocument();
  });

  it("shows a conservative failure state", async () => {
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new Error("network failed")));

    render(<BackendStatusCard />);

    await waitFor(() => {
      expect(screen.getByText("后端状态无法确认")).toBeInTheDocument();
    });
  });
});

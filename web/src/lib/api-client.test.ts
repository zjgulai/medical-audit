import { afterEach, describe, expect, it, vi } from "vitest";

import { fetchBackendHealth, fetchSearchBackendStatus } from "./api-client";

describe("api-client", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
    vi.restoreAllMocks();
  });

  it("fetches backend health through the Next proxy", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => ({
        ok: true,
        json: async () => ({
          status: "ok",
          version: "0.1.0",
          data_root: "/tmp/data"
        })
      }))
    );

    const health = await fetchBackendHealth();

    expect(fetch).toHaveBeenCalledWith("/api/backend/health", {
      headers: { Accept: "application/json" },
      cache: "no-store"
    });
    expect(health.status).toBe("ok");
  });

  it("raises a clear error when the search backend check fails", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => ({
        ok: false,
        status: 409,
        text: async () => "search engine is not initialized"
      }))
    );

    await expect(fetchSearchBackendStatus()).rejects.toThrow(
      "Backend request failed: GET /api/backend/index/search-backend returned 409"
    );
  });
});

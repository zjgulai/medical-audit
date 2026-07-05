import { afterEach, describe, expect, it, vi } from "vitest";

import {
  resolveServerBackendBaseUrl,
  serverGetJson,
  toServerBackendUrl
} from "./api-client.server";

describe("api-client.server", () => {
  afterEach(() => {
    vi.unstubAllEnvs();
    vi.unstubAllGlobals();
  });

  it("resolves and normalizes the server backend base URL", () => {
    vi.stubEnv("MEDICAL_AUDIT_API_BASE_URL", "https://backend.example.test///");

    expect(resolveServerBackendBaseUrl()).toBe("https://backend.example.test");
  });

  it("rejects invalid backend base URLs", () => {
    expect(() => resolveServerBackendBaseUrl("file:///tmp/backend")).toThrow(
      "MEDICAL_AUDIT_API_BASE_URL must use http or https."
    );
    expect(() => resolveServerBackendBaseUrl("not a url")).toThrow(
      "MEDICAL_AUDIT_API_BASE_URL must be a valid URL."
    );
  });

  it("builds absolute backend URLs from API paths", () => {
    expect(toServerBackendUrl("/api/v1/auth/session", "http://127.0.0.1:8021")).toBe(
      "http://127.0.0.1:8021/api/v1/auth/session"
    );
    expect(() => toServerBackendUrl("api/v1/auth/session")).toThrow(
      "Backend API path must start with '/'."
    );
  });

  it("fetches JSON with no-store semantics from the absolute backend URL", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => ({
        ok: true,
        json: async () => ({ status: "ok" })
      }))
    );

    const result = await serverGetJson<{ readonly status: string }>(
      "/api/v1/health",
      {},
      "http://127.0.0.1:8021"
    );

    expect(fetch).toHaveBeenCalledWith(
      "http://127.0.0.1:8021/api/v1/health",
      expect.objectContaining({ cache: "no-store" })
    );
    expect(result.status).toBe("ok");
  });
});

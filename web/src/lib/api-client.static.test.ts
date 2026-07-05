import { describe, expect, it } from "vitest";

import { failStaticBackendRequest, staticBackendRuntime } from "./api-client.static";

describe("api-client.static", () => {
  it("keeps static export backend requests fail-closed", () => {
    expect(staticBackendRuntime.dynamicApiAvailable).toBe(false);
    expect(() => failStaticBackendRequest("/api/v1/query")).toThrow(
      "Static export cannot call backend endpoint '/api/v1/query'."
    );
  });
});

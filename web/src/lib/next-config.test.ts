import { describe, expect, it } from "vitest";

import nextConfig from "../../next.config";

type RewriteRule = {
  readonly source: string;
  readonly destination: string;
};

async function getRewriteRules(): Promise<readonly RewriteRule[]> {
  if (typeof nextConfig.rewrites !== "function") {
    throw new Error("nextConfig.rewrites must be a function in dev mode.");
  }

  return (await nextConfig.rewrites()) as readonly RewriteRule[];
}

describe("nextConfig backend rewrites", () => {
  it("keeps Next dev aligned with production nginx backend page routes", async () => {
    const rules = await getRewriteRules();

    expect(rules.map((rule) => rule.source)).toEqual(
      expect.arrayContaining([
        "/api/backend/:path*",
        "/api/v1/:path*",
        "/pages/:path*",
        "/review-tasks/:path*",
        "/audit/:path*",
        "/audit-findings/:path*",
        "/static/:path*"
      ])
    );
  });

  it("strips frontend-only API prefixes before proxying to the backend", async () => {
    const rules = await getRewriteRules();

    expect(rules.find((rule) => rule.source === "/api/backend/:path*")).toMatchObject({
      destination: "http://127.0.0.1:8021/:path*"
    });
    expect(rules.find((rule) => rule.source === "/pages/:path*")).toMatchObject({
      destination: "http://127.0.0.1:8021/pages/:path*"
    });
  });
});

import type { NextConfig } from "next";

const DEFAULT_BACKEND_BASE_URL = "http://127.0.0.1:8021";

const resolveBackendBaseUrl = (value: string | undefined): string => {
  const candidate = (value?.trim() || DEFAULT_BACKEND_BASE_URL).replace(/\/+$/, "");
  let parsed: URL;

  try {
    parsed = new URL(candidate);
  } catch (error) {
    throw new Error("MEDICAL_AUDIT_API_BASE_URL must be a valid URL.", { cause: error });
  }

  if (parsed.protocol !== "http:" && parsed.protocol !== "https:") {
    throw new Error("MEDICAL_AUDIT_API_BASE_URL must use http or https.");
  }

  return candidate;
};

const backendBaseUrl = resolveBackendBaseUrl(process.env.MEDICAL_AUDIT_API_BASE_URL);
const staticExportEnabled = process.env.MEDICAL_AUDIT_NEXT_EXPORT === "1";

const backendRouteSources = [
  "/health",
  "/query",
  "/index/:path*",
  "/query/:path*",
  "/operation/:path*",
  "/audit/:path*",
  "/audit-findings/:path*",
  "/preview/:path*",
  "/static/:path*",
  "/pages/:path*",
  "/review-tasks/:path*"
] as const;

const nextConfig: NextConfig = {
  reactStrictMode: true,
  ...(staticExportEnabled ? { output: "export" as const } : {}),
  typescript: {
    ignoreBuildErrors: false,
    tsconfigPath: "tsconfig.json"
  },
  ...(staticExportEnabled
    ? {}
    : {
        async rewrites() {
          return [
            {
              source: "/api/backend/:path*",
              destination: `${backendBaseUrl}/:path*`
            },
            {
              source: "/api/v1/:path*",
              destination: `${backendBaseUrl}/:path*`
            },
            ...backendRouteSources.map((source) => ({
              source,
              destination: `${backendBaseUrl}${source}`
            }))
          ];
        }
      })
};

export default nextConfig;

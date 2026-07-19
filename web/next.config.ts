import type { NextConfig } from "next";

const DEFAULT_BACKEND_BASE_URL = "http://127.0.0.1:8021";
const COMMIT_SHA_PATTERN = /^[0-9a-f]{40}$/;

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

export const resolveStaticExportBuildId = (
  value: string | undefined
): string | undefined => {
  const candidate = value?.trim();
  if (!candidate) {
    return undefined;
  }

  if (!COMMIT_SHA_PATTERN.test(candidate)) {
    throw new Error("MEDICAL_AUDIT_DEPLOY_SHA must be a full lowercase commit SHA.");
  }

  return candidate;
};

const backendBaseUrl = resolveBackendBaseUrl(process.env.MEDICAL_AUDIT_API_BASE_URL);
const staticExportEnabled = process.env.MEDICAL_AUDIT_NEXT_EXPORT === "1";
const staticExportBuildId = staticExportEnabled
  ? resolveStaticExportBuildId(process.env.MEDICAL_AUDIT_DEPLOY_SHA)
  : undefined;

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
  ...(staticExportBuildId ? { generateBuildId: () => staticExportBuildId } : {}),
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

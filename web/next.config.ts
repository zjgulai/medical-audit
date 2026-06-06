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

const nextConfig: NextConfig = {
  reactStrictMode: true,
  typescript: {
    ignoreBuildErrors: false,
    tsconfigPath: "tsconfig.json"
  },
  async rewrites() {
    return [
      {
        source: "/api/backend/:path*",
        destination: `${backendBaseUrl}/:path*`
      }
    ];
  }
};

export default nextConfig;

import type { NextConfig } from "next";

const backendBaseUrl = process.env.MEDICAL_AUDIT_API_BASE_URL ?? "http://127.0.0.1:8021";

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

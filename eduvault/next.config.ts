import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  skipTrailingSlashRedirect: true,
  async rewrites() {
    // Proxy /api/* to the Django backend in development so the browser never
    // has to make cross-origin requests (avoids CORS issues with cookies/headers).
    // In production, point NEXT_PUBLIC_API_BASE_URL at your real API and remove these.
    const backendOrigin = process.env.BACKEND_ORIGIN ?? "http://127.0.0.1:8000";
    return [
      {
        source: "/api/:path*/",
        destination: `${backendOrigin}/api/:path*/`,
      },
      {
        source: "/api/:path*",
        destination: `${backendOrigin}/api/:path*`,
      },
    ];
  },
};

export default nextConfig;

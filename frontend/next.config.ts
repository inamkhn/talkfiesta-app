import type { NextConfig } from "next";

// Server-only upstream. Browser requests stay on the frontend origin so the
// HttpOnly refresh cookie does not require cross-origin browser credentials.
const apiOrigin = (process.env.API_PROXY_ORIGIN || "http://127.0.0.1:8000").replace(/\/$/, "");
const nextConfig: NextConfig = {
  async rewrites() {
    return [{ source: "/api/v1/:path*", destination: `${apiOrigin}/api/v1/:path*` }];
  },
};
export default nextConfig;

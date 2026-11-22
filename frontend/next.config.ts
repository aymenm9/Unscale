import type { NextConfig } from "next";

// The browser only ever talks to this Next.js app. /api/* is forwarded to FastAPI,
// so the login cookie stays same-site (works on Vercel + Render too).
const backend = process.env.BACKEND_URL ?? "http://localhost:8000";

const nextConfig: NextConfig = {
  turbopack: {
    rules: {
      "*.css": {
        loaders: ["@tailwindcss/turbopack"],
        as: "*.css",
      },
    },
  },
  experimental: {
    // AI steps (rewrite a draft, simulate a reply) can take 1-2 minutes. The default proxy
    // timeout (30s) would cut them off, so allow 3 minutes.
    proxyTimeout: 180_000,
  },
  async rewrites() {
    return [{ source: "/api/:path*", destination: `${backend}/api/:path*` }];
  },
};

export default nextConfig;

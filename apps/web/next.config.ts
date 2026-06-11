import type { NextConfig } from "next";

const TEAM_HUB_URL = process.env.NEXT_PUBLIC_TEAM_HUB_URL ?? "https://team-iota-neon.vercel.app";

const nextConfig: NextConfig = {
  experimental: {
    proxyTimeout: 1000 * 300, // 300s — GLM thinking blocks take 60-180s for complex queries
  },
  async redirects() {
    return [
      {
        source: "/team",
        destination: TEAM_HUB_URL,
        permanent: true,
      },
      {
        source: "/stocks/:ticker/anjali",
        destination: "/stocks/:ticker/quantfactor",
        permanent: true,
      },
      {
        source: "/team/:path*",
        destination: `${TEAM_HUB_URL}/:path*`,
        permanent: true,
      },
    ];
  },
  async rewrites() {
    return [
      {
        // API_PROXY_URL: server-side override for containerized deploys where
        // the browser URL (localhost:8000) differs from the server's route to
        // the API (http://api:8000 on the compose network).
        source: "/api/:path*",
        destination: `${process.env.API_PROXY_URL ?? process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000"}/:path*`,
      },
    ];
  },
};

export default nextConfig;

import type { NextConfig } from "next";

const TEAM_HUB_URL = process.env.NEXT_PUBLIC_TEAM_HUB_URL ?? "https://team-iota-neon.vercel.app";

// Content-Security-Policy — shipped in Report-Only mode first. The app talks to
// several external origins (Supabase, LiveKit voice, Stripe, Vercel analytics);
// enforcing a CSP blind would risk breaking voice/checkout. Report-Only collects
// violations without blocking, so the policy can be tightened then flipped to
// enforce (rename header to `Content-Security-Policy`) once reports are clean.
const CSP_REPORT_ONLY = [
  "default-src 'self'",
  // Next.js inlines bootstrap/runtime scripts; unsafe-inline/eval needed without nonces.
  "script-src 'self' 'unsafe-inline' 'unsafe-eval' https://js.stripe.com https://va.vercel-scripts.com",
  "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com",
  "font-src 'self' https://fonts.gstatic.com data:",
  "img-src 'self' data: blob: https:",
  // Supabase (REST+realtime wss), LiveKit voice (wss), Stripe, Vercel insights, API origin.
  "connect-src 'self' https://*.supabase.co wss://*.supabase.co https://*.livekit.cloud wss://*.livekit.cloud https://api.stripe.com https://*.vercel-insights.com https://neuralquant.onrender.com",
  "frame-src 'self' https://js.stripe.com https://hooks.stripe.com",
  "media-src 'self' blob:",
  "worker-src 'self' blob:",
  "object-src 'none'",
  "base-uri 'self'",
  "form-action 'self'",
  "frame-ancestors 'self'",
  // NOTE: upgrade-insecure-requests is intentionally omitted — it is ignored in
  // Report-Only mode and logs a console error. Re-add it when flipping to enforce.
].join("; ");

// Static security headers — safe to enforce immediately on a normal SPA.
// microphone=(self) is intentional: Veronica voice captures mic on this origin.
const securityHeaders = [
  { key: "Strict-Transport-Security", value: "max-age=63072000; includeSubDomains" },
  { key: "X-Frame-Options", value: "SAMEORIGIN" },
  { key: "X-Content-Type-Options", value: "nosniff" },
  { key: "Referrer-Policy", value: "strict-origin-when-cross-origin" },
  { key: "Permissions-Policy", value: "camera=(), microphone=(self), geolocation=(), browsing-topics=()" },
  { key: "X-DNS-Prefetch-Control", value: "on" },
  { key: "Content-Security-Policy-Report-Only", value: CSP_REPORT_ONLY },
];

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
  async headers() {
    return [
      {
        source: "/:path*",
        headers: securityHeaders,
      },
    ];
  },
};

export default nextConfig;

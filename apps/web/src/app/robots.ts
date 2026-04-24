import type { MetadataRoute } from "next";

export default function robots(): MetadataRoute.Robots {
  return {
    rules: [
      {
        userAgent: "*",
        allow: "/",
        disallow: ["/api/", "/auth/", "/dashboard", "/watchlist", "/backtest", "/query"],
      },
    ],
    sitemap: "https://neuralquant.vercel.app/sitemap.xml",
  };
}
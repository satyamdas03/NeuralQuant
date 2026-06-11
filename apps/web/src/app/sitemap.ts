import type { MetadataRoute } from "next";

const SITE_URL = process.env.NEXT_PUBLIC_SITE_URL?.trim() || "https://neuralquant.co";

// Core NSE tickers for SEO (top 200 by market cap)
const NSE_TICKERS = [
  "RELIANCE.NS", "TCS.NS", "HDFCBANK.NS", "INFY.NS", "ICICIBANK.NS",
  "BHARTIARTL.NS", "ITC.NS", "SBIN.NS", "LT.NS", "KOTAKBANK.NS",
  "HCLTECH.NS", "AXISBANK.NS", "BAJFINANCE.NS", "MARUTI.NS", "SUNPHARMA.NS",
  "TATAMOTORS.NS", "WIPRO.NS", "ULTRACEMCO.NS", "ADANIENT.NS", "TITAN.NS",
  "ASIANPAINT.NS", "HINDUNILVR.NS", "TATASTEEL.NS", "NESTLEIND.NS", "ONGC.NS",
  "POWERGRID.NS", "HDFC.NS", "COALINDIA.NS", "NTPC.NS", "BAJAJFINSV.NS",
  "DRREDDY.NS", "TECHM.NS", "JSWSTEEL.NS", "M&M.NS", "TATACONSUM.NS",
  "INDUSINDBK.NS", "CIPLA.NS", "GRASIM.NS", "BPCL.NS", "EICHERMOT.NS",
  "HINDALCO.NS", "HEROMOTOCO.NS", "BRITANNIA.NS", "DIVISLAB.NS", "APOLLOHOSP.NS",
  "TRENT.NS", "ADANIPORTS.NS", "SHRIRAMFIN.NS",
];

// Top 50 US tickers
const US_TICKERS = [
  "AAPL", "MSFT", "GOOGL", "AMZN", "NVDA", "META", "TSLA", "BRK-B",
  "LLY", "AVGO", "JPM", "V", "UNH", "WMT", "XOM", "MA", "PG", "JNJ",
  "HD", "COST", "MRK", "ABBV", "ORCL", "CRM", "BAC", "AMD", "NFLX",
  "ADBE", "CVX", "KO", "PEP", "CSCO", "TMO", "ABT", "ACN", "MCD", "INTC",
  "WFC", "CAT", "VZ", "TXN", "QCOM", "MS", "RTX", "NEE", "AMGN", "UPS", "IBM",
];

const SECTORS = [
  "banking", "it", "pharma", "auto", "energy", "fmcg", "metals",
  "telecom", "infrastructure", "financial-services", "cement", "chemicals",
  "consumer-durables", "real-estate", "media",
];

export default function sitemap(): MetadataRoute.Sitemap {
  const now = new Date();

  const corePages: MetadataRoute.Sitemap = [
    { url: SITE_URL, lastModified: now, changeFrequency: "weekly", priority: 1.0 },
    { url: `${SITE_URL}/pricing`, lastModified: now, changeFrequency: "monthly", priority: 0.9 },
    { url: `${SITE_URL}/methodology`, lastModified: now, changeFrequency: "monthly", priority: 0.8 },
    { url: `${SITE_URL}/screener`, lastModified: now, changeFrequency: "weekly", priority: 0.8 },
    { url: `${SITE_URL}/compare`, lastModified: now, changeFrequency: "weekly", priority: 0.7 },
    { url: `${SITE_URL}/sources`, lastModified: now, changeFrequency: "monthly", priority: 0.5 },
    { url: `${SITE_URL}/login`, lastModified: now, changeFrequency: "yearly", priority: 0.4 },
    { url: `${SITE_URL}/signup`, lastModified: now, changeFrequency: "yearly", priority: 0.5 },
    { url: `${SITE_URL}/privacy`, lastModified: now, changeFrequency: "yearly", priority: 0.2 },
    { url: `${SITE_URL}/terms`, lastModified: now, changeFrequency: "yearly", priority: 0.2 },
  ];

  const stockPages: MetadataRoute.Sitemap = [
    ...NSE_TICKERS.map((t) => ({
      url: `${SITE_URL}/stocks/${t}`,
      lastModified: now,
      changeFrequency: "daily" as const,
      priority: 0.8,
    })),
    ...US_TICKERS.map((t) => ({
      url: `${SITE_URL}/stocks/${t}`,
      lastModified: now,
      changeFrequency: "daily" as const,
      priority: 0.7,
    })),
  ];

  const sectorPages: MetadataRoute.Sitemap = SECTORS.map((s) => ({
    url: `${SITE_URL}/best-stocks/${s}`,
    lastModified: now,
    changeFrequency: "weekly" as const,
    priority: 0.6,
  }));

  return [...corePages, ...stockPages, ...sectorPages];
}
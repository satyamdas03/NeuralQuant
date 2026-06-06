import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Stock Screener — NeuralQuant",
  description:
    "AI-powered stock screener with 5-factor quant filtering, regime detection, and sector peer comparisons for US and India markets.",
  openGraph: {
    title: "AI Stock Screener — 5-Factor Quant Filtering | NeuralQuant",
    description:
      "Screen stocks by quality, momentum, value, low-vol, and insider factors. Regime-aware filtering for S&P 500 and NIFTY 500.",
    url: "https://neuralquant.co/screener",
    siteName: "NeuralQuant",
    images: [
      {
        url: "/og-image.png",
        width: 1200,
        height: 630,
        alt: "NeuralQuant Stock Screener",
      },
    ],
    type: "website",
  },
  twitter: {
    card: "summary_large_image",
    title: "AI Stock Screener — 5-Factor Quant Filtering | NeuralQuant",
    description:
      "Screen stocks by quality, momentum, value, low-vol, and insider factors. Regime-aware filtering for S&P 500 and NIFTY 500.",
    creator: "@neuralquant",
    site: "@neuralquant",
  },
  alternates: {
    canonical: "https://neuralquant.co/screener",
  },
};

export default function ScreenerLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return <>{children}</>;
}

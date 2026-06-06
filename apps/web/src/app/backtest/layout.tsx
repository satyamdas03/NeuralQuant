import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Backtest — NeuralQuant",
  description:
    "Backtest quant strategies with historical data. Q1FY27 results: all pools beat NIFTY50, 87%+ hit rate. Simulate factor portfolios and momentum rotations.",
  openGraph: {
    title: "Backtest Engine — Quant Strategy Results | NeuralQuant",
    description:
      "Backtest quant strategies with historical data. Q1FY27: all pools beat NIFTY50, 87%+ hit rate. Factor portfolios and momentum rotations.",
    url: "https://neuralquant.co/backtest",
    siteName: "NeuralQuant",
    images: [
      {
        url: "/og-image.png",
        width: 1200,
        height: 630,
        alt: "NeuralQuant Backtest Engine",
      },
    ],
    type: "website",
  },
  twitter: {
    card: "summary_large_image",
    title: "Backtest Engine — Quant Strategy Results | NeuralQuant",
    description:
      "Backtest quant strategies with historical data. Q1FY27: all pools beat NIFTY50, 87%+ hit rate.",
    creator: "@neuralquant",
    site: "@neuralquant",
  },
  alternates: {
    canonical: "https://neuralquant.co/backtest",
  },
};

export default function BacktestLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return <>{children}</>;
}

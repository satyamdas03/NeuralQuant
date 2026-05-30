import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Data Sources — NeuralQuant",
  description: "Full transparency on NeuralQuant data sources: Finnhub, FMP, OpenBB, yfinance, and FRED. Coverage, latency, and refresh schedules.",
  openGraph: {
    title: "Data Sources — NeuralQuant",
    description: "Full transparency on NeuralQuant data sources: Finnhub, FMP, OpenBB, yfinance, and FRED. Coverage, latency, and refresh schedules.",
    url: "https://neuralquant.co/sources",
    siteName: "NeuralQuant",
    images: ["/og-image.png"],
    type: "website",
  },
  twitter: {
    card: "summary_large_image",
    title: "Data Sources — NeuralQuant",
    description: "Full transparency on NeuralQuant data sources: Finnhub, FMP, OpenBB, yfinance, and FRED. Coverage, latency, and refresh schedules.",
  },
  alternates: {
    canonical: "https://neuralquant.co/sources",
  },
};

export default function SourcesLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return <>{children}</>;
}

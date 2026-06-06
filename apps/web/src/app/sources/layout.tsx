import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Data Sources — NeuralQuant",
  description:
    "Full transparency on NeuralQuant data sources: Finnhub, FMP Premium, OpenBB, yfinance, and FRED. Coverage, latency, and refresh schedules.",
  openGraph: {
    title: "Data Sources — Full Transparency | NeuralQuant",
    description:
      "Full transparency on NeuralQuant data sources: Finnhub, FMP Premium, OpenBB, yfinance, and FRED. Coverage, latency, and refresh schedules.",
    url: "https://neuralquant.co/sources",
    siteName: "NeuralQuant",
    images: [
      {
        url: "/og-image.png",
        width: 1200,
        height: 630,
        alt: "NeuralQuant Data Sources",
      },
    ],
    type: "website",
  },
  twitter: {
    card: "summary_large_image",
    title: "Data Sources — Full Transparency | NeuralQuant",
    description:
      "Full transparency on NeuralQuant data sources: Finnhub, FMP Premium, OpenBB, yfinance, and FRED.",
    creator: "@neuralquant",
    site: "@neuralquant",
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

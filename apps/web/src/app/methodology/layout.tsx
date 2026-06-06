import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Methodology — NeuralQuant",
  description:
    "How the QuantFactor Engine selects stocks. IRS% scoring explained, Q1FY27 backtest results (87%+ hit rate), and SEBI-compliant methodology transparency.",
  openGraph: {
    title: "Methodology — IRS% Scoring & Backtest Results | NeuralQuant",
    description:
      "How the QuantFactor Engine selects stocks. IRS% scoring, Q1FY27 backtest (87%+ hit rate), and SEBI-compliant methodology.",
    url: "https://neuralquant.co/methodology",
    siteName: "NeuralQuant",
    images: [
      {
        url: "/og-image.png",
        width: 1200,
        height: 630,
        alt: "NeuralQuant Methodology — IRS% Scoring",
      },
    ],
    type: "website",
  },
  twitter: {
    card: "summary_large_image",
    title: "Methodology — IRS% Scoring & Backtest Results | NeuralQuant",
    description:
      "How the QuantFactor Engine selects stocks. IRS% scoring, Q1FY27 backtest (87%+ hit rate), and SEBI-compliant methodology.",
    creator: "@neuralquant",
    site: "@neuralquant",
  },
  alternates: {
    canonical: "https://neuralquant.co/methodology",
  },
};

export default function MethodologyLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return <>{children}</>;
}

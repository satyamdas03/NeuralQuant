import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Backtest Engine — NeuralQuant",
  description: "Backtest your quant strategies with historical data. Simulate factor-based portfolios, momentum, and value rotations.",
  openGraph: {
    title: "Backtest Engine — NeuralQuant",
    description: "Backtest your quant strategies with historical data. Simulate factor-based portfolios, momentum, and value rotations.",
    url: "https://neuralquant.co/backtest",
    siteName: "NeuralQuant",
    images: ["/og-image.png"],
    type: "website",
  },
  twitter: {
    card: "summary_large_image",
    title: "Backtest Engine — NeuralQuant",
    description: "Backtest your quant strategies with historical data. Simulate factor-based portfolios, momentum, and value rotations.",
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

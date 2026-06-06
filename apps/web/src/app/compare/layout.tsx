import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Compare Stocks — NeuralQuant",
  description:
    "Side-by-side stock comparison with 5-factor IRS% scores, valuation metrics, technical indicators, and peer benchmarking for US and India markets.",
  openGraph: {
    title: "Compare Stocks — Side-by-Side AI Analysis | NeuralQuant",
    description:
      "Side-by-side stock comparison with 5-factor IRS% scores, valuation metrics, technical indicators, and peer benchmarking.",
    url: "https://neuralquant.co/compare",
    siteName: "NeuralQuant",
    images: [
      {
        url: "/og-image.png",
        width: 1200,
        height: 630,
        alt: "NeuralQuant Stock Comparison",
      },
    ],
    type: "website",
  },
  twitter: {
    card: "summary_large_image",
    title: "Compare Stocks — Side-by-Side AI Analysis | NeuralQuant",
    description:
      "Side-by-side stock comparison with 5-factor IRS% scores, valuation metrics, and peer benchmarking.",
    creator: "@neuralquant",
    site: "@neuralquant",
  },
  alternates: {
    canonical: "https://neuralquant.co/compare",
  },
};

export default function CompareLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return <>{children}</>;
}

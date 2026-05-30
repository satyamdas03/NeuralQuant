import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Compare Stocks — NeuralQuant",
  description: "Side-by-side stock comparison with 5-factor scores, valuation metrics, technical indicators, and peer benchmarking.",
  openGraph: {
    title: "Compare Stocks — NeuralQuant",
    description: "Side-by-side stock comparison with 5-factor scores, valuation metrics, technical indicators, and peer benchmarking.",
    url: "https://neuralquant.co/compare",
    siteName: "NeuralQuant",
    images: ["/og-image.png"],
    type: "website",
  },
  twitter: {
    card: "summary_large_image",
    title: "Compare Stocks — NeuralQuant",
    description: "Side-by-side stock comparison with 5-factor scores, valuation metrics, technical indicators, and peer benchmarking.",
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

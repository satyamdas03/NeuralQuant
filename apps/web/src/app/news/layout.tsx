import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Market News — NeuralQuant",
  description: "Real-time market news, sentiment analysis, and insider cluster detection powered by Finnhub and AI summarization.",
  openGraph: {
    title: "Market News — NeuralQuant",
    description: "Real-time market news, sentiment analysis, and insider cluster detection powered by Finnhub and AI summarization.",
    url: "https://neuralquant.co/news",
    siteName: "NeuralQuant",
    images: ["/og-image.png"],
    type: "website",
  },
  twitter: {
    card: "summary_large_image",
    title: "Market News — NeuralQuant",
    description: "Real-time market news, sentiment analysis, and insider cluster detection powered by Finnhub and AI summarization.",
  },
  alternates: {
    canonical: "https://neuralquant.co/news",
  },
};

export default function NewsLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return <>{children}</>;
}

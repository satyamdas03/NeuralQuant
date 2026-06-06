import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Market News — NeuralQuant",
  description:
    "Real-time market news, sentiment analysis, and insider cluster detection powered by Finnhub and AI summarization.",
  openGraph: {
    title: "Market News — AI Sentiment & Insider Tracking | NeuralQuant",
    description:
      "Real-time market news, sentiment analysis, and insider cluster detection powered by AI.",
    url: "https://neuralquant.co/news",
    siteName: "NeuralQuant",
    images: [
      {
        url: "/og-image.png",
        width: 1200,
        height: 630,
        alt: "NeuralQuant Market News",
      },
    ],
    type: "website",
  },
  twitter: {
    card: "summary_large_image",
    title: "Market News — AI Sentiment & Insider Tracking | NeuralQuant",
    description:
      "Real-time market news, sentiment analysis, and insider cluster detection powered by AI.",
    creator: "@neuralquant",
    site: "@neuralquant",
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

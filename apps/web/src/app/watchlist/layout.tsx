import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Watchlists — NeuralQuant",
  description:
    "Manage your stock watchlists with AI scores, live prices, insider sentiment, and technical indicators.",
  openGraph: {
    title: "Watchlists — AI-Powered Tracking | NeuralQuant",
    description:
      "Manage stock watchlists with AI scores, live prices, insider sentiment, and technical indicators.",
    url: "https://neuralquant.co/watchlist",
    siteName: "NeuralQuant",
    images: [
      {
        url: "/og-image.png",
        width: 1200,
        height: 630,
        alt: "NeuralQuant Watchlists",
      },
    ],
    type: "website",
  },
  twitter: {
    card: "summary_large_image",
    title: "Watchlists — AI-Powered Tracking | NeuralQuant",
    description:
      "Manage stock watchlists with AI scores, live prices, insider sentiment, and technical indicators.",
    creator: "@neuralquant",
    site: "@neuralquant",
  },
  alternates: {
    canonical: "https://neuralquant.co/watchlist",
  },
};

export default function WatchlistLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return <>{children}</>;
}

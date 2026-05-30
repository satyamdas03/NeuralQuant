import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Watchlists — NeuralQuant",
  description: "Manage your stock watchlists with AI scores, live prices, insider sentiment, and technical indicators.",
  openGraph: {
    title: "Watchlists — NeuralQuant",
    description: "Manage your stock watchlists with AI scores, live prices, insider sentiment, and technical indicators.",
    url: "https://neuralquant.co/watchlist",
    siteName: "NeuralQuant",
    images: ["/og-image.png"],
    type: "website",
  },
  twitter: {
    card: "summary_large_image",
    title: "Watchlists — NeuralQuant",
    description: "Manage your stock watchlists with AI scores, live prices, insider sentiment, and technical indicators.",
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

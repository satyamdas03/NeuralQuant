import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Trade Desk — NeuralQuant",
  description: "AI-assisted trade desk with real-time signals, risk checks, and portfolio rebalancing recommendations.",
  openGraph: {
    title: "Trade Desk — NeuralQuant",
    description: "AI-assisted trade desk with real-time signals, risk checks, and portfolio rebalancing recommendations.",
    url: "https://neuralquant.co/trade",
    siteName: "NeuralQuant",
    images: ["/og-image.png"],
    type: "website",
  },
  twitter: {
    card: "summary_large_image",
    title: "Trade Desk — NeuralQuant",
    description: "AI-assisted trade desk with real-time signals, risk checks, and portfolio rebalancing recommendations.",
  },
  alternates: {
    canonical: "https://neuralquant.co/trade",
  },
};

export default function TradeLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return <>{children}</>;
}

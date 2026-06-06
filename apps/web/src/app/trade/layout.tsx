import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Trade Desk — NeuralQuant",
  description:
    "AI-assisted trade desk with real-time signals, risk checks, and portfolio rebalancing recommendations.",
  openGraph: {
    title: "Trade Desk — AI-Assisted Signals | NeuralQuant",
    description:
      "AI-assisted trade desk with real-time signals, risk checks, and portfolio rebalancing recommendations.",
    url: "https://neuralquant.co/trade",
    siteName: "NeuralQuant",
    images: [
      {
        url: "/og-image.png",
        width: 1200,
        height: 630,
        alt: "NeuralQuant Trade Desk",
      },
    ],
    type: "website",
  },
  twitter: {
    card: "summary_large_image",
    title: "Trade Desk — AI-Assisted Signals | NeuralQuant",
    description:
      "AI-assisted trade desk with real-time signals, risk checks, and portfolio rebalancing.",
    creator: "@neuralquant",
    site: "@neuralquant",
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

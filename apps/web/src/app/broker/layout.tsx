import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Broker Integration — NeuralQuant",
  description:
    "Connect your brokerage account for seamless portfolio sync, trade execution, and performance tracking.",
  openGraph: {
    title: "Broker Integration — Seamless Portfolio Sync | NeuralQuant",
    description:
      "Connect your brokerage account for seamless portfolio sync, trade execution, and performance tracking.",
    url: "https://neuralquant.co/broker",
    siteName: "NeuralQuant",
    images: [
      {
        url: "/og-image.png",
        width: 1200,
        height: 630,
        alt: "NeuralQuant Broker Integration",
      },
    ],
    type: "website",
  },
  twitter: {
    card: "summary_large_image",
    title: "Broker Integration — Seamless Portfolio Sync | NeuralQuant",
    description:
      "Connect your brokerage for seamless portfolio sync, trade execution, and performance tracking.",
    creator: "@neuralquant",
    site: "@neuralquant",
  },
  alternates: {
    canonical: "https://neuralquant.co/broker",
  },
};

export default function BrokerLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return <>{children}</>;
}

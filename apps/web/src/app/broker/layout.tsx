import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Broker Integration — NeuralQuant",
  description: "Connect your brokerage account for seamless portfolio sync, trade execution, and performance tracking.",
  openGraph: {
    title: "Broker Integration — NeuralQuant",
    description: "Connect your brokerage account for seamless portfolio sync, trade execution, and performance tracking.",
    url: "https://neuralquant.co/broker",
    siteName: "NeuralQuant",
    images: ["/og-image.png"],
    type: "website",
  },
  twitter: {
    card: "summary_large_image",
    title: "Broker Integration — NeuralQuant",
    description: "Connect your brokerage account for seamless portfolio sync, trade execution, and performance tracking.",
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

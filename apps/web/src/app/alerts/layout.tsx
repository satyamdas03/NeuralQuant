import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Price Alerts — NeuralQuant",
  description: "Set and manage stock price alerts, score change notifications, and regime shift warnings for your watchlist.",
  openGraph: {
    title: "Price Alerts — NeuralQuant",
    description: "Set and manage stock price alerts, score change notifications, and regime shift warnings for your watchlist.",
    url: "https://neuralquant.co/alerts",
    siteName: "NeuralQuant",
    images: ["/og-image.png"],
    type: "website",
  },
  twitter: {
    card: "summary_large_image",
    title: "Price Alerts — NeuralQuant",
    description: "Set and manage stock price alerts, score change notifications, and regime shift warnings for your watchlist.",
  },
  alternates: {
    canonical: "https://neuralquant.co/alerts",
  },
};

export default function AlertsLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return <>{children}</>;
}

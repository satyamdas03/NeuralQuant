import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Price Alerts — NeuralQuant",
  description:
    "Set and manage stock price alerts, score change notifications, and regime shift warnings for your watchlist.",
  openGraph: {
    title: "Price Alerts — Smart Notifications | NeuralQuant",
    description:
      "Set and manage stock price alerts, score change notifications, and regime shift warnings for your watchlist.",
    url: "https://neuralquant.co/alerts",
    siteName: "NeuralQuant",
    images: [
      {
        url: "/og-image.png",
        width: 1200,
        height: 630,
        alt: "NeuralQuant Price Alerts",
      },
    ],
    type: "website",
  },
  twitter: {
    card: "summary_large_image",
    title: "Price Alerts — Smart Notifications | NeuralQuant",
    description:
      "Set and manage stock price alerts, score change notifications, and regime shift warnings.",
    creator: "@neuralquant",
    site: "@neuralquant",
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

import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Ask Morgan — NeuralQuant",
  description: "Ask Morgan anything about stocks, sectors, or macro. Senior equity research analyst with institutional-grade analysis, live data, and source citations.",
  openGraph: {
    title: "Ask Morgan — NeuralQuant",
    description: "Ask Morgan anything about stocks, sectors, or macro. Senior equity research analyst with institutional-grade analysis, live data, and source citations.",
    url: "https://neuralquant.co/query",
    siteName: "NeuralQuant",
    images: ["/og-image.png"],
    type: "website",
  },
  twitter: {
    card: "summary_large_image",
    title: "Ask Morgan — NeuralQuant",
    description: "Ask Morgan anything about stocks, sectors, or macro. Senior equity research analyst with institutional-grade analysis, live data, and source citations.",
  },
  alternates: {
    canonical: "https://neuralquant.co/query",
  },
};

export default function QueryLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return <>{children}</>;
}

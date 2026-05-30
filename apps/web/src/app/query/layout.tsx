import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Ask AI — NeuralQuant",
  description: "Ask AI anything about stocks, sectors, or macro. Multi-agent PARA-DEBATE with conversation memory, live data, and source citations.",
  openGraph: {
    title: "Ask AI — NeuralQuant",
    description: "Ask AI anything about stocks, sectors, or macro. Multi-agent PARA-DEBATE with conversation memory, live data, and source citations.",
    url: "https://neuralquant.co/query",
    siteName: "NeuralQuant",
    images: ["/og-image.png"],
    type: "website",
  },
  twitter: {
    card: "summary_large_image",
    title: "Ask AI — NeuralQuant",
    description: "Ask AI anything about stocks, sectors, or macro. Multi-agent PARA-DEBATE with conversation memory, live data, and source citations.",
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

import type { Metadata } from "next";
import LandingPage from "@/components/landing/LandingPage";

export const metadata: Metadata = {
  title: "NeuralQuant — AI Stock Intelligence",
  description:
    "Institutional-grade AI stock analysis for US and India markets. ForeCast Score, PARA-DEBATE multi-agent analysis, and regime detection. Free during development.",
  openGraph: {
    title: "NeuralQuant — AI Stock Intelligence",
    description:
      "Institutional-grade AI stock analysis for US and India markets. ForeCast Score, PARA-DEBATE multi-agent analysis, and regime detection.",
    url: "https://neuralquant.co",
    siteName: "NeuralQuant",
    images: ["/og-image.png"],
    type: "website",
  },
  twitter: {
    card: "summary_large_image",
    title: "NeuralQuant — AI Stock Intelligence",
    description:
      "Institutional-grade AI stock analysis for US and India markets. ForeCast Score, PARA-DEBATE multi-agent analysis, and regime detection.",
  },
  alternates: {
    canonical: "https://neuralquant.co",
  },
};

export default function Home() {
  return <LandingPage />;
}

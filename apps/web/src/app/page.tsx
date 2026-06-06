import type { Metadata } from "next";
import LandingPage from "@/components/landing/LandingPage";

export const metadata: Metadata = {
  title: "NeuralQuant — AI Stock Intelligence for US & India Markets",
  description:
    "Beat the market with IRS% scoring and 7-agent PARA-DEBATE analysis. Institutional-grade AI for stocks — 87%+ hit rate in Q1FY27 backtest. Free tier available.",
  openGraph: {
    title: "NeuralQuant — AI Stock Intelligence for US & India Markets",
    description:
      "Beat the market with IRS% scoring and 7-agent PARA-DEBATE analysis. 87%+ hit rate in Q1FY27 backtest. Free tier available.",
    url: "https://neuralquant.co",
    siteName: "NeuralQuant",
    images: [
      {
        url: "/og-image.png",
        width: 1200,
        height: 630,
        alt: "NeuralQuant — AI Stock Intelligence",
      },
    ],
    type: "website",
    locale: "en_US",
  },
  twitter: {
    card: "summary_large_image",
    title: "NeuralQuant — AI Stock Intelligence for US & India Markets",
    description:
      "Beat the market with IRS% scoring and 7-agent PARA-DEBATE analysis. 87%+ hit rate in Q1FY27 backtest. Free tier available.",
    images: ["/og-image.png"],
    creator: "@neuralquant",
    site: "@neuralquant",
  },
  alternates: {
    canonical: "https://neuralquant.co",
  },
};

export default function Home() {
  return <LandingPage />;
}

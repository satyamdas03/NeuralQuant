import type { Metadata } from "next";
import LandingPage from "@/components/landing/LandingPage";

export const metadata: Metadata = {
  title: "NeuralQuant — AI Stock Intelligence for US & India Markets",
  description:
    "Research tools for US and India stocks: IRS% factor scoring and multi-agent PARA-DEBATE analysis. Information only, not investment advice.",
  openGraph: {
    title: "NeuralQuant — AI Stock Intelligence for US & India Markets",
    description:
      "Research tools for US and India stocks: IRS% factor scoring and multi-agent PARA-DEBATE analysis. Information only, not investment advice.",
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
      "Research tools for US and India stocks: IRS% factor scoring and multi-agent PARA-DEBATE analysis. Information only, not investment advice.",
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

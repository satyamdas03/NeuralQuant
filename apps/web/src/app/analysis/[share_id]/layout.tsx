import { Metadata } from "next";

type Props = { params: Promise<{ share_id: string }> };

export async function generateMetadata({ params }: Props): Promise<Metadata> {
  const { share_id } = await params;
  const baseUrl = process.env.NEXT_PUBLIC_SITE_URL || "https://neuralquant.co";
  const ogImageUrl = `${baseUrl}/api/og/analysis/${share_id}`;

  return {
    title: "Stock Analysis | NeuralQuant",
    description: "View a shared AI-powered PARA-DEBATE stock analysis on NeuralQuant.",
    openGraph: {
      title: "NeuralQuant AI Stock Analysis",
      description: "7-Agent PARA-DEBATE • Institutional-Grade Research",
      type: "article",
      siteName: "NeuralQuant",
      images: [{ url: ogImageUrl, width: 1200, height: 630, alt: "NeuralQuant AI Stock Analysis" }],
    },
    twitter: {
      card: "summary_large_image",
      title: "NeuralQuant AI Stock Analysis",
      description: "7-Agent PARA-DEBATE • Institutional-Grade Research",
      images: [ogImageUrl],
    },
  };
}

export default function AnalysisLayout({ children }: { children: React.ReactNode }) {
  return children;
}
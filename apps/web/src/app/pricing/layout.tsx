import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Pricing — NeuralQuant",
  description: "NeuralQuant pricing plans: Free, Investor ($9/mo), and Pro ($29/mo). AI stock analysis, PARA-DEBATE, screener, and unlimited watchlists.",
  openGraph: {
    title: "Pricing — NeuralQuant",
    description: "NeuralQuant pricing plans: Free, Investor ($9/mo), and Pro ($29/mo). AI stock analysis, PARA-DEBATE, screener, and unlimited watchlists.",
    url: "https://neuralquant.co/pricing",
    siteName: "NeuralQuant",
    images: ["/og-image.png"],
    type: "website",
  },
  twitter: {
    card: "summary_large_image",
    title: "Pricing — NeuralQuant",
    description: "NeuralQuant pricing plans: Free, Investor ($9/mo), and Pro ($29/mo). AI stock analysis, PARA-DEBATE, screener, and unlimited watchlists.",
  },
  alternates: {
    canonical: "https://neuralquant.co/pricing",
  },
};

export default function PricingLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return <>{children}</>;
}

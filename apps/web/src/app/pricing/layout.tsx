import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Pricing — NeuralQuant",
  description:
    "NeuralQuant pricing — Free tier, Investor ($9.99/mo), and Pro ($29.99/mo). AI stock analysis, PARA-DEBATE, screener, and unlimited watchlists.",
  openGraph: {
    title: "Pricing — Free & Pro Plans | NeuralQuant",
    description:
      "Start free, upgrade when ready. Investor $9.99/mo, Pro $29.99/mo. AI stock analysis, 7-agent PARA-DEBATE, and unlimited watchlists.",
    url: "https://neuralquant.co/pricing",
    siteName: "NeuralQuant",
    images: [
      {
        url: "/og-image.png",
        width: 1200,
        height: 630,
        alt: "NeuralQuant Pricing Plans",
      },
    ],
    type: "website",
  },
  twitter: {
    card: "summary_large_image",
    title: "Pricing — Free & Pro Plans | NeuralQuant",
    description:
      "Start free, upgrade when ready. Investor $9.99/mo, Pro $29.99/mo. AI stock analysis, 7-agent PARA-DEBATE, and unlimited watchlists.",
    creator: "@neuralquant",
    site: "@neuralquant",
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

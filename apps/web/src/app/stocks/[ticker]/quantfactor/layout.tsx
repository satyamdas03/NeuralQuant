import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "QuantFactor Analysis — NeuralQuant",
  description:
    "Investment Readiness Score breakdown with G Score, Risk Efficiency, and quintile analysis. Deep-dive into stock quality, momentum, and valuation.",
  openGraph: {
    title: "QuantFactor Analysis — NeuralQuant",
    description:
      "Investment Readiness Score breakdown with G Score, Risk Efficiency, and quintile analysis.",
    siteName: "NeuralQuant",
    images: ["/og-image.png"],
    type: "website",
  },
  twitter: {
    card: "summary_large_image",
    title: "QuantFactor Analysis — NeuralQuant",
    description:
      "Investment Readiness Score breakdown with G Score, Risk Efficiency, and quintile analysis.",
  },
};

export default function QuantFactorLayout({ children }: { children: React.ReactNode }) {
  return <>{children}</>;
}
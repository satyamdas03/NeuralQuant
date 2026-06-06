import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Portfolio — NeuralQuant",
  description:
    "AI-powered portfolio intelligence with IRS%, sell signals, and geopolitical risk scanning for US and India markets.",
  openGraph: {
    title: "Portfolio — NeuralQuant",
    description:
      "AI-powered portfolio intelligence with IRS%, sell signals, and geopolitical risk scanning for US and India markets.",
    url: "https://neuralquant.co/portfolio",
    siteName: "NeuralQuant",
    images: ["/og-image.png"],
    type: "website",
  },
  twitter: {
    card: "summary_large_image",
    title: "Portfolio — NeuralQuant",
    description:
      "AI-powered portfolio intelligence with IRS%, sell signals, and geopolitical risk scanning for US and India markets.",
  },
  alternates: {
    canonical: "https://neuralquant.co/portfolio",
  },
};

export default function PortfolioLayout({ children }: { children: React.ReactNode }) {
  return <>{children}</>;
}
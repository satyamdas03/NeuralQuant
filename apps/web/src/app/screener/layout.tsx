import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Stock Screener — NeuralQuant",
  description: "AI-powered stock screener with 5-factor quant filtering, regime detection, and sector peer comparisons for US and India markets.",
  openGraph: {
    title: "Stock Screener — NeuralQuant",
    description: "AI-powered stock screener with 5-factor quant filtering, regime detection, and sector peer comparisons for US and India markets.",
    url: "https://neuralquant.co/screener",
    siteName: "NeuralQuant",
    images: ["/og-image.png"],
    type: "website",
  },
  twitter: {
    card: "summary_large_image",
    title: "Stock Screener — NeuralQuant",
    description: "AI-powered stock screener with 5-factor quant filtering, regime detection, and sector peer comparisons for US and India markets.",
  },
  alternates: {
    canonical: "https://neuralquant.co/screener",
  },
};

export default function ScreenerLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return <>{children}</>;
}

import type { Metadata } from "next";

export async function generateMetadata({
  params,
}: {
  params: Promise<{ ticker: string }>;
}): Promise<Metadata> {
  const { ticker } = await params;
  const decoded = decodeURIComponent(ticker);
  const isIndia = decoded.endsWith(".NS") || decoded.endsWith(".BO");
  const name = decoded.replace(/\.NS$|\.BO$/, "");
  const market = isIndia ? "India (NSE/BSE)" : "US (NYSE/NASDAQ)";
  const currency = isIndia ? "₹" : "$";

  return {
    title: `${name} Stock Score — NeuralQuant 5-Factor AI Analysis | ${market}`,
    description: `AI-powered ${name} stock analysis with 5-factor quant scoring (quality, momentum, value, low-vol, insider), HMM regime detection, and multi-agent PARA-DEBATE. ${currency} price targets and sector-adjusted ratings.`,
    openGraph: {
      title: `${name} Stock Score — NeuralQuant`,
      description: `5-factor AI analysis + multi-agent debate for ${name}. Free stock intelligence.`,
      type: "website",
      url: `https://neuralquant.co/stocks/${ticker}`,
      siteName: "NeuralQuant",
      images: ["/og-image.png"],
    },
    twitter: {
      card: "summary_large_image",
      title: `${name} Stock Score — NeuralQuant`,
      description: `5-factor AI analysis + multi-agent debate for ${name}. Free stock intelligence.`,
    },
    alternates: {
      canonical: `https://neuralquant.co/stocks/${ticker}`,
    },
  };
}

export default function StockLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return <>{children}</>;
}
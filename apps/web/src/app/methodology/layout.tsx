import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Methodology — NeuralQuant",
  description:
    "How the Anjali Value Engine selects stocks. Institutional-grade quantitative research, made transparent. IRS% scoring, Q1FY27 backtest results, and SEBI-compliant disclaimers.",
  openGraph: {
    title: "Methodology — NeuralQuant",
    description:
      "How the Anjali Value Engine selects stocks. Institutional-grade quantitative research, made transparent. IRS% scoring, Q1FY27 backtest results, and SEBI-compliant disclaimers.",
    url: "https://neuralquant.co/methodology",
    siteName: "NeuralQuant",
    images: ["/og-image.png"],
    type: "website",
  },
  twitter: {
    card: "summary_large_image",
    title: "Methodology — NeuralQuant",
    description:
      "How the Anjali Value Engine selects stocks. Institutional-grade quantitative research, made transparent. IRS% scoring, Q1FY27 backtest results, and SEBI-compliant disclaimers.",
  },
  alternates: {
    canonical: "https://neuralquant.co/methodology",
  },
};

export default function MethodologyLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return <>{children}</>;
}

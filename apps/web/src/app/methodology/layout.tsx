import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Methodology — NeuralQuant",
  description:
    "How the QuantFactor Engine works: IRS% scoring, data sources, and known limitations of the research process.",
  openGraph: {
    title: "Methodology — IRS% Scoring | NeuralQuant",
    description:
      "How the QuantFactor Engine works: IRS% scoring, data sources, and known limitations of the research process.",
    url: "https://neuralquant.co/methodology",
    siteName: "NeuralQuant",
    images: [
      {
        url: "/og-image.png",
        width: 1200,
        height: 630,
        alt: "NeuralQuant Methodology — IRS% Scoring",
      },
    ],
    type: "website",
  },
  twitter: {
    card: "summary_large_image",
    title: "Methodology — IRS% Scoring | NeuralQuant",
    description:
      "How the QuantFactor Engine works: IRS% scoring, data sources, and known limitations of the research process.",
    creator: "@neuralquant",
    site: "@neuralquant",
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

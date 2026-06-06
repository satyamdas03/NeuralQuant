import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Data Terminal — NeuralQuant",
  description:
    "Professional-grade data terminal with OpenBB integration. Access macro indicators, economic data, and institutional datasets.",
  openGraph: {
    title: "Data Terminal — OpenBB Integration | NeuralQuant",
    description:
      "Professional-grade data terminal with OpenBB integration. Access macro indicators, economic data, and institutional datasets.",
    url: "https://neuralquant.co/terminal",
    siteName: "NeuralQuant",
    images: [
      {
        url: "/og-image.png",
        width: 1200,
        height: 630,
        alt: "NeuralQuant Data Terminal",
      },
    ],
    type: "website",
  },
  twitter: {
    card: "summary_large_image",
    title: "Data Terminal — OpenBB Integration | NeuralQuant",
    description:
      "Professional-grade data terminal with OpenBB integration. Access macro indicators and institutional datasets.",
    creator: "@neuralquant",
    site: "@neuralquant",
  },
  alternates: {
    canonical: "https://neuralquant.co/terminal",
  },
};

export default function TerminalLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return <>{children}</>;
}

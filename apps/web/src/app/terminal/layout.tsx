import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Data Terminal — NeuralQuant",
  description: "Professional-grade data terminal with OpenBB integration. Access macro indicators, economic data, and institutional datasets.",
  openGraph: {
    title: "Data Terminal — NeuralQuant",
    description: "Professional-grade data terminal with OpenBB integration. Access macro indicators, economic data, and institutional datasets.",
    url: "https://neuralquant.co/terminal",
    siteName: "NeuralQuant",
    images: ["/og-image.png"],
    type: "website",
  },
  twitter: {
    card: "summary_large_image",
    title: "Data Terminal — NeuralQuant",
    description: "Professional-grade data terminal with OpenBB integration. Access macro indicators, economic data, and institutional datasets.",
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

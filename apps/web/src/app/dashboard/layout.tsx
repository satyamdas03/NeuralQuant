import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Dashboard — NeuralQuant",
  description:
    "Live markets dashboard with AI stock scores, portfolio overview, top movers, and sector performance for S&P 500 and NIFTY 500.",
  openGraph: {
    title: "Markets Dashboard — Live AI Scores | NeuralQuant",
    description:
      "Live markets dashboard with AI stock scores, portfolio overview, top movers, and sector performance for S&P 500 and NIFTY 500.",
    url: "https://neuralquant.co/dashboard",
    siteName: "NeuralQuant",
    images: [
      {
        url: "/og-image.png",
        width: 1200,
        height: 630,
        alt: "NeuralQuant Markets Dashboard",
      },
    ],
    type: "website",
  },
  twitter: {
    card: "summary_large_image",
    title: "Markets Dashboard — Live AI Scores | NeuralQuant",
    description:
      "Live markets dashboard with AI stock scores, portfolio overview, top movers, and sector performance.",
    creator: "@neuralquant",
    site: "@neuralquant",
  },
  alternates: {
    canonical: "https://neuralquant.co/dashboard",
  },
};

export default function DashboardLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return <>{children}</>;
}

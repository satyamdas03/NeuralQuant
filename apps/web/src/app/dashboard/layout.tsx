import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Markets Dashboard — NeuralQuant",
  description: "Live markets dashboard with AI stock scores, portfolio overview, top movers, and sector performance for S&P 500 and NIFTY 500.",
  openGraph: {
    title: "Markets Dashboard — NeuralQuant",
    description: "Live markets dashboard with AI stock scores, portfolio overview, top movers, and sector performance for S&P 500 and NIFTY 500.",
    url: "https://neuralquant.co/dashboard",
    siteName: "NeuralQuant",
    images: ["/og-image.png"],
    type: "website",
  },
  twitter: {
    card: "summary_large_image",
    title: "Markets Dashboard — NeuralQuant",
    description: "Live markets dashboard with AI stock scores, portfolio overview, top movers, and sector performance for S&P 500 and NIFTY 500.",
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

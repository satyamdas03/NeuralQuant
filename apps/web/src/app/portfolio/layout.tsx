import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Portfolio — NeuralQuant",
  description: "AI-powered portfolio intelligence with IRS%, sell signals, and geopolitical risk scanning.",
};

export default function PortfolioLayout({ children }: { children: React.ReactNode }) {
  return <>{children}</>;
}
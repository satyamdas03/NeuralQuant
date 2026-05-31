import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Stock Analysis | NeuralQuant",
  description: "View a shared AI-powered PARA-DEBATE stock analysis on NeuralQuant.",
};

export default function AnalysisLayout({ children }: { children: React.ReactNode }) {
  return children;
}
import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Anjali Analysis — NeuralQuant",
  description: "Investment Readiness Score breakdown with G Score, Risk Efficiency, and quintile analysis.",
};

export default function AnjaliLayout({ children }: { children: React.ReactNode }) {
  return <>{children}</>;
}
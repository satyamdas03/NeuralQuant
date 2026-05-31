import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Analytics Dashboard | NeuralQuant",
  description: "Internal growth metrics and analytics dashboard",
};

export default function AnalyticsLayout({ children }: { children: React.ReactNode }) {
  return children;
}
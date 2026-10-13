import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Hermes Agent — Frozen | NeuralQuant",
  description:
    "The Hermes autonomous trading agent page is archived for internal reference. No live trading data is displayed.",
  robots: { index: false },
};

export default function HermesLayout({ children }: { children: React.ReactNode }) {
  return children;
}

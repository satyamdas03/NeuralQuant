import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Live Trading — Hermes Agent | QuantAlpha",
  description:
    "Watch QuantAlpha's autonomous trading agent live: real-time logs, trade tape, P&L, and a self-modifying strategy that has already rewritten itself dozens of times.",
};

export default function HermesLayout({ children }: { children: React.ReactNode }) {
  return children;
}

"use client";

import { useEffect, useRef, useState } from "react";
import Link from "next/link";
import AlphaCounterCard from "./AlphaCounterCard";
import EquityCurveChart from "./EquityCurveChart";
import QuarterlyBreakdownTable from "./QuarterlyBreakdownTable";
import SEBIDisclaimer from "./SEBIDisclaimer";

const METRICS = [
  { label: "Alpha", value: 13.5, suffix: "%", color: "positive" as const, subtext: "vs NIFTY50" },
  { label: "Hit Rate", value: 89, suffix: "%", color: "positive" as const, subtext: "selections beat benchmark" },
  { label: "Avg Return", value: 24.8, suffix: "%", color: "positive" as const, subtext: "unweighted average" },
  { label: "Nifty50", value: 11.3, suffix: "%", color: "neutral" as const, subtext: "same period benchmark" },
];

export default function BacktestResultsSection() {
  const sectionRef = useRef<HTMLElement>(null);
  const [isVisible, setIsVisible] = useState(false);

  useEffect(() => {
    const el = sectionRef.current;
    if (!el) return;

    const observer = new IntersectionObserver(
      ([entry]) => {
        if (entry.isIntersecting) {
          setIsVisible(true);
          observer.disconnect();
        }
      },
      { threshold: 0.15 }
    );

    observer.observe(el);
    return () => observer.disconnect();
  }, []);

  return (
    <section
      ref={sectionRef}
      className="relative w-full py-24 md:py-32 overflow-hidden"
      style={{ background: "var(--color-surface-deep)" }}
    >
      {/* Radial gradient glow behind chart area */}
      <div className="absolute top-1/3 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[800px] h-[600px] bg-primary-fixed/4 rounded-full blur-[140px] pointer-events-none" />

      <div className="relative z-10 max-w-[1400px] mx-auto px-4 lg:px-16">
        {/* Header */}
        <div className="text-center mb-14">
          <div
            className={`inline-flex items-center gap-2 border border-primary-fixed/30 bg-surface-container-low px-4 py-2 font-mono text-[11px] font-bold tracking-[0.2em] uppercase text-primary-fixed mb-6 transition-all duration-700 ${
              isVisible ? "opacity-100 translate-y-0" : "opacity-0 translate-y-4"
            }`}
          >
            <span className="w-2 h-2 rounded-full bg-primary-fixed animate-pulse" />
            Q1 FY2027 — Live Backtest Results
          </div>
          <h2
            className={`font-headline text-3xl md:text-5xl lg:text-6xl font-bold tracking-tight mb-4 transition-all duration-700 delay-100 ${
              isVisible ? "opacity-100 translate-y-0" : "opacity-0 translate-y-4"
            }`}
          >
            The Numbers Don&apos;t Lie
          </h2>
          <p
            className={`text-text-muted max-w-2xl mx-auto text-lg leading-relaxed transition-all duration-700 delay-200 ${
              isVisible ? "opacity-100 translate-y-0" : "opacity-0 translate-y-4"
            }`}
          >
            Every selection was scored by the Anjali Value Engine (IRS%) and
            tracked against NIFTY50 from April through June 2026. No hindsight.
            No cherry-picking.
          </p>
        </div>

        {/* Metric cards grid */}
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-4 mb-16">
          {METRICS.map((m, i) => (
            <div
              key={m.label}
              className={`transition-all duration-700 ${
                isVisible ? "opacity-100 translate-y-0" : "opacity-0 translate-y-6"
              }`}
              style={{ transitionDelay: `${300 + i * 100}ms` }}
            >
              <AlphaCounterCard
                label={m.label}
                value={m.value}
                suffix={m.suffix}
                color={m.color}
                animate={isVisible}
                subtext={m.subtext}
              />
            </div>
          ))}
        </div>

        {/* Equity curve chart */}
        <div
          className={`mb-16 transition-all duration-700 ${
            isVisible ? "opacity-100 translate-y-0" : "opacity-0 translate-y-6"
          }`}
          style={{ transitionDelay: "700ms" }}
        >
          <EquityCurveChart />
        </div>

        {/* Quarterly breakdown table */}
        <div
          className={`mb-16 transition-all duration-700 ${
            isVisible ? "opacity-100 translate-y-0" : "opacity-0 translate-y-6"
          }`}
          style={{ transitionDelay: "900ms" }}
        >
          <QuarterlyBreakdownTable />
        </div>

        {/* Methodology link */}
        <div
          className={`text-center mb-10 transition-all duration-700 ${
            isVisible ? "opacity-100 translate-y-0" : "opacity-0 translate-y-4"
          }`}
          style={{ transitionDelay: "1000ms" }}
        >
          <Link
            href="/methodology"
            className="inline-flex items-center gap-2 font-mono text-[11px] font-bold tracking-[0.2em] uppercase text-primary-fixed hover:text-primary-dim transition-colors"
          >
            Read the full methodology
            <span aria-hidden="true">→</span>
          </Link>
        </div>

        {/* SEBI Disclaimer */}
        <div
          className={`transition-all duration-700 ${
            isVisible ? "opacity-100 translate-y-0" : "opacity-0 translate-y-4"
          }`}
          style={{ transitionDelay: "1100ms" }}
        >
          <SEBIDisclaimer />
        </div>
      </div>
    </section>
  );
}

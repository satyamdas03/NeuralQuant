"use client";

import Link from "next/link";

export default function SEBIDisclaimer() {
  return (
    <div
      className="w-full border p-6 md:p-8"
      style={{
        background: "var(--color-surface-low)",
        borderColor: "var(--color-border-glow)",
      }}
    >
      <div className="flex items-start gap-4">
        {/* Warning icon */}
        <div className="flex-shrink-0 mt-0.5">
          <svg
            width="20"
            height="20"
            viewBox="0 0 24 24"
            fill="none"
            stroke="var(--color-tertiary-fixed)"
            strokeWidth="2"
            strokeLinecap="round"
            strokeLinejoin="round"
          >
            <path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z" />
            <line x1="12" y1="9" x2="12" y2="13" />
            <line x1="12" y1="17" x2="12.01" y2="17" />
          </svg>
        </div>

        <div className="flex-1">
          <h4 className="font-headline text-sm md:text-base font-bold text-tertiary-fixed mb-3">
            Regulatory Disclaimer
          </h4>

          <p className="font-mono text-[11px] md:text-xs text-text-muted leading-relaxed">
            Results shown are based on backtested quantitative selection using the QuantFactor Engine
            (IRS% scoring system) applied to Indian SmallCap 250 and MicroCap 250 universes for
            Q1 FY2027 (April–June 2026). Past performance does not guarantee future results.
            Backtested results are hypothetical and do not reflect actual trading. NeuralQuant is a
            research and analytics tool — it is not a SEBI-registered Investment Advisor, Portfolio
            Manager, or Research Analyst. Nothing on this page constitutes investment advice. Please
            consult a SEBI-registered financial advisor before making any investment decisions.
          </p>

          <div className="mt-4 flex flex-wrap items-center gap-4">
            <Link
              href="/methodology"
              className="inline-flex items-center gap-2 font-mono text-[11px] font-bold tracking-[0.15em] uppercase text-primary-fixed hover:text-primary-dim transition-colors"
            >
              View Methodology
              <span aria-hidden="true">→</span>
            </Link>
            <span className="font-mono text-[10px] text-text-muted">
              Last updated: June 2026
            </span>
          </div>
        </div>
      </div>
    </div>
  );
}

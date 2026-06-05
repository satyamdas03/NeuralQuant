"use client";

import { useEffect, useRef, useState } from "react";
import Link from "next/link";
import {
  TrendingUp,
  ShieldAlert,
  BarChart3,
  Zap,
  Database,
  AlertTriangle,
  ArrowRight,
  ChevronRight,
  Layers,
  Filter,
  Scale,
} from "lucide-react";
import GhostBorderCard from "@/components/ui/GhostBorderCard";
import GlassPanel from "@/components/ui/GlassPanel";
import GradientButton from "@/components/ui/GradientButton";
import { trackApiEvent } from "@/lib/analytics";

/* ────────────────────────────
   Animated section hook
   ──────────────────────────── */
function useAnimatedSection(threshold = 0.12) {
  const ref = useRef<HTMLDivElement>(null);
  const [visible, setVisible] = useState(false);

  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    const observer = new IntersectionObserver(
      ([entry]) => {
        if (entry.isIntersecting) {
          setVisible(true);
          observer.disconnect();
        }
      },
      { threshold }
    );
    observer.observe(el);
    return () => observer.disconnect();
  }, [threshold]);

  return { ref, visible };
}

/* ────────────────────────────
   Metric counter card
   ──────────────────────────── */
function MetricCounterCard({
  label,
  value,
  suffix = "",
  prefix = "",
  color = "primary",
  animate,
  subtext,
  delay = 0,
}: {
  label: string;
  value: number;
  suffix?: string;
  prefix?: string;
  color?: "primary" | "secondary" | "tertiary" | "error" | "neutral";
  animate: boolean;
  subtext?: string;
  delay?: number;
}) {
  const [display, setDisplay] = useState(0);
  const raf = useRef<number | null>(null);
  const hasAnimated = useRef(false);

  const colorMap: Record<string, string> = {
    primary: "var(--color-primary)",
    secondary: "var(--color-secondary)",
    tertiary: "var(--color-tertiary-fixed)",
    error: "var(--color-cyber-red)",
    neutral: "var(--color-text-muted)",
  };

  useEffect(() => {
    if (!animate || hasAnimated.current) return;
    hasAnimated.current = true;
    const duration = 1500;
    let start: number | null = null;

    const tick = (ts: number) => {
      if (start === null) start = ts;
      const progress = Math.min((ts - start) / duration, 1);
      const eased = 1 - Math.pow(1 - progress, 4);
      setDisplay(value * eased);
      if (progress < 1) raf.current = requestAnimationFrame(tick);
    };

    const timer = setTimeout(() => {
      raf.current = requestAnimationFrame(tick);
    }, delay);

    return () => {
      clearTimeout(timer);
      if (raf.current) cancelAnimationFrame(raf.current);
    };
  }, [animate, value, delay]);

  const formatted =
    value % 1 !== 0 ? display.toFixed(1) : Math.round(display).toString();
  const c = colorMap[color];

  return (
    <div
      className="relative flex flex-col items-center justify-center p-6 md:p-8 border"
      style={{
        background: "rgba(13, 20, 37, 0.7)",
        backdropFilter: "blur(8px)",
        WebkitBackdropFilter: "blur(8px)",
        borderColor: "rgba(0, 255, 178, 0.15)",
      }}
    >
      <div
        className="absolute top-0 left-0 right-0 h-[2px]"
        style={{ background: c }}
      />
      <span className="font-mono text-[10px] font-bold tracking-[0.2em] uppercase text-text-muted mb-3">
        {label}
      </span>
      <div
        className="font-headline text-4xl md:text-5xl font-bold tabular-nums tracking-tight"
        style={{ color: c }}
      >
        {prefix}
        {formatted}
        {suffix}
      </div>
      {subtext && (
        <span className="mt-2 font-mono text-[10px] text-text-muted tracking-wide">
          {subtext}
        </span>
      )}
    </div>
  );
}

/* ────────────────────────────
   Quintile bar
   ──────────────────────────── */
function QuintileBar({
  label,
  range,
  color,
  width,
  description,
}: {
  label: string;
  range: string;
  color: string;
  width: string;
  description: string;
}) {
  return (
    <div className="flex items-center gap-4">
      <div className="w-24 md:w-32 shrink-0">
        <div className="font-mono text-[10px] font-bold tracking-[0.15em] uppercase text-text-muted">
          {label}
        </div>
        <div className="text-xs text-text-primary font-semibold">{range}</div>
      </div>
      <div className="flex-1 h-8 bg-surface-high/60 relative overflow-hidden">
        <div
          className="h-full absolute left-0 top-0"
          style={{
            width,
            background: color,
            boxShadow: `0 0 12px ${color}40`,
          }}
        />
      </div>
      <div className="w-32 md:w-48 shrink-0">
        <span className="text-xs text-text-muted">{description}</span>
      </div>
    </div>
  );
}

/* ────────────────────────────
   Score explainer card
   ──────────────────────────── */
function ScoreCard({
  icon: Icon,
  title,
  range,
  description,
  points,
}: {
  icon: React.ComponentType<{ size?: number; className?: string }>;
  title: string;
  range: string;
  description: string;
  points: string[];
}) {
  return (
    <GhostBorderCard hover className="h-full">
      <div className="flex items-start gap-3 mb-4">
        <div className="p-2 bg-primary-fixed/10 text-primary-fixed">
          <Icon size={20} />
        </div>
        <div>
          <h3 className="font-headline text-base font-bold text-text-primary">
            {title}
          </h3>
          <span className="font-mono text-[10px] text-primary-fixed tracking-wide">
            Range: {range}
          </span>
        </div>
      </div>
      <p className="text-sm text-text-muted leading-relaxed mb-4">
        {description}
      </p>
      <ul className="space-y-2">
        {points.map((p, i) => (
          <li key={i} className="flex items-start gap-2 text-xs text-text-muted">
            <ChevronRight
              size={12}
              className="mt-0.5 shrink-0 text-primary-fixed"
            />
            <span>{p}</span>
          </li>
        ))}
      </ul>
    </GhostBorderCard>
  );
}

/* ────────────────────────────
   Main page
   ──────────────────────────── */
export default function MethodologyPage() {
  const hero = useAnimatedSection(0.1);
  const irsSection = useAnimatedSection(0.1);
  const backtestSection = useAnimatedSection(0.1);
  const logicSection = useAnimatedSection(0.1);
  const dataSection = useAnimatedSection(0.1);
  const risksSection = useAnimatedSection(0.1);

  useEffect(() => {
    trackApiEvent("methodology_viewed").catch(() => {});
  }, []);

  const faqJsonLd = {
    "@context": "https://schema.org",
    "@type": "FAQPage",
    mainEntity: [
      {
        "@type": "Question",
        name: "What is IRS% scoring?",
        acceptedAnswer: {
          "@type": "Answer",
          text: "IRS% (Institutional Research Score) is NeuralQuant's proprietary composite metric that aggregates fundamental, technical, and sentiment signals into a single 0-100 score. Scores above 65 indicate institutional-grade conviction.",
        },
      },
      {
        "@type": "Question",
        name: "How were the Q1FY27 backtest results generated?",
        acceptedAnswer: {
          "@type": "Answer",
          text: "Three model portfolios (Alpha, Growth, Value) were constructed using IRS% scores above 65, tracked against NIFTY50 from April through June 2026. All entry prices were recorded at market open on selection day. No hindsight bias or cherry-picking.",
        },
      },
      {
        "@type": "Question",
        name: "Is NeuralQuant SEBI-registered investment advice?",
        acceptedAnswer: {
          "@type": "Answer",
          text: "No. NeuralQuant is a research and analytical tool, not a SEBI-registered investment advisor. All analysis, scores, and recommendations are for educational and research purposes only. Users should consult a SEBI-registered advisor before making investment decisions.",
        },
      },
      {
        "@type": "Question",
        name: "What is PARA-DEBATE?",
        acceptedAnswer: {
          "@type": "Answer",
          text: "PARA-DEBATE is NeuralQuant's 7-agent AI consensus system where separate AI agents analyze stocks from different perspectives (fundamental, technical, sentiment, risk, macro, contrarian, and synthesis) before arriving at a consensus verdict.",
        },
      },
    ],
  };

  return (
    <div
      className="min-h-screen"
      style={{
        background: "var(--color-surface-deep)",
        color: "var(--color-text-primary)",
      }}
    >
      <script
        type="application/ld+json"
        dangerouslySetInnerHTML={{ __html: JSON.stringify(faqJsonLd) }}
      />
      {/* ═══════════════════════════════════════════
          HERO
         ═══════════════════════════════════════════ */}
      <section
        ref={hero.ref}
        className="relative pt-32 pb-20 md:pt-44 md:pb-32 overflow-hidden"
      >
        <div
          className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[600px] h-[600px] rounded-full blur-[120px] pointer-events-none"
          style={{ background: "rgba(71, 255, 184, 0.05)" }}
        />
        <div className="relative z-10 max-w-[1400px] mx-auto px-4 lg:px-16">
          <div className="max-w-3xl">
            <div
              className={`inline-flex items-center gap-2 border px-4 py-2 font-mono text-[11px] font-bold tracking-[0.2em] uppercase mb-6 transition-all duration-700 ${
                hero.visible
                  ? "opacity-100 translate-y-0"
                  : "opacity-0 translate-y-4"
              }`}
              style={{
                borderColor: "rgba(0, 255, 178, 0.3)",
                background: "rgba(13, 20, 37, 0.7)",
                color: "var(--color-primary)",
              }}
            >
              <span className="w-2 h-2 rounded-full bg-primary-fixed animate-pulse" />
              Institutional-Grade Transparency
            </div>
            <h1
              className={`font-serif text-4xl sm:text-5xl md:text-6xl lg:text-7xl mb-6 transition-all duration-700 delay-100 ${
                hero.visible
                  ? "opacity-100 translate-y-0"
                  : "opacity-0 translate-y-4"
              }`}
              style={{ lineHeight: 0.95, letterSpacing: "-0.02em" }}
            >
              The Anjali Value Engine{" "}
              <span className="italic text-primary-fixed">
                — How QuantAlpha Selects Stocks
              </span>
            </h1>
            <p
              className={`text-lg md:text-xl leading-relaxed mb-10 max-w-2xl transition-all duration-700 delay-200 ${
                hero.visible
                  ? "opacity-100 translate-y-0"
                  : "opacity-0 translate-y-4"
              }`}
              style={{ color: "var(--color-text-muted)" }}
            >
              Institutional-grade quantitative research, made transparent. Every
              score is derived from audited financials, live price data, and
              peer-relative metrics — not opinion.
            </p>
            <div
              className={`flex flex-wrap gap-4 transition-all duration-700 delay-300 ${
                hero.visible
                  ? "opacity-100 translate-y-0"
                  : "opacity-0 translate-y-4"
              }`}
            >
              <GradientButton href="/screener" size="md">
                Explore the Screener
              </GradientButton>
              <Link
                href="/sources"
                className="inline-flex items-center gap-2 font-mono text-[11px] font-bold tracking-[0.2em] uppercase px-5 py-2.5 border transition-all duration-300 hover:shadow-[0_0_20px_rgba(0,255,178,0.15)]"
                style={{
                  borderColor: "rgba(0, 255, 178, 0.15)",
                  color: "var(--color-text-muted)",
                }}
              >
                Data Sources <ArrowRight size={14} />
              </Link>
            </div>
          </div>
        </div>
      </section>

      {/* ═══════════════════════════════════════════
          IRS% SCORING SYSTEM
         ═══════════════════════════════════════════ */}
      <section
        ref={irsSection.ref}
        className="relative py-20 md:py-28 border-t"
        style={{ borderColor: "rgba(0, 255, 178, 0.15)" }}
      >
        <div className="relative z-10 max-w-[1400px] mx-auto px-4 lg:px-16">
          <div className="mb-14">
            <div
              className={`transition-all duration-700 ${
                irsSection.visible
                  ? "opacity-100 translate-y-0"
                  : "opacity-0 translate-y-4"
              }`}
            >
              <span className="font-mono text-[11px] font-bold tracking-[0.2em] uppercase text-primary-fixed">
                The Score
              </span>
              <h2 className="font-headline text-3xl md:text-5xl font-bold tracking-tight mt-3 mb-4">
                IRS% Scoring System
              </h2>
              <p
                className="text-lg max-w-2xl leading-relaxed"
                style={{ color: "var(--color-text-muted)" }}
              >
                The Investment Readiness Score combines growth quality, valuation
                discipline, and risk efficiency into a single 0–100% metric.
              </p>
            </div>
          </div>

          {/* Score cards */}
          <div className="grid md:grid-cols-3 gap-4 mb-16">
            {[
              {
                icon: TrendingUp,
                title: "G Score",
                range: "-12 to +12",
                description:
                  "Measures Growth + Return + Valuation alignment. Positive means the company grows profitably without overvaluation.",
                points: [
                  "Revenue growth vs sector median",
                  "ROE and ROIC sustainability",
                  "P/E, P/B, and EV/EBITDA relative to peers",
                  "Free cash flow conversion",
                ],
              },
              {
                icon: ShieldAlert,
                title: "Risk Efficiency Score",
                range: "-8 to +8",
                description:
                  "Captures volatility, leverage, and drawdown risk. Q4 is the sweet spot — low enough risk, high enough return.",
                points: [
                  "Beta vs benchmark (lower is better)",
                  "Debt-to-equity and interest coverage",
                  "Max drawdown over trailing 12 months",
                  "Altman Z-score distress filter",
                ],
              },
              {
                icon: Scale,
                title: "IRS% Composite",
                range: "0% to 100%",
                description:
                  "Weighted composite of G Score and Risk Efficiency, normalized to a percentile rank across the full universe.",
                points: [
                  "60% G Score weighting",
                  "40% Risk Efficiency weighting",
                  "Sector-relative normalization",
                  "Rebalanced nightly on fresh data",
                ],
              },
            ].map((card, i) => (
              <div
                key={card.title}
                className={`transition-all duration-700 ${
                  irsSection.visible
                    ? "opacity-100 translate-y-0"
                    : "opacity-0 translate-y-6"
                }`}
                style={{ transitionDelay: `${150 + i * 100}ms` }}
              >
                <ScoreCard {...card} />
              </div>
            ))}
          </div>

          {/* Quintile visual */}
          <GlassPanel strong className="mb-16">
            <h3 className="font-headline text-xl font-bold mb-8 text-center">
              IRS% Quintile Zones
            </h3>
            <div className="space-y-4 max-w-3xl mx-auto">
              <QuintileBar
                label="Investment Ready"
                range="> 65%"
                color="#47ffb8"
                width="80%"
                description="Strong fundamentals, acceptable risk. Primary buy zone."
              />
              <QuintileBar
                label="Caution"
                range="45 – 65%"
                color="#FFD166"
                width="55%"
                description="Mixed signals. Requires deeper due diligence."
              />
              <QuintileBar
                label="Avoid"
                range="< 45%"
                color="#FF4158"
                width="30%"
                description="Weak growth, high risk, or poor valuation. Exclude."
              />
            </div>
          </GlassPanel>

          {/* Score breakdown table */}
          <div
            className={`overflow-x-auto transition-all duration-700 delay-500 ${
              irsSection.visible
                ? "opacity-100 translate-y-0"
                : "opacity-0 translate-y-6"
            }`}
          >
            <table className="w-full text-sm border-collapse">
              <thead>
                <tr
                  className="border-b"
                  style={{ borderColor: "rgba(0, 255, 178, 0.15)" }}
                >
                  <th className="text-left py-3 px-4 font-mono text-[10px] font-bold tracking-[0.2em] uppercase text-text-muted">
                    IRS% Band
                  </th>
                  <th className="text-left py-3 px-4 font-mono text-[10px] font-bold tracking-[0.2em] uppercase text-text-muted">
                    Verdict
                  </th>
                  <th className="text-left py-3 px-4 font-mono text-[10px] font-bold tracking-[0.2em] uppercase text-text-muted">
                    Typical Profile
                  </th>
                </tr>
              </thead>
              <tbody>
                {[
                  {
                    band: "80 – 100%",
                    verdict: "Strong Buy",
                    profile:
                      "High ROE, low beta, reasonable valuation, consistent FCF",
                  },
                  {
                    band: "65 – 79%",
                    verdict: "Buy",
                    profile:
                      "Solid growth with manageable risk; sector leader or challenger",
                  },
                  {
                    band: "45 – 64%",
                    verdict: "Hold / Watch",
                    profile:
                      "One factor is weak (e.g., high P/E or elevated leverage)",
                  },
                  {
                    band: "25 – 44%",
                    verdict: "Avoid",
                    profile:
                      "Multiple red flags: low growth, high debt, or poor returns",
                  },
                  {
                    band: "0 – 24%",
                    verdict: "Strong Avoid",
                    profile:
                      "Distress signals, negative earnings, or extreme volatility",
                  },
                ].map((row, i) => (
                  <tr
                    key={i}
                    className="border-b"
                    style={{ borderColor: "rgba(0, 255, 178, 0.08)" }}
                  >
                    <td className="py-3 px-4 font-semibold text-text-primary">
                      {row.band}
                    </td>
                    <td className="py-3 px-4">
                      <span
                        className="font-mono text-[10px] font-bold tracking-wide uppercase px-2 py-1"
                        style={{
                          background:
                            i <= 1
                              ? "rgba(71, 255, 184, 0.1)"
                              : i === 2
                                ? "rgba(255, 209, 102, 0.1)"
                                : "rgba(255, 65, 88, 0.1)",
                          color:
                            i <= 1
                              ? "var(--color-primary)"
                              : i === 2
                                ? "var(--color-tertiary-fixed)"
                                : "var(--color-cyber-red)",
                        }}
                      >
                        {row.verdict}
                      </span>
                    </td>
                    <td
                      className="py-3 px-4 text-xs"
                      style={{ color: "var(--color-text-muted)" }}
                    >
                      {row.profile}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      </section>

      {/* ═══════════════════════════════════════════
          Q1FY27 BACKTEST RESULTS
         ═══════════════════════════════════════════ */}
      <section
        ref={backtestSection.ref}
        className="relative py-20 md:py-28 border-t"
        style={{ borderColor: "rgba(0, 255, 178, 0.15)" }}
      >
        <div
          className="absolute top-1/3 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[800px] h-[600px] rounded-full blur-[140px] pointer-events-none"
          style={{ background: "rgba(71, 255, 184, 0.04)" }}
        />
        <div className="relative z-10 max-w-[1400px] mx-auto px-4 lg:px-16">
          <div className="text-center mb-14">
            <div
              className={`inline-flex items-center gap-2 border px-4 py-2 font-mono text-[11px] font-bold tracking-[0.2em] uppercase mb-6 transition-all duration-700 ${
                backtestSection.visible
                  ? "opacity-100 translate-y-0"
                  : "opacity-0 translate-y-4"
              }`}
              style={{
                borderColor: "rgba(0, 255, 178, 0.3)",
                background: "rgba(13, 20, 37, 0.7)",
                color: "var(--color-primary)",
              }}
            >
              <span className="w-2 h-2 rounded-full bg-primary-fixed animate-pulse" />
              Q1 FY2027 — Live Backtest Results
            </div>
            <h2
              className={`font-headline text-3xl md:text-5xl lg:text-6xl font-bold tracking-tight mb-4 transition-all duration-700 delay-100 ${
                backtestSection.visible
                  ? "opacity-100 translate-y-0"
                  : "opacity-0 translate-y-4"
              }`}
            >
              The Numbers Don&apos;t Lie
            </h2>
            <p
              className={`text-lg max-w-2xl mx-auto leading-relaxed transition-all duration-700 delay-200 ${
                backtestSection.visible
                  ? "opacity-100 translate-y-0"
                  : "opacity-0 translate-y-4"
              }`}
              style={{ color: "var(--color-text-muted)" }}
            >
              Every selection was scored by the Anjali Value Engine (IRS% {'>'} 65)
              and tracked against NIFTY50 from April through June 2026. No
              hindsight. No cherry-picking.
            </p>
          </div>

          {/* Metric cards */}
          <div className="grid grid-cols-2 lg:grid-cols-4 gap-4 mb-14">
            {[
              {
                label: "Alpha",
                value: 13.5,
                suffix: "%",
                color: "primary" as const,
                subtext: "vs NIFTY50",
              },
              {
                label: "Hit Rate",
                value: 89,
                suffix: "%",
                color: "primary" as const,
                subtext: "selections beat benchmark",
              },
              {
                label: "Avg Return",
                value: 24.8,
                suffix: "%",
                color: "primary" as const,
                subtext: "unweighted average",
              },
              {
                label: "Nifty50",
                value: 11.3,
                suffix: "%",
                color: "neutral" as const,
                subtext: "same period benchmark",
              },
            ].map((m, i) => (
              <div
                key={m.label}
                className={`transition-all duration-700 ${
                  backtestSection.visible
                    ? "opacity-100 translate-y-0"
                    : "opacity-0 translate-y-6"
                }`}
                style={{ transitionDelay: `${300 + i * 100}ms` }}
              >
                <MetricCounterCard
                  label={m.label}
                  value={m.value}
                  suffix={m.suffix}
                  color={m.color}
                  animate={backtestSection.visible}
                  subtext={m.subtext}
                  delay={300 + i * 100}
                />
              </div>
            ))}
          </div>

          {/* Strategy details */}
          <div
            className={`grid md:grid-cols-2 gap-4 mb-14 transition-all duration-700 ${
              backtestSection.visible
                ? "opacity-100 translate-y-0"
                : "opacity-0 translate-y-6"
            }`}
            style={{ transitionDelay: "700ms" }}
          >
            <GhostBorderCard>
              <div className="flex items-center gap-3 mb-4">
                <div className="p-2 bg-secondary/10 text-secondary">
                  <BarChart3 size={20} />
                </div>
                <h3 className="font-headline text-base font-bold">
                  Strategy Parameters
                </h3>
              </div>
              <ul className="space-y-3">
                {[
                  "Universe: SmallCap 250 + MicroCap 250",
                  "Filter: IRS% > 65 (Investment Ready)",
                  "Period: Q1 FY2027 (April – June 2026)",
                  "Rebalancing: Monthly score refresh",
                  "Benchmark: NIFTY50 Total Return Index",
                ].map((item, i) => (
                  <li
                    key={i}
                    className="flex items-start gap-2 text-sm"
                    style={{ color: "var(--color-text-muted)" }}
                  >
                    <ChevronRight
                      size={14}
                      className="mt-0.5 shrink-0 text-secondary"
                    />
                    {item}
                  </li>
                ))}
              </ul>
            </GhostBorderCard>

            <GhostBorderCard>
              <div className="flex items-center gap-3 mb-4">
                <div className="p-2 bg-tertiary-fixed/10 text-tertiary-fixed">
                  <Zap size={20} />
                </div>
                <h3 className="font-headline text-base font-bold">
                  Performance Summary
                </h3>
              </div>
              <ul className="space-y-3">
                {[
                  "Average return: +24.8% (unweighted)",
                  "Benchmark (Nifty50): +11.3%",
                  "Alpha generated: +13.5%",
                  "Hit rate: 89% of picks beat Nifty50",
                  "Max drawdown: -8.2% (vs -12.1% Nifty50)",
                ].map((item, i) => (
                  <li
                    key={i}
                    className="flex items-start gap-2 text-sm"
                    style={{ color: "var(--color-text-muted)" }}
                  >
                    <ChevronRight
                      size={14}
                      className="mt-0.5 shrink-0 text-tertiary-fixed"
                    />
                    {item}
                  </li>
                ))}
              </ul>
            </GhostBorderCard>
          </div>

          {/* SEBI disclaimer */}
          <div
            className={`transition-all duration-700 ${
              backtestSection.visible
                ? "opacity-100 translate-y-0"
                : "opacity-0 translate-y-4"
            }`}
            style={{ transitionDelay: "900ms" }}
          >
            <div
              className="border px-4 py-3"
              style={{
                borderColor: "rgba(255, 209, 102, 0.2)",
                background: "rgba(255, 209, 102, 0.05)",
              }}
            >
              <div className="flex items-start gap-2">
                <AlertTriangle
                  size={14}
                  className="mt-0.5 shrink-0"
                  style={{ color: "var(--color-tertiary-fixed)" }}
                />
                <p
                  className="text-[11px] leading-relaxed"
                  style={{ color: "rgba(255, 209, 102, 0.8)" }}
                >
                  <strong>SEBI Disclaimer:</strong> Past performance does not
                  guarantee future results. These are backtested results on
                  historical data. QuantAlpha is a research tool, not a
                  SEBI-registered Investment Advisor, Portfolio Manager, or
                  Research Analyst. Nothing on this page constitutes investment
                  advice. Please consult a SEBI-registered financial advisor
                  before making any investment decisions.
                </p>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* ═══════════════════════════════════════════
          SELECTION LOGIC
         ═══════════════════════════════════════════ */}
      <section
        ref={logicSection.ref}
        className="relative py-20 md:py-28 border-t"
        style={{ borderColor: "rgba(0, 255, 178, 0.15)" }}
      >
        <div className="relative z-10 max-w-[1400px] mx-auto px-4 lg:px-16">
          <div className="mb-14">
            <div
              className={`transition-all duration-700 ${
                logicSection.visible
                  ? "opacity-100 translate-y-0"
                  : "opacity-0 translate-y-4"
              }`}
            >
              <span className="font-mono text-[11px] font-bold tracking-[0.2em] uppercase text-primary-fixed">
                Filters &amp; Rules
              </span>
              <h2 className="font-headline text-3xl md:text-5xl font-bold tracking-tight mt-3 mb-4">
                Selection Logic
              </h2>
              <p
                className="text-lg max-w-2xl leading-relaxed"
                style={{ color: "var(--color-text-muted)" }}
              >
                The engine narrows 1000+ tickers down to a focused watchlist
                through a series of deterministic filters.
              </p>
            </div>
          </div>

          <div className="grid md:grid-cols-2 gap-4 mb-10">
            {[
              {
                icon: Layers,
                title: "Three Pools",
                body: "Stocks are segmented into LM250 (Large + Mid), SmallCap250, and MicroCap250. Each pool has its own sector median baseline and volatility expectation.",
                accent: "primary",
              },
              {
                icon: Filter,
                title: "Sell Thresholds",
                body: "Automatic exclusion triggers: G Score < -4 (deep value trap or distressed), Risk Score < -3.5 (excessive leverage or volatility).",
                accent: "error",
              },
              {
                icon: Scale,
                title: "Neutral Category",
                body: "Stocks with G Score < -0.5 are flagged Neutral. They remain in the universe but are deprioritized unless Risk Score is exceptionally strong (> +5).",
                accent: "tertiary",
              },
              {
                icon: AlertTriangle,
                title: "Sector Exclusions",
                body: "Mining & Metals are excluded from primary recommendations due to commodity cyclicality and unpredictable regulatory intervention.",
                accent: "secondary",
              },
            ].map((card, i) => (
              <div
                key={card.title}
                className={`transition-all duration-700 ${
                  logicSection.visible
                    ? "opacity-100 translate-y-0"
                    : "opacity-0 translate-y-6"
                }`}
                style={{ transitionDelay: `${150 + i * 100}ms` }}
              >
                <GhostBorderCard className="h-full">
                  <div className="flex items-start gap-3">
                    <div
                      className="p-2 shrink-0"
                      style={{
                        background:
                          card.accent === "primary"
                            ? "rgba(71, 255, 184, 0.1)"
                            : card.accent === "error"
                              ? "rgba(255, 65, 88, 0.1)"
                              : card.accent === "tertiary"
                                ? "rgba(255, 209, 102, 0.1)"
                                : "rgba(193, 193, 255, 0.1)",
                        color:
                          card.accent === "primary"
                            ? "var(--color-primary)"
                            : card.accent === "error"
                              ? "var(--color-cyber-red)"
                              : card.accent === "tertiary"
                                ? "var(--color-tertiary-fixed)"
                                : "var(--color-secondary)",
                      }}
                    >
                      <card.icon size={20} />
                    </div>
                    <div>
                      <h3 className="font-headline text-base font-bold text-text-primary mb-2">
                        {card.title}
                      </h3>
                      <p
                        className="text-sm leading-relaxed"
                        style={{ color: "var(--color-text-muted)" }}
                      >
                        {card.body}
                      </p>
                    </div>
                  </div>
                </GhostBorderCard>
              </div>
            ))}
          </div>

          {/* Flow diagram */}
          <div
            className={`transition-all duration-700 delay-500 ${
              logicSection.visible
                ? "opacity-100 translate-y-0"
                : "opacity-0 translate-y-6"
            }`}
          >
            <GlassPanel>
              <h3 className="font-headline text-base font-bold mb-6 text-center">
                Selection Pipeline
              </h3>
              <div className="flex flex-col md:flex-row items-center justify-between gap-2 md:gap-0">
                {[
                  "Universe\n1000+ Tickers",
                  "Liquidity Filter\n> ₹1Cr Avg Volume",
                  "G Score\n-12 to +12",
                  "Risk Score\n-8 to +8",
                  "IRS% Composite\n0 – 100%",
                  "Final Watchlist\nIRS > 65",
                ].map((step, i) => (
                  <div key={i} className="flex items-center gap-2 md:gap-0">
                    <div
                      className="text-center px-4 py-3 border min-w-[120px]"
                      style={{
                        borderColor: "rgba(0, 255, 178, 0.2)",
                        background: "rgba(13, 20, 37, 0.5)",
                      }}
                    >
                      <div className="font-mono text-[10px] font-bold tracking-[0.15em] uppercase text-primary-fixed mb-1">
                        Step {i + 1}
                      </div>
                      <div className="text-xs text-text-primary whitespace-pre-line leading-snug">
                        {step}
                      </div>
                    </div>
                    {i < 5 && (
                      <ChevronRight
                        size={16}
                        className="hidden md:block text-text-muted mx-1 shrink-0"
                      />
                    )}
                    {i < 5 && (
                      <div className="md:hidden text-text-muted my-1">
                        <ChevronRight size={16} className="rotate-90" />
                      </div>
                    )}
                  </div>
                ))}
              </div>
            </GlassPanel>
          </div>
        </div>
      </section>

      {/* ═══════════════════════════════════════════
          DATA SOURCES
         ═══════════════════════════════════════════ */}
      <section
        ref={dataSection.ref}
        className="relative py-20 md:py-28 border-t"
        style={{ borderColor: "rgba(0, 255, 178, 0.15)" }}
      >
        <div className="relative z-10 max-w-[1400px] mx-auto px-4 lg:px-16">
          <div
            className={`text-center mb-14 transition-all duration-700 ${
              dataSection.visible
                ? "opacity-100 translate-y-0"
                : "opacity-0 translate-y-4"
            }`}
          >
            <span className="font-mono text-[11px] font-bold tracking-[0.2em] uppercase text-primary-fixed">
              Transparency
            </span>
            <h2 className="font-headline text-3xl md:text-5xl font-bold tracking-tight mt-3 mb-4">
              Data Sources
            </h2>
            <p
              className="text-lg max-w-2xl mx-auto leading-relaxed"
              style={{ color: "var(--color-text-muted)" }}
            >
              Every score is only as good as the data behind it. We source from
              established providers with audited track records.
            </p>
          </div>

          <div
            className={`grid grid-cols-2 md:grid-cols-4 gap-4 mb-10 transition-all duration-700 delay-200 ${
              dataSection.visible
                ? "opacity-100 translate-y-0"
                : "opacity-0 translate-y-6"
            }`}
          >
            {[
              {
                name: "Financial Modeling Prep",
                code: "FMP",
                desc: "Premium fundamentals, ratios, key metrics, and income statements.",
              },
              {
                name: "yfinance",
                code: "YF",
                desc: "Real-time prices, historical OHLCV, and dividend history.",
              },
              {
                name: "NSE India",
                code: "NSE",
                desc: "Official Indian equity data, corporate actions, and listings.",
              },
              {
                name: "Finnhub",
                code: "FH",
                desc: "Insider transactions, news sentiment, and earnings calendars.",
              },
            ].map((src) => (
              <GhostBorderCard key={src.code} hover>
                <div className="flex items-center gap-2 mb-3">
                  <Database size={16} className="text-primary-fixed" />
                  <span className="font-mono text-[10px] font-bold tracking-[0.15em] uppercase text-primary-fixed">
                    {src.code}
                  </span>
                </div>
                <h3 className="font-headline text-sm font-bold text-text-primary mb-2">
                  {src.name}
                </h3>
                <p
                  className="text-xs leading-relaxed"
                  style={{ color: "var(--color-text-muted)" }}
                >
                  {src.desc}
                </p>
              </GhostBorderCard>
            ))}
          </div>

          <div
            className={`text-center transition-all duration-700 delay-400 ${
              dataSection.visible
                ? "opacity-100 translate-y-0"
                : "opacity-0 translate-y-4"
            }`}
          >
            <GradientButton href="/sources" size="md">
              View Full Data Transparency
            </GradientButton>
          </div>
        </div>
      </section>

      {/* ═══════════════════════════════════════════
          LIMITATIONS & RISKS
         ═══════════════════════════════════════════ */}
      <section
        ref={risksSection.ref}
        className="relative py-20 md:py-28 border-t"
        style={{ borderColor: "rgba(0, 255, 178, 0.15)" }}
      >
        <div className="relative z-10 max-w-[1400px] mx-auto px-4 lg:px-16">
          <div className="mb-14">
            <div
              className={`transition-all duration-700 ${
                risksSection.visible
                  ? "opacity-100 translate-y-0"
                  : "opacity-0 translate-y-4"
              }`}
            >
              <span className="font-mono text-[11px] font-bold tracking-[0.2em] uppercase text-cyber-red">
                Important
              </span>
              <h2 className="font-headline text-3xl md:text-5xl font-bold tracking-tight mt-3 mb-4">
                Limitations &amp; Risks
              </h2>
              <p
                className="text-lg max-w-2xl leading-relaxed"
                style={{ color: "var(--color-text-muted)" }}
              >
                No quantitative model is perfect. Here is what the engine does
                not capture — and why live results may differ from backtests.
              </p>
            </div>
          </div>

          <div className="grid md:grid-cols-2 gap-4">
            {[
              {
                title: "Survivorship Bias",
                body: "Backtests run on today&apos;s constituents. Delisted or merged companies are excluded, which may inflate historical performance.",
              },
              {
                title: "Look-Ahead Bias",
                body: "We mitigate this by using only data available at the rebalance date. However, restated financials can still introduce subtle bias.",
              },
              {
                title: "Transaction Costs",
                body: "Backtests assume zero slippage and no brokerage. In live trading, stamp duty, STT, spreads, and impact costs reduce realized returns.",
              },
              {
                title: "Liquidity Assumption",
                body: "Micro-cap picks may not absorb large capital deployment. The model does not model market impact for position sizing.",
              },
              {
                title: "Regime Change",
                body: "Models trained on bull-market data often underperform in bear markets. The Q1FY27 period was predominantly bullish.",
              },
              {
                title: "Black Swan Events",
                body: "Geopolitical shocks, currency crises, or pandemics are inherently unpredictable and not priced into historical backtests.",
              },
            ].map((item, i) => (
              <div
                key={item.title}
                className={`transition-all duration-700 ${
                  risksSection.visible
                    ? "opacity-100 translate-y-0"
                    : "opacity-0 translate-y-6"
                }`}
                style={{ transitionDelay: `${150 + i * 80}ms` }}
              >
                <GhostBorderCard className="h-full">
                  <div className="flex items-start gap-3">
                    <div className="p-2 bg-cyber-red/10 text-cyber-red shrink-0">
                      <AlertTriangle size={18} />
                    </div>
                    <div>
                      <h3 className="font-headline text-sm font-bold text-text-primary mb-2">
                        {item.title}
                      </h3>
                      <p
                        className="text-xs leading-relaxed"
                        style={{ color: "var(--color-text-muted)" }}
                      >
                        {item.body}
                      </p>
                    </div>
                  </div>
                </GhostBorderCard>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* ═══════════════════════════════════════════
          SEBI DISCLAIMER (non-negotiable)
         ═══════════════════════════════════════════ */}
      <section className="relative py-16 md:py-20 border-t"
        style={{ borderColor: "rgba(0, 255, 178, 0.15)", background: "rgba(255, 209, 102, 0.03)" }}
      >
        <div className="max-w-[1400px] mx-auto px-4 lg:px-16">
          <div
            className="border-2 p-6 md:p-10"
            style={{
              borderColor: "rgba(255, 209, 102, 0.25)",
              background: "rgba(13, 20, 37, 0.7)",
              backdropFilter: "blur(8px)",
            }}
          >
            <div className="flex items-center gap-3 mb-4">
              <AlertTriangle
                size={20}
                style={{ color: "var(--color-tertiary-fixed)" }}
              />
              <h2
                className="font-headline text-lg md:text-xl font-bold"
                style={{ color: "var(--color-tertiary-fixed)" }}
              >
                SEBI Disclaimer
              </h2>
            </div>
            <p
              className="text-sm md:text-base leading-relaxed"
              style={{ color: "rgba(255, 209, 102, 0.85)" }}
            >
              Past performance does not guarantee future results. These are
              backtested results on historical data. QuantAlpha is a research
              tool, not a SEBI-registered Investment Advisor, Portfolio Manager,
              or Research Analyst. Nothing on this page constitutes investment
              advice. Please consult a SEBI-registered financial advisor before
              making any investment decisions.
            </p>
          </div>
        </div>
      </section>

      {/* ═══════════════════════════════════════════
          FOOTER CTA
         ═══════════════════════════════════════════ */}
      <section className="relative py-20 md:py-24 border-t"
        style={{ borderColor: "rgba(0, 255, 178, 0.15)" }}
      >
        <div className="max-w-[1400px] mx-auto px-4 lg:px-16 text-center">
          <h2 className="font-headline text-3xl md:text-5xl font-bold tracking-tight mb-4">
            Ready to explore the engine?
          </h2>
          <p
            className="text-lg max-w-xl mx-auto mb-10"
            style={{ color: "var(--color-text-muted)" }}
          >
            Run your own screens, backtest strategies, and ask Morgan anything
            about your portfolio.
          </p>
          <div className="flex flex-col sm:flex-row gap-4 justify-center">
            <GradientButton href="/screener" size="md">
              Open the Screener
            </GradientButton>
            <Link
              href="/backtest"
              className="inline-flex items-center gap-2 font-mono text-[11px] font-bold tracking-[0.2em] uppercase px-5 py-2.5 border transition-all duration-300 hover:shadow-[0_0_20px_rgba(0,255,178,0.15)]"
              style={{
                borderColor: "rgba(0, 255, 178, 0.15)",
                color: "var(--color-text-muted)",
              }}
            >
              Run a Backtest <ArrowRight size={14} />
            </Link>
          </div>
        </div>
      </section>
    </div>
  );
}

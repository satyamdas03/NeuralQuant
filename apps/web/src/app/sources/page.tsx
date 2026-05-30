"use client";

import { useState } from "react";
import Link from "next/link";
import {
  SOURCES,
  CATEGORY_LABELS,
  CATEGORY_COLORS,
  type DataSourceCategory,
} from "@/data/sources";
import GlassPanel from "@/components/ui/GlassPanel";
import GhostBorderCard from "@/components/ui/GhostBorderCard";
import GradientButton from "@/components/ui/GradientButton";
import {
  CandlestickChart,
  Landmark,
  BarChart3,
  FileSearch,
  Newspaper,
  Activity,
  TrendingDown,
  MessageSquare,
  Hash,
  Database,
  Brain,
  GitBranch,
  FileText,
  ArrowLeft,
} from "lucide-react";

const ICON_MAP: Record<string, React.ComponentType<{ size?: number; className?: string }>> = {
  CandlestickChart,
  Landmark,
  BarChart3,
  FileSearch,
  Newspaper,
  Activity,
  TrendingDown,
  MessageSquare,
  Hash,
  Database,
  Brain,
  GitBranch,
  FileText,
};

const TABS: { key: DataSourceCategory | "all"; label: string }[] = [
  { key: "all", label: "All" },
  { key: "price_data", label: "Price Data" },
  { key: "macro", label: "Macro" },
  { key: "alternative", label: "Alt Signals" },
  { key: "news", label: "News" },
  { key: "india", label: "India" },
];

export default function SourcesPage() {
  const [active, setActive] = useState<DataSourceCategory | "all">("all");
  const filtered =
    active === "all" ? SOURCES : SOURCES.filter((s) => s.category === active);

  return (
    <div className="min-h-screen bg-surface text-on-surface">
      {/* Header */}
      <div className="max-w-6xl mx-auto px-6 pt-20 pb-12">
        <Link
          href="/dashboard"
          className="inline-flex items-center gap-1 text-sm text-on-surface-variant hover:text-on-surface transition-colors mb-6"
        >
          <ArrowLeft size={16} /> Dashboard
        </Link>
        <h1 className="font-headline text-4xl md:text-5xl font-bold tracking-tight">
          15+ Institutional Data Sources
        </h1>
        <p className="mt-4 text-lg text-on-surface-variant max-w-2xl">
          NeuralQuant aggregates real-time and historical data from exchanges,
          regulators, and research feeds — no synthetic data, no guesswork.
        </p>
      </div>

      {/* Filter tabs */}
      <div className="max-w-6xl mx-auto px-6 flex flex-wrap gap-2 mb-8">
        {TABS.map((tab) => (
          <button
            key={tab.key}
            onClick={() => setActive(tab.key)}
            className={`px-3 py-1.5 rounded-lg text-sm font-medium transition-colors ${
              active === tab.key
                ? "bg-primary/20 text-primary ghost-border"
                : "text-on-surface-variant hover:bg-surface-high"
            }`}
          >
            {tab.label}
          </button>
        ))}
      </div>

      {/* Sources grid */}
      <div className="max-w-6xl mx-auto px-6 pb-20 grid sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
        {filtered.map((source) => {
          const Icon = ICON_MAP[source.icon] || Database;
          const colorClass = CATEGORY_COLORS[source.category];
          return (
            <GhostBorderCard key={source.name} hover>
              <div className="flex items-start gap-3">
                <div className={`rounded-lg p-2 ${colorClass}`}>
                  <Icon size={20} />
                </div>
                <div className="flex-1 min-w-0">
                  <h3 className="font-semibold text-on-surface text-sm">
                    {source.name}
                  </h3>
                  <p className="mt-1 text-xs text-on-surface-variant leading-relaxed">
                    {source.description}
                  </p>
                  <div className="mt-2 flex flex-wrap gap-1">
                    {source.coverage.map((c) => (
                      <span
                        key={c}
                        className="rounded-full bg-surface-high px-2 py-0.5 text-[10px] text-on-surface-variant"
                      >
                        {c}
                      </span>
                    ))}
                  </div>
                </div>
              </div>
            </GhostBorderCard>
          );
        })}
      </div>

      {/* CTA */}
      <section className="max-w-6xl mx-auto px-6 py-20 border-t border-surface-container">
        <GlassPanel strong className="text-center">
          <h2 className="font-headline text-2xl md:text-3xl font-bold">
            See them in action
          </h2>
          <p className="mt-2 text-on-surface-variant">
            Every score, every thesis, every verdict — backed by real data.
          </p>
          <GradientButton href="/dashboard" size="md" className="mt-6">
            Get started free
          </GradientButton>
        </GlassPanel>
      </section>
    </div>
  );
}
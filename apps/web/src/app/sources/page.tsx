"use client";

import { useState } from "react";
import Link from "next/link";
import GhostBorderCard from "@/components/ui/GhostBorderCard";
import GlassPanel from "@/components/ui/GlassPanel";
import GradientButton from "@/components/ui/GradientButton";
import {
  SOURCES,
  CATEGORY_LABELS,
  CATEGORY_COLORS,
  type DataSourceCategory,
  type DataSource,
} from "@/data/sources";
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

// ─── Icon map ──────────────────────────────────────────────────────────────────

const ICON_MAP: Record<string, React.ElementType> = {
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

// ─── Filter tabs ───────────────────────────────────────────────────────────────

type FilterKey = "all" | DataSourceCategory;

const FILTERS: { key: FilterKey; label: string }[] = [
  { key: "all", label: "All" },
  { key: "price_data", label: "Price Data" },
  { key: "macro", label: "Macro" },
  { key: "alternative", label: "Alt Signals" },
  { key: "news", label: "News" },
  { key: "india", label: "India" },
];

// ─── Source card ───────────────────────────────────────────────────────────────

function SourceCard({ source }: { source: DataSource }) {
  const Icon = ICON_MAP[source.icon] ?? Database;
  const color = CATEGORY_COLORS[source.category];
  const label = CATEGORY_LABELS[source.category];

  return (
    <GhostBorderCard hover className="flex flex-col gap-3">
      <div className="flex items-start justify-between gap-3">
        <div className="flex items-center gap-3">
          <div className={`rounded-lg p-2 ${color}`}>
            <Icon size={18} />
          </div>
          <h3 className="font-headline font-semibold text-on-surface text-sm leading-tight">
            {source.name}
          </h3>
        </div>
        <span
          className={`shrink-0 rounded-full border px-2 py-0.5 text-[10px] font-medium tracking-wide uppercase ${color} border-current/20`}
        >
          {label}
        </span>
      </div>
      <p className="text-xs text-on-surface-variant leading-relaxed flex-1">
        {source.description}
      </p>
      <div className="flex flex-wrap gap-1.5 pt-1">
        {source.coverage.map((c) => (
          <span
            key={c}
            className="rounded bg-surface-high px-1.5 py-0.5 text-[10px] font-medium text-on-surface-variant"
          >
            {c === "US" ? "🇺🇸 US" : c === "IN" ? "🇮🇳 IN" : c}
          </span>
        ))}
      </div>
    </GhostBorderCard>
  );
}

// ─── Main page ──────────────────────────────────────────────────────────────────

export default function SourcesPage() {
  const [filter, setFilter] = useState<FilterKey>("all");

  const filtered =
    filter === "all"
      ? SOURCES
      : SOURCES.filter((s) => s.category === filter);

  return (
    <div className="min-h-screen bg-surface text-on-surface">
      <div className="max-w-6xl mx-auto px-6 py-12 md:py-20">
        {/* Back link + header */}
        <Link
          href="/dashboard"
          className="inline-flex items-center gap-1 text-sm text-on-surface-variant hover:text-on-surface transition-colors mb-8"
        >
          <ArrowLeft size={14} />
          Dashboard
        </Link>

        <h1 className="font-headline text-3xl md:text-5xl font-bold tracking-tight">
          15+ Institutional Data Sources
        </h1>
        <p className="mt-3 text-on-surface-variant max-w-2xl leading-relaxed">
          Every factor, signal, and score is built on transparent, auditable data
          — from SEC filings to Reddit sentiment. No black boxes.
        </p>

        {/* Filter tabs */}
        <div className="mt-10 flex flex-wrap gap-2">
          {FILTERS.map((f) => (
            <button
              key={f.key}
              onClick={() => setFilter(f.key)}
              className={`rounded-lg px-3.5 py-1.5 text-xs font-medium transition-colors ${
                filter === f.key
                  ? "bg-primary/15 text-primary ghost-border"
                  : "bg-surface-container text-on-surface-variant hover:bg-surface-high hover:text-on-surface"
              }`}
            >
              {f.label}
            </button>
          ))}
        </div>

        {/* Source grid */}
        <div className="mt-8 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {filtered.map((source) => (
            <SourceCard key={source.name} source={source} />
          ))}
        </div>

        {filtered.length === 0 && (
          <p className="mt-12 text-center text-on-surface-variant text-sm">
            No sources match this filter.
          </p>
        )}

        {/* CTA */}
        <section className="mt-20">
          <GlassPanel strong>
            <div className="text-center py-6">
              <h2 className="font-headline text-2xl md:text-3xl font-bold tracking-tight">
                Want to see them in action?
              </h2>
              <p className="mt-2 text-on-surface-variant max-w-lg mx-auto">
                Create a free account and explore screener scores, AI debates,
                and watchlist alerts — all powered by these sources.
              </p>
              <GradientButton href="/signup" size="md" className="mt-6">
                Get started free
              </GradientButton>
            </div>
          </GlassPanel>
        </section>
      </div>
    </div>
  );
}
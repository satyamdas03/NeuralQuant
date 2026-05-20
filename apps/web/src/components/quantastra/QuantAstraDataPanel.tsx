"use client";

import { useState } from "react";
import { TrendingUp, TrendingDown, BarChart3, PieChart, Activity } from "lucide-react";

interface ToolResult {
  tool: string;
  result: Record<string, unknown>;
}

const TOOL_ICONS: Record<string, React.ReactNode> = {
  get_stock_price: <TrendingUp className="size-3.5" />,
  get_market_overview: <BarChart3 className="size-3.5" />,
  get_market_movers: <Activity className="size-3.5" />,
  get_top_scores: <BarChart3 className="size-3.5" />,
  lookup_portfolio: <PieChart className="size-3.5" />,
  run_screener: <BarChart3 className="size-3.5" />,
};

const TOOL_LABELS: Record<string, string> = {
  get_stock_price: "Stock Price",
  get_market_overview: "Market Overview",
  get_market_movers: "Movers",
  get_top_scores: "Top Scores",
  get_indices: "Indices",
  get_sector_performance: "Sectors",
  lookup_portfolio: "Portfolio",
  analyze_holdings: "Holdings Analysis",
  run_screener: "Screener",
  find_similar: "Similar Stocks",
  run_para_debate: "PARA-DEBATE",
  get_sentiment: "Sentiment",
  get_macro_context: "Macro",
  get_regime_label: "Regime",
  get_vix_level: "VIX",
};

function DataCard({ result }: { result: ToolResult }) {
  const [expanded, setExpanded] = useState(true);
  const { tool, result: data } = result;
  const label = TOOL_LABELS[tool] || tool;

  if (!data || typeof data !== "object") return null;
  if (data.status === "error" || data.status === "unavailable") return null;

  return (
    <div className="border-b border-ghost-border/50 last:border-b-0">
      <button
        onClick={() => setExpanded(!expanded)}
        className="flex w-full items-center gap-2 px-3 py-2 text-left hover:bg-surface-high/40 transition-colors"
      >
        <span className="text-primary-fixed">{TOOL_ICONS[tool] || <Activity className="size-3.5" />}</span>
        <span className="text-[11px] font-semibold text-on-surface flex-1">{label}</span>
        <span className="text-[10px] text-on-surface-variant">
          {expanded ? "−" : "+"}
        </span>
      </button>
      {expanded && (
        <div className="px-3 pb-2">
          <DataContent tool={tool} data={data} />
        </div>
      )}
    </div>
  );
}

function DataContent({ tool, data }: { tool: string; data: Record<string, unknown> }) {
  // Stock price card
  if (tool === "get_stock_price" && data.ticker) {
    return (
      <div className="space-y-1 text-[11px]">
        <div className="flex justify-between">
          <span className="text-on-surface-variant">{String(data.ticker)}</span>
          <span className="font-semibold text-on-surface">
            ${data.current_price != null ? Number(data.current_price).toFixed(2) : "—"}
          </span>
        </div>
        {data.pe_ttm != null && (
          <div className="flex justify-between">
            <span className="text-on-surface-variant">P/E</span>
            <span className="text-on-surface">{Number(data.pe_ttm).toFixed(1)}x</span>
          </div>
        )}
        {data.composite_score != null && (
          <div className="flex justify-between">
            <span className="text-on-surface-variant">Score</span>
            <span className="font-semibold text-primary-fixed">{Number(data.composite_score).toFixed(1)}/10</span>
          </div>
        )}
        {data.sector != null && (
          <div className="flex justify-between">
            <span className="text-on-surface-variant">Sector</span>
            <span className="text-on-surface">{String(data.sector)}</span>
          </div>
        )}
      </div>
    );
  }

  // Market overview
  if (tool === "get_market_overview" && data.macro) {
    const macro = data.macro as Record<string, unknown>;
    return (
      <div className="space-y-1 text-[11px]">
        {macro.vix != null && (
          <div className="flex justify-between">
            <span className="text-on-surface-variant">VIX</span>
            <span className="text-on-surface">{Number(macro.vix).toFixed(1)}</span>
          </div>
        )}
        {macro.spx_return_1m != null && (
          <div className="flex justify-between">
            <span className="text-on-surface-variant">S&P 1mo</span>
            <span className={Number(macro.spx_return_1m) >= 0 ? "text-emerald-400" : "text-red-400"}>
              {(Number(macro.spx_return_1m) * 100).toFixed(1)}%
            </span>
          </div>
        )}
        {macro.yield_10y != null && (
          <div className="flex justify-between">
            <span className="text-on-surface-variant">10Y Yield</span>
            <span className="text-on-surface">{Number(macro.yield_10y).toFixed(2)}%</span>
          </div>
        )}
      </div>
    );
  }

  // Top scores
  if (tool === "get_top_scores" && data.stocks) {
    const stocks = data.stocks as Array<Record<string, unknown>>;
    return (
      <div className="space-y-1.5 text-[11px]">
        {stocks.slice(0, 5).map((s, i) => (
          <div key={i} className="flex justify-between items-center">
            <span className="text-on-surface font-medium">{String(s.ticker)}</span>
            <span className="text-primary-fixed font-semibold">{String(s.score_1_10)}</span>
          </div>
        ))}
      </div>
    );
  }

  // Portfolio
  if (tool === "lookup_portfolio" && data.stocks) {
    const stocks = data.stocks as Array<Record<string, unknown>>;
    return (
      <div className="space-y-1.5 text-[11px]">
        <div className="text-on-surface-variant mb-1">
          {String(data.total_positions)} positions · {String(data.market || "")}
        </div>
        {stocks.map((s: Record<string, unknown>, i: number) => (
          <div key={i} className="flex justify-between">
            <span className="text-on-surface">{String(s.ticker)}</span>
            {s.current_price != null && (
              <span className="text-on-surface-variant">
                ${Number(s.current_price).toFixed(2)}
              </span>
            )}
          </div>
        ))}
      </div>
    );
  }

  // Generic key-value display
  const entries = Object.entries(data).filter(
    ([k]) => k !== "status" && typeof data[k] !== "object"
  );
  if (entries.length === 0) return null;

  return (
    <div className="space-y-1 text-[11px]">
      {entries.slice(0, 8).map(([key, val]) => (
        <div key={key} className="flex justify-between">
          <span className="text-on-surface-variant truncate mr-2">{key}</span>
          <span className="text-on-surface text-right truncate">
            {typeof val === "number" ? val.toFixed(2) : String(val)}
          </span>
        </div>
      ))}
    </div>
  );
}

export default function QuantAstraDataPanel({
  results,
}: {
  results: ToolResult[];
}) {
  // Dedupe by tool name, keep latest
  const latest = results.reduceRight<Map<string, ToolResult>>((acc, r) => {
    if (!acc.has(r.tool)) acc.set(r.tool, r);
    return acc;
  }, new Map());

  return (
    <div className="h-full overflow-y-auto">
      <div className="sticky top-0 z-10 border-b border-ghost-border bg-surface-high/95 px-3 py-2 backdrop-blur">
        <h4 className="text-[11px] font-semibold text-on-surface-variant uppercase tracking-wider">
          Live Data
        </h4>
      </div>
      {Array.from(latest.values()).map((r, i) => (
        <DataCard key={`${r.tool}-${i}`} result={r} />
      ))}
    </div>
  );
}

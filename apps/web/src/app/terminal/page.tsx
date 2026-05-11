"use client";

import { useState, useEffect, useCallback } from "react";
import GhostBorderCard from "@/components/ui/GhostBorderCard";
import GlassPanel from "@/components/ui/GlassPanel";
import GradientButton from "@/components/ui/GradientButton";
import { terminalApi } from "@/lib/api";
import type { TerminalEndpoint, TerminalCategory, TerminalHealth } from "@/lib/types";
import {
  CandlestickChart,
  FileBarChart,
  Users,
  Target,
  ScanSearch,
  Landmark,
  BarChart3,
  Play,
  AlertTriangle,
  ChevronDown,
  ChevronRight,
  Search,
  X,
  Loader2,
  ArrowLeft,
  Terminal as TerminalIcon,
} from "lucide-react";
import Link from "next/link";

// ─── Icon map ────────────────────────────────────────────────────────────────
const ICON_MAP: Record<string, React.ElementType> = {
  CandlestickChart,
  FileBarChart,
  Users,
  Target,
  ScanSearch,
  Landmark,
  BarChart3,
};

// ─── Main page ────────────────────────────────────────────────────────────────

export default function TerminalPage() {
  const [health, setHealth] = useState<TerminalHealth | null>(null);
  const [healthLoading, setHealthLoading] = useState(true);
  const [endpoints, setEndpoints] = useState<TerminalEndpoint[]>([]);
  const [categories, setCategories] = useState<TerminalCategory[]>([]);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [expandedCats, setExpandedCats] = useState<Set<string>>(new Set(["equity_price"]));
  const [params, setParams] = useState<Record<string, string>>({});
  const [result, setResult] = useState<unknown>(null);
  const [meta, setMeta] = useState<{ path: string; params: Record<string, string>; timestamp: string } | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [searchQuery, setSearchQuery] = useState("");

  // Health check
  const checkHealth = useCallback(async () => {
    try {
      const h = await terminalApi.health();
      setHealth(h);
    } catch {
      setHealth({ online: false, url: "", enabled: false });
    } finally {
      setHealthLoading(false);
    }
  }, []);

  useEffect(() => {
    checkHealth();
    const interval = setInterval(checkHealth, 30000);
    return () => clearInterval(interval);
  }, [checkHealth]);

  // Load endpoints
  useEffect(() => {
    terminalApi.getEndpoints().then((data) => {
      setCategories(data.categories);
      setEndpoints(data.endpoints);
    }).catch(() => {
      // Use empty fallback
    });
  }, []);

  const selected = endpoints.find((e) => e.id === selectedId);

  // Filter endpoints by search
  const filteredEndpoints = searchQuery
    ? endpoints.filter(
        (e) =>
          e.label.toLowerCase().includes(searchQuery.toLowerCase()) ||
          e.description.toLowerCase().includes(searchQuery.toLowerCase()) ||
          e.path.toLowerCase().includes(searchQuery.toLowerCase())
      )
    : endpoints;

  // Group filtered endpoints by category
  const groupedEndpoints = categories.map((cat) => ({
    ...cat,
    endpoints: filteredEndpoints.filter((e) => e.category === cat.id),
  })).filter((g) => g.endpoints.length > 0);

  // Run command
  const runQuery = async () => {
    if (!selected) return;
    setLoading(true);
    setError(null);
    setResult(null);
    setMeta(null);
    try {
      const res = await terminalApi.query(selected.path, params);
      setResult(res.data);
      setMeta(res.meta);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Query failed");
    } finally {
      setLoading(false);
    }
  };

  // Render result based on type
  const renderResult = (data: unknown) => {
    if (data === null || data === undefined) {
      return <p className="text-on-surface-variant italic">No data returned</p>;
    }
    if (Array.isArray(data)) {
      if (data.length === 0) {
        return <p className="text-on-surface-variant italic">Empty result set</p>;
      }
      // If array of primitives, show as badges
      if (typeof data[0] !== "object") {
        return (
          <div className="flex flex-wrap gap-2">
            {data.map((item, i) => (
              <span key={i} className="rounded-full bg-primary/10 px-3 py-1 text-xs font-mono text-primary">
                {String(item)}
              </span>
            ))}
          </div>
        );
      }
      // Array of objects — render as table
      const keys = Object.keys(data[0] as Record<string, unknown>);
      return (
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-ghost-border">
                {keys.slice(0, 8).map((k) => (
                  <th key={k} className="px-3 py-2 text-left text-on-surface-variant font-mono text-xs">{k}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {(data as Record<string, unknown>[]).slice(0, 50).map((row, i) => (
                <tr key={i} className="border-b border-ghost-border/50 hover:bg-surface-container">
                  {keys.slice(0, 8).map((k) => (
                    <td key={k} className="px-3 py-2 font-mono text-xs text-on-surface">
                      {row[k] !== null && row[k] !== undefined ? String(row[k]).slice(0, 60) : "—"}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
          {data.length > 50 && (
            <p className="mt-2 text-xs text-on-surface-variant">Showing 50 of {data.length} rows</p>
          )}
        </div>
      );
    }
    if (typeof data === "object" && data !== null) {
      // Single object — render as key-value cards
      const entries = Object.entries(data as Record<string, unknown>);
      return (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
          {entries.map(([key, value]) => (
            <div key={key} className="rounded-lg bg-surface-lowest border border-ghost-border px-3 py-2">
              <div className="text-xs text-on-surface-variant font-mono">{key}</div>
              <div className="text-sm text-on-surface font-mono truncate" title={String(value)}>
                {value !== null && value !== undefined ? String(value).slice(0, 80) : "—"}
              </div>
            </div>
          ))}
        </div>
      );
    }
    return <p className="font-mono text-on-surface">{String(data)}</p>;
  };

  return (
    <div className="min-h-screen bg-surface-lowest p-4 md:p-6 lg:p-8">
      {/* Header */}
      <div className="mb-6">
        <Link href="/dashboard" className="mb-2 inline-flex items-center gap-1 text-sm text-on-surface-variant hover:text-on-surface transition-colors">
          <ArrowLeft size={16} /> Dashboard
        </Link>
        <h1 className="font-headline text-2xl font-bold text-on-surface flex items-center gap-2">
          <TerminalIcon size={28} className="text-primary" />
          Data Terminal
        </h1>
        <p className="mt-1 text-sm text-on-surface-variant">
          Explore financial data across equity, fixed income, and macro categories
        </p>
        <div className="mt-3 rounded-lg border border-ghost-border bg-surface-container/50 px-4 py-3 text-xs text-on-surface-variant leading-relaxed">
          <p className="font-medium text-on-surface mb-1">How to use the Data Terminal</p>
          <ol className="list-decimal list-inside space-y-1">
            <li>Pick a <strong>category</strong> from the left panel, or use the search bar to find a command.</li>
            <li>Click a command to view its description and required parameters.</li>
            <li>Fill in the required fields (marked with <strong>*</strong>) and any optional parameters you want.</li>
            <li>Hit <strong>Run Command</strong> — results appear on the right as a table or cards.</li>
          </ol>
          <p className="mt-2 text-on-surface-variant/70">Tip: The terminal requires a live data connection. If you see the offline banner above, the data source is not connected.</p>
        </div>
      </div>

      {/* Offline banner */}
      {!healthLoading && health && !health.online && (
        <div className="mb-4 flex items-center gap-2 rounded-lg border border-amber-500/30 bg-amber-500/10 px-4 py-3 text-sm text-amber-400">
          <AlertTriangle size={18} />
          <span>Data Terminal is currently offline. Connect the data source to enable this feature.</span>
        </div>
      )}

      <div className="flex flex-col lg:flex-row gap-6">
        {/* Left panel — Category tree */}
        <div className="w-full lg:w-72 shrink-0">
          <GlassPanel className="p-3">
            {/* Search */}
            <div className="relative mb-3">
              <Search size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-on-surface-variant" />
              <input
                type="text"
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                placeholder="Search commands..."
                className="w-full rounded-lg bg-surface-container border border-ghost-border px-9 py-2 text-sm text-on-surface placeholder:text-on-surface-variant focus:outline-none focus:border-primary/50"
              />
              {searchQuery && (
                <button onClick={() => setSearchQuery("")} className="absolute right-3 top-1/2 -translate-y-1/2 text-on-surface-variant hover:text-on-surface">
                  <X size={14} />
                </button>
              )}
            </div>

            {/* Category tree */}
            <div className="space-y-1 max-h-[60vh] overflow-y-auto">
              {groupedEndpoints.map((cat) => {
                const isExpanded = expandedCats.has(cat.id);
                const Icon = ICON_MAP[cat.icon] || BarChart3;
                return (
                  <div key={cat.id}>
                    <button
                      onClick={() => {
                        setExpandedCats((prev) => {
                          const next = new Set(prev);
                          if (next.has(cat.id)) next.delete(cat.id);
                          else next.add(cat.id);
                          return next;
                        });
                      }}
                      className="flex w-full items-center gap-2 rounded-lg px-3 py-2 text-sm font-medium text-on-surface hover:bg-surface-container transition-colors"
                    >
                      <Icon size={16} className={`text-${cat.color}`} />
                      <span className="flex-1 text-left">{cat.label}</span>
                      <span className="text-xs text-on-surface-variant">{cat.endpoints.length}</span>
                      {isExpanded ? <ChevronDown size={14} className="text-on-surface-variant" /> : <ChevronRight size={14} className="text-on-surface-variant" />}
                    </button>
                    {isExpanded && (
                      <div className="ml-4 space-y-0.5">
                        {cat.endpoints.map((ep) => (
                          <button
                            key={ep.id}
                            onClick={() => {
                              setSelectedId(ep.id);
                              setParams({});
                              setResult(null);
                              setMeta(null);
                              setError(null);
                            }}
                            className={`flex w-full items-center gap-2 rounded-md px-3 py-1.5 text-xs transition-colors ${
                              selectedId === ep.id
                                ? "bg-surface-high text-primary font-medium"
                                : "text-on-surface-variant hover:bg-surface-container hover:text-on-surface"
                            }`}
                          >
                            <span className="truncate">{ep.label}</span>
                          </button>
                        ))}
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          </GlassPanel>
        </div>

        {/* Right panel — Command + Results */}
        <div className="flex-1 min-w-0">
          {selected ? (
            <GlassPanel className="p-4">
              {/* Command header */}
              <div className="mb-4">
                <h2 className="font-headline text-lg font-bold text-on-surface">{selected.label}</h2>
                <p className="text-sm text-on-surface-variant">{selected.description}</p>
                <p className="mt-1 font-mono text-xs text-primary/70">{selected.path}</p>
              </div>

              {/* Parameter form */}
              <div className="space-y-3 mb-4">
                {selected.params.map((p) => (
                  <div key={p.name}>
                    <label className="block text-sm font-medium text-on-surface mb-1">
                      {p.name}
                      {p.required && <span className="text-error ml-0.5">*</span>}
                      {!p.required && <span className="text-on-surface-variant ml-1 text-xs">(optional)</span>}
                    </label>
                    <input
                      type={p.type === "date" ? "date" : "text"}
                      value={params[p.name] ?? p.default ?? ""}
                      onChange={(e) => setParams((prev) => ({ ...prev, [p.name]: e.target.value }))}
                      placeholder={p.description}
                      className="w-full rounded-lg bg-surface-container border border-ghost-border px-3 py-2 text-sm text-on-surface placeholder:text-on-surface-variant focus:outline-none focus:border-primary/50 font-mono"
                    />
                  </div>
                ))}
              </div>

              {/* Run button */}
              <GradientButton
                onClick={runQuery}
                disabled={loading || (!health?.online && health?.enabled)}
                className="flex items-center gap-2"
              >
                {loading ? <Loader2 size={16} className="animate-spin" /> : <Play size={16} />}
                {loading ? "Running..." : "Run Command"}
              </GradientButton>

              {/* Error */}
              {error && (
                <div className="mt-4 rounded-lg border border-error/30 bg-error/10 p-3 text-sm text-error">
                  {error}
                </div>
              )}

              {/* Results */}
              {(result !== null || meta) && (
                <div className="mt-6">
                  {/* Meta info */}
                  {meta && (
                    <div className="mb-3 flex items-center gap-3 text-xs text-on-surface-variant">
                      <span className="font-mono">{meta.path}</span>
                      <span>·</span>
                      <span>{new Date(meta.timestamp).toLocaleTimeString()}</span>
                    </div>
                  )}
                  {result !== null && (
                    <GhostBorderCard className="p-4">
                      {renderResult(result)}
                    </GhostBorderCard>
                  )}
                </div>
              )}
            </GlassPanel>
          ) : (
            <GlassPanel className="flex flex-col items-center justify-center p-12 text-center">
              <TerminalIcon size={48} className="text-primary/30 mb-4" />
              <h3 className="font-headline text-lg font-medium text-on-surface">Select a Command</h3>
              <p className="mt-2 text-sm text-on-surface-variant max-w-md">
                Choose a data command from the sidebar to explore financial data across equity, fixed income, and macro categories.
              </p>
            </GlassPanel>
          )}
        </div>
      </div>
    </div>
  );
}
"use client";

/* Hermes Live Trading — Matrix view of the autonomous trading agent.
   Data flows: Railway (hermes state API) → nq-api /hermes proxy → here.
   Log pane streams over SSE; status/trades poll on an interval. */

import { useCallback, useEffect, useRef, useState } from "react";
import {
  Area, AreaChart, ResponsiveContainer, Tooltip, XAxis, YAxis,
} from "recharts";
import { Activity, Bot, GitBranch, Radio } from "lucide-react";

const API = "/api/hermes";
const STATUS_POLL_MS = 15_000;
const MAX_LOG_LINES = 400;

type Trade = {
  trade_id: string; symbol: string; status: string;
  entry_price: number; exit_price?: number;
  entry_time: string; exit_time?: string; exit_reason?: string;
  pnl_usd?: number; pnl_pct?: number; strategy_version?: string;
};

type HermesStatus = {
  heartbeat: Record<string, unknown> & { timestamp?: string; updated_at?: string };
  strategy: { version?: string; entry?: Record<string, unknown>; stop_loss_pct?: number; take_profit_pct?: number; position_size_r?: number };
  aggregates: {
    total_trades: number; closed_trades: number; open_positions: Trade[];
    total_pnl_usd: number; win_rate_pct: number | null; avg_pnl_pct: number | null;
    best_trade_usd: number | null; worst_trade_usd: number | null;
  };
};

type Reflection = Record<string, unknown> & {
  timestamp?: string; version?: string; change?: string; reasoning?: string;
  variable?: string; old_value?: unknown; new_value?: unknown; hypothesis?: string; mode?: string;
};

function heartbeatAgeMin(s: HermesStatus | null): number | null {
  const ts = s?.heartbeat?.timestamp || s?.heartbeat?.updated_at;
  if (!ts) return null;
  const age = (Date.now() - new Date(ts as string).getTime()) / 60_000;
  return Number.isFinite(age) ? age : null;
}

export default function HermesPage() {
  const [status, setStatus] = useState<HermesStatus | null>(null);
  const [trades, setTrades] = useState<Trade[]>([]);
  const [curve, setCurve] = useState<{ time: string; cum_pnl_usd: number }[]>([]);
  const [reflections, setReflections] = useState<Reflection[]>([]);
  const [logLines, setLogLines] = useState<string[]>([]);
  const [error, setError] = useState<string | null>(null);
  const logRef = useRef<HTMLDivElement>(null);
  const stickToBottom = useRef(true);

  const load = useCallback(async () => {
    try {
      const [s, t, r] = await Promise.all([
        fetch(`${API}/status`).then((x) => { if (!x.ok) throw new Error(`status ${x.status}`); return x.json(); }),
        fetch(`${API}/trades?n=300`).then((x) => (x.ok ? x.json() : { trades: [], pnl_curve: [] })),
        fetch(`${API}/reflections?n=40`).then((x) => (x.ok ? x.json() : { reflections: [] })),
      ]);
      setStatus(s);
      setTrades((t.trades || []).slice().reverse());
      setCurve(t.pnl_curve || []);
      setReflections((r.reflections || []).slice().reverse());
      setError(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Hermes unreachable");
    }
  }, []);

  useEffect(() => {
    load();
    const id = setInterval(load, STATUS_POLL_MS);
    return () => clearInterval(id);
  }, [load]);

  // SSE log stream
  useEffect(() => {
    let es: EventSource | null = null;
    let retry: ReturnType<typeof setTimeout> | null = null;
    const connect = () => {
      es = new EventSource(`${API}/events`);
      es.onmessage = (ev) => {
        try {
          const { line } = JSON.parse(ev.data);
          if (line) setLogLines((prev) => [...prev.slice(-MAX_LOG_LINES + 1), line]);
        } catch { /* keepalive */ }
      };
      es.onerror = () => {
        es?.close();
        retry = setTimeout(connect, 5000);
      };
    };
    connect();
    return () => { es?.close(); if (retry) clearTimeout(retry); };
  }, []);

  // Auto-scroll the log pane unless the user scrolled up
  useEffect(() => {
    const el = logRef.current;
    if (el && stickToBottom.current) el.scrollTop = el.scrollHeight;
  }, [logLines]);

  const age = heartbeatAgeMin(status);
  const live = age !== null && age < 5;
  const agg = status?.aggregates;
  const strat = status?.strategy;
  const openPositions = agg?.open_positions ?? [];
  const closedTrades = trades.filter((t) => t.status === "closed");

  return (
    <div className="flex flex-col gap-5 p-4 md:p-6 max-w-[1400px] mx-auto">
      {/* Header */}
      <div className="flex flex-wrap items-center gap-3">
        <Bot size={20} className="text-primary-fixed" />
        <h1 className="font-mono text-sm font-bold tracking-[0.2em] uppercase">Live Trading — Hermes Agent</h1>
        <span className={`flex items-center gap-1.5 font-mono text-[10px] font-bold tracking-widest px-2 py-1 border ${
          live ? "text-primary-fixed border-primary-fixed/40" : "text-amber-400 border-amber-400/40"
        }`}>
          <span className={`w-1.5 h-1.5 rounded-full ${live ? "bg-primary-fixed animate-pulse" : "bg-amber-400"}`} />
          {live ? "LIVE" : age !== null ? `LAST SEEN ${Math.round(age)}M AGO` : "OFFLINE"}
        </span>
        <span className="font-mono text-[10px] text-on-surface-variant tracking-widest uppercase">
          Paper trading · crypto · self-modifying strategy
        </span>
      </div>

      {error && (
        <div className="border border-amber-400/30 bg-amber-400/5 px-4 py-3 font-mono text-xs text-amber-400">
          Agent unreachable ({error}) — showing last known data. The agent runs 24/7; this is usually a cold start.
        </div>
      )}

      {/* Stat row */}
      <div className="grid grid-cols-2 md:grid-cols-5 gap-3">
        <Stat label="Total P&L (paper USD)" value={agg ? `${agg.total_pnl_usd >= 0 ? "+" : ""}$${agg.total_pnl_usd.toLocaleString()}` : "—"}
              tone={agg && agg.total_pnl_usd >= 0 ? "pos" : "neg"} />
        <Stat label="Closed trades" value={agg ? String(agg.closed_trades) : "—"} />
        <Stat label="Win rate" value={agg?.win_rate_pct != null ? `${agg.win_rate_pct}%` : "—"} />
        <Stat label="Open positions" value={agg ? String(openPositions.length) : "—"} />
        <Stat label="Strategy version" value={strat?.version ? `v${strat.version}` : "—"} accent />
      </div>

      {/* Log + P&L */}
      <div className="grid lg:grid-cols-2 gap-5">
        {/* Matrix log */}
        <div className="ghost-border bg-black/60 flex flex-col min-h-[320px]">
          <div className="flex items-center gap-2 px-4 py-2 border-b border-primary-fixed/15">
            <Radio size={13} className="text-primary-fixed" />
            <span className="font-mono text-[10px] font-bold tracking-[0.2em] uppercase text-primary-fixed">Agent feed</span>
          </div>
          <div
            ref={logRef}
            onScroll={(e) => {
              const el = e.currentTarget;
              stickToBottom.current = el.scrollHeight - el.scrollTop - el.clientHeight < 40;
            }}
            className="flex-1 overflow-y-auto px-4 py-3 font-mono text-[11px] leading-relaxed text-primary-fixed/90 max-h-[420px]"
          >
            {logLines.length === 0 ? (
              <span className="text-on-surface-variant">connecting to agent…</span>
            ) : (
              logLines.map((l, i) => <div key={i} className="whitespace-pre-wrap break-all">{l}</div>)
            )}
          </div>
        </div>

        {/* P&L curve */}
        <div className="ghost-border p-4 min-h-[320px] flex flex-col">
          <span className="font-mono text-[10px] font-bold tracking-[0.2em] uppercase text-on-surface-variant mb-3">
            Cumulative P&L — closed trades
          </span>
          {curve.length > 1 ? (
            <ResponsiveContainer width="100%" height={300}>
              <AreaChart data={curve} margin={{ top: 4, right: 8, bottom: 0, left: 0 }}>
                <defs>
                  <linearGradient id="pnlFill" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="0%" stopColor="#00ffb2" stopOpacity={0.25} />
                    <stop offset="100%" stopColor="#00ffb2" stopOpacity={0} />
                  </linearGradient>
                </defs>
                <XAxis dataKey="time" hide />
                <YAxis tick={{ fill: "#9aa5a0", fontSize: 10, fontFamily: "monospace" }} width={56}
                       tickFormatter={(v: number) => `$${v}`} />
                <Tooltip
                  contentStyle={{ background: "#0a0f0d", border: "1px solid rgba(0,255,178,0.25)", fontFamily: "monospace", fontSize: 11 }}
                  labelFormatter={(l) => new Date(String(l)).toLocaleString()}
                  formatter={(v) => [`$${v}`, "cum P&L"]}
                />
                <Area type="monotone" dataKey="cum_pnl_usd" stroke="#00ffb2" strokeWidth={1.5} fill="url(#pnlFill)" />
              </AreaChart>
            </ResponsiveContainer>
          ) : (
            <span className="font-mono text-xs text-on-surface-variant m-auto">no closed trades in window</span>
          )}
        </div>
      </div>

      {/* Open positions */}
      {openPositions.length > 0 && (
        <div className="ghost-border p-4">
          <span className="font-mono text-[10px] font-bold tracking-[0.2em] uppercase text-on-surface-variant">Open positions</span>
          <div className="mt-2 grid md:grid-cols-3 gap-3">
            {openPositions.slice(0, 9).map((p, i) => (
              <div key={`${p.trade_id}-${i}`} className="border border-primary-fixed/20 px-3 py-2 font-mono text-xs">
                <div className="font-bold text-primary-fixed">{p.symbol}</div>
                <div className="text-on-surface-variant">entry ${p.entry_price?.toLocaleString()} · SL {strat?.stop_loss_pct}% · TP {strat?.take_profit_pct}%</div>
                <div className="text-on-surface-variant">{p.entry_time ? new Date(p.entry_time).toLocaleString() : ""}</div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Trade tape + strategy evolution */}
      <div className="grid lg:grid-cols-2 gap-5">
        <div className="ghost-border p-4 overflow-x-auto">
          <div className="flex items-center gap-2 mb-3">
            <Activity size={13} className="text-primary-fixed" />
            <span className="font-mono text-[10px] font-bold tracking-[0.2em] uppercase text-on-surface-variant">Trade tape</span>
          </div>
          <table className="w-full font-mono text-[11px]">
            <thead>
              <tr className="text-on-surface-variant text-left">
                <th className="py-1 pr-3">Closed</th><th className="pr-3">Pair</th>
                <th className="pr-3">Entry</th><th className="pr-3">Exit</th>
                <th className="pr-3">P&L</th><th>Reason</th>
              </tr>
            </thead>
            <tbody>
              {closedTrades.slice(0, 25).map((t, i) => (
                <tr key={`${t.trade_id}-${i}`} className="border-t border-outline-variant/15">
                  <td className="py-1.5 pr-3 text-on-surface-variant">{t.exit_time ? new Date(t.exit_time).toLocaleDateString() : "—"}</td>
                  <td className="pr-3">{t.symbol}</td>
                  <td className="pr-3">${t.entry_price?.toLocaleString()}</td>
                  <td className="pr-3">${t.exit_price?.toLocaleString()}</td>
                  <td className={`pr-3 font-bold ${(t.pnl_pct ?? 0) >= 0 ? "text-primary-fixed" : "text-red-400"}`}>
                    {(t.pnl_pct ?? 0) >= 0 ? "+" : ""}{t.pnl_pct?.toFixed(2)}%
                  </td>
                  <td className="text-on-surface-variant">{t.exit_reason?.replace(/_/g, " ")}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        <div className="ghost-border p-4">
          <div className="flex items-center gap-2 mb-3">
            <GitBranch size={13} className="text-primary-fixed" />
            <span className="font-mono text-[10px] font-bold tracking-[0.2em] uppercase text-on-surface-variant">
              Strategy evolution — the agent rewrites itself
            </span>
          </div>
          <div className="flex flex-col gap-3 max-h-[360px] overflow-y-auto pr-1">
            {reflections.length === 0 ? (
              <span className="font-mono text-xs text-on-surface-variant">no reflections yet</span>
            ) : (
              reflections.map((r, i) => (
                <div key={i} className="border-l-2 border-primary-fixed/40 pl-3 font-mono text-[11px]">
                  <div className="text-primary-fixed font-bold">
                    {r.version ? `v${r.version}` : ""} {r.variable ? `· ${r.variable}: ${String(r.old_value)} → ${String(r.new_value)}` : r.change || ""}
                    {r.mode ? <span className="text-on-surface-variant font-normal"> ({String(r.mode)})</span> : null}
                  </div>
                  {(r.reasoning || r.hypothesis) && (
                    <div className="text-on-surface-variant mt-0.5 leading-relaxed">{String(r.reasoning || r.hypothesis)}</div>
                  )}
                  {r.timestamp && <div className="text-on-surface-variant/60 mt-0.5">{new Date(String(r.timestamp)).toLocaleString()}</div>}
                </div>
              ))
            )}
          </div>
        </div>
      </div>

      <p className="font-mono text-[10px] text-on-surface-variant leading-relaxed">
        Hermes is an autonomous PAPER-trading research agent. No real capital is deployed. Nothing on this page is
        investment advice. QuantAlpha is a research tool, not a SEBI-registered investment advisor.
      </p>
    </div>
  );
}

function Stat({ label, value, tone, accent }: { label: string; value: string; tone?: "pos" | "neg"; accent?: boolean }) {
  return (
    <div className="ghost-border px-4 py-3">
      <div className="font-mono text-[9px] tracking-[0.15em] uppercase text-on-surface-variant">{label}</div>
      <div className={`font-mono text-lg font-bold mt-1 ${
        tone === "pos" ? "text-primary-fixed" : tone === "neg" ? "text-red-400" : accent ? "text-primary-fixed" : ""
      }`}>{value}</div>
    </div>
  );
}

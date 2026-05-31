"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { authedApi } from "@/lib/api";
import type { AnalyticsDashboard } from "@/lib/types";
import GlassPanel from "@/components/ui/GlassPanel";
import GradientButton from "@/components/ui/GradientButton";

type Period = "24h" | "7d" | "30d";

export default function AnalyticsDashboardPage() {
  const [data, setData] = useState<AnalyticsDashboard | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [period, setPeriod] = useState<Period>("7d");
  const [authed, setAuthed] = useState<boolean | null>(null);

  useEffect(() => {
    authedApi.me()
      .then((u) => setAuthed(u.tier === "pro" || u.tier === "api"))
      .catch(() => setAuthed(false));
  }, []);

  useEffect(() => {
    if (authed !== true) return;
    setLoading(true);
    authedApi.getAnalyticsDashboard(period)
      .then(setData)
      .catch((e) => setError(e instanceof Error ? e.message : "Failed to load analytics"))
      .finally(() => setLoading(false));
  }, [period, authed]);

  if (authed === null) {
    return <div className="min-h-screen bg-[#0a0a0f] flex items-center justify-center text-on-surface-variant">Loading...</div>;
  }

  if (authed === false) {
    return (
      <div className="min-h-screen bg-[#0a0a0f] flex items-center justify-center p-4">
        <GlassPanel className="max-w-md text-center p-8">
          <h2 className="font-headline text-xl font-bold text-on-surface">Admin Access Required</h2>
          <p className="mt-2 text-on-surface-variant text-sm">
            This dashboard is only available to Pro and API tier users.
          </p>
          <Link href="/pricing" className="mt-6 inline-block">
            <GradientButton>Upgrade to Pro</GradientButton>
          </Link>
        </GlassPanel>
      </div>
    );
  }

  if (loading) {
    return <div className="min-h-screen bg-[#0a0a0f] flex items-center justify-center text-on-surface-variant">Loading analytics...</div>;
  }

  if (error || !data) {
    return <div className="min-h-screen bg-[#0a0a0f] flex items-center justify-center text-red-400">{error || "No data"}</div>;
  }

  const { summary, events_by_type, top_shared_tickers, conversion_funnel } = data;

  const maxEventType = Math.max(...Object.values(events_by_type), 1);

  return (
    <div className="min-h-screen bg-[#0a0a0f] text-on-surface">
      <div className="mx-auto max-w-6xl px-4 py-8 space-y-6">
        <div className="flex items-center justify-between">
          <h1 className="font-headline text-2xl font-bold">Analytics Dashboard</h1>
          <div className="flex gap-2">
            {(["24h", "7d", "30d"] as Period[]).map((p) => (
              <button
                key={p}
                onClick={() => setPeriod(p)}
                className={`rounded-lg px-3 py-1.5 text-sm font-medium transition-colors ${
                  period === p ? "bg-accent text-surface-low" : "bg-surface-high text-on-surface-variant hover:bg-surface-higher"
                }`}
              >
                {p}
              </button>
            ))}
          </div>
        </div>

        {/* Summary Cards */}
        <div className="grid gap-4 md:grid-cols-4">
          <GlassPanel className="p-5">
            <div className="text-sm text-on-surface-variant">Total Events</div>
            <div className="mt-1 text-3xl font-bold font-mono">{summary.total_events.toLocaleString()}</div>
          </GlassPanel>
          <GlassPanel className="p-5">
            <div className="text-sm text-on-surface-variant">Shares Created</div>
            <div className="mt-1 text-3xl font-bold font-mono text-accent">{summary.total_shares_created.toLocaleString()}</div>
          </GlassPanel>
          <GlassPanel className="p-5">
            <div className="text-sm text-on-surface-variant">Share Views</div>
            <div className="mt-1 text-3xl font-bold font-mono">{summary.total_share_views.toLocaleString()}</div>
          </GlassPanel>
          <GlassPanel className="p-5">
            <div className="text-sm text-on-surface-variant">Unique Users</div>
            <div className="mt-1 text-3xl font-bold font-mono">{summary.unique_active_users.toLocaleString()}</div>
          </GlassPanel>
        </div>

        {/* Conversion Funnel */}
        <GlassPanel className="p-5">
          <h3 className="font-headline text-lg font-bold mb-4">Conversion Funnel</h3>
          <div className="flex items-center gap-4 text-sm">
            <div className="flex-1 rounded-lg bg-accent/10 p-3 text-center">
              <div className="text-2xl font-bold font-mono text-accent">{conversion_funnel.shares_created}</div>
              <div className="text-on-surface-variant mt-1">Shares Created</div>
            </div>
            <div className="text-on-surface-variant">→</div>
            <div className="flex-1 rounded-lg bg-blue-400/10 p-3 text-center">
              <div className="text-2xl font-bold font-mono text-blue-400">{conversion_funnel.shares_viewed}</div>
              <div className="text-on-surface-variant mt-1">Shares Viewed</div>
            </div>
            <div className="text-on-surface-variant">→</div>
            <div className="flex-1 rounded-lg bg-green-400/10 p-3 text-center">
              <div className="text-2xl font-bold font-mono text-green-400">{conversion_funnel.signups_from_share}</div>
              <div className="text-on-surface-variant mt-1">Signups from Share</div>
            </div>
          </div>
          {conversion_funnel.shares_created > 0 && (
            <div className="mt-3 text-sm text-on-surface-variant">
              Viral coefficient: <span className="font-bold text-accent">
                {(conversion_funnel.signups_from_share / conversion_funnel.shares_created * 100).toFixed(1)}%
              </span>
            </div>
          )}
        </GlassPanel>

        {/* Events by Type */}
        <GlassPanel className="p-5">
          <h3 className="font-headline text-lg font-bold mb-4">Events by Type</h3>
          <div className="space-y-2">
            {Object.entries(events_by_type)
              .sort(([, a], [, b]) => b - a)
              .slice(0, 10)
              .map(([type, count]) => (
                <div key={type} className="flex items-center gap-3">
                  <div className="w-36 text-sm text-on-surface-variant truncate">{type}</div>
                  <div className="flex-1">
                    <div
                      className="h-6 rounded bg-accent/30"
                      style={{ width: `${Math.max((count / maxEventType) * 100, 2)}%` }}
                    />
                  </div>
                  <div className="w-16 text-right font-mono text-sm">{count}</div>
                </div>
              ))}
          </div>
        </GlassPanel>

        {/* Top Shared Tickers */}
        {top_shared_tickers.length > 0 && (
          <GlassPanel className="p-5">
            <h3 className="font-headline text-lg font-bold mb-4">Top Shared Tickers</h3>
            <table className="w-full text-sm">
              <thead>
                <tr className="text-on-surface-variant border-b border-ghost-border">
                  <th className="py-2 text-left">Ticker</th>
                  <th className="py-2 text-right">Shares</th>
                  <th className="py-2 text-right">Views</th>
                </tr>
              </thead>
              <tbody>
                {top_shared_tickers.slice(0, 10).map((t) => (
                  <tr key={t.ticker} className="border-b border-ghost-border/30">
                    <td className="py-2 font-mono font-bold">{t.ticker}</td>
                    <td className="py-2 text-right text-accent">{t.shares}</td>
                    <td className="py-2 text-right">{t.views}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </GlassPanel>
        )}
      </div>
    </div>
  );
}
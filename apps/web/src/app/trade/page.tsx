"use client";

import { useState, useEffect, useCallback } from "react";
import type { TradeSignal, TradeStrategy, CalibrationReport, BacktestResponse } from "@/lib/types";
import { tradeApi } from "@/lib/api";
import SignalFeed from "@/components/trade/SignalFeed";
import StrategyCard from "@/components/trade/StrategyCard";
import RiskDashboard from "@/components/trade/RiskDashboard";
import PositionSizer from "@/components/trade/PositionSizer";
import CalibrationPanel from "@/components/trade/CalibrationPanel";
import HistoricalBacktest from "@/components/trade/HistoricalBacktest";
import GlassPanel from "@/components/ui/GlassPanel";
import GradientButton from "@/components/ui/GradientButton";
import {
  TrendingUp,
  RefreshCw,
  DollarSign,
  Globe,
  Loader2,
  Play,
} from "lucide-react";

export default function TradePage() {
  const [market, setMarket] = useState<"US" | "IN">("US");
  const [strategyId, setStrategyId] = useState("momentum_breakout");
  const [bankroll, setBankroll] = useState(10000);
  const [strategies, setStrategies] = useState<TradeStrategy[]>([]);
  const [signals, setSignals] = useState<TradeSignal[]>([]);
  const [calibration, setCalibration] = useState<CalibrationReport | null>(null);
  const [loading, setLoading] = useState(true);
  const [strategiesLoading, setStrategiesLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [marketOpen, setMarketOpen] = useState<boolean | null>(null);
  const [backtestResult, setBacktestResult] = useState<BacktestResponse | null>(null);
  const [backtestRunning, setBacktestRunning] = useState(false);

  const fetchStrategies = useCallback(async () => {
    try {
      setStrategiesLoading(true);
      const res = await tradeApi.getStrategies();
      setStrategies(res.strategies);
    } catch {
      // use defaults
    } finally {
      setStrategiesLoading(false);
    }
  }, []);

  const fetchSignals = useCallback(async () => {
    try {
      setLoading(true);
      setError(null);
      const res = await tradeApi.getSignals(market, strategyId, bankroll);
      setSignals(res.signals);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load signals");
    } finally {
      setLoading(false);
    }
  }, [market, strategyId, bankroll]);

  const fetchCalibration = useCallback(async () => {
    try {
      const res = await tradeApi.getCalibration(90, market);
      setCalibration(res);
    } catch {
      // no history yet
    }
  }, [market]);

  useEffect(() => {
    fetchStrategies();
  }, [fetchStrategies]);

  useEffect(() => {
    fetchSignals();
    fetchCalibration();
  }, [fetchSignals, fetchCalibration]);

  // Check market status on mount + poll every 60s
  useEffect(() => {
    async function check() {
      try {
        const res = await tradeApi.getMarketStatus();
        setMarketOpen(res.is_open);
      } catch {
        setMarketOpen(false);
      }
    }
    check();
    const interval = setInterval(check, 60_000);
    return () => clearInterval(interval);
  }, []);

  async function runBacktest() {
    setBacktestRunning(true);
    try {
      const res = await tradeApi.runBacktest({
        market,
        years: 20,
        initial_capital: bankroll,
        strategy_id: strategyId,
      });
      setBacktestResult(res);
    } catch {
      // silent
    } finally {
      setBacktestRunning(false);
    }
  }

  return (
    <div className="max-w-7xl mx-auto px-4 py-6 space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="text-2xl font-headline font-bold text-on-surface flex items-center gap-3">
            <TrendingUp size={28} className="text-primary" />
            Trade Signals
          </h1>
          <p className="text-sm text-on-surface-variant mt-1">
            AI-powered trade signals with Kelly position sizing and risk controls
          </p>
        </div>

        <div className="flex items-center gap-2">
          {/* Market toggle */}
          <div className="flex rounded-lg bg-surface-high border border-ghost-border overflow-hidden">
            {(["US", "IN"] as const).map((m) => (
              <button
                key={m}
                onClick={() => setMarket(m)}
                className={`px-3 py-1.5 text-xs font-medium transition-colors ${
                  market === m
                    ? "bg-primary/15 text-primary"
                    : "text-on-surface-variant hover:text-on-surface"
                }`}
              >
                {m === "US" ? "US" : "India"}
              </button>
            ))}
          </div>

          <GradientButton onClick={fetchSignals} disabled={loading} size="sm">
            <RefreshCw size={14} className={loading ? "animate-spin" : ""} />
            Refresh
          </GradientButton>
        </div>
      </div>

      {/* Error banner */}
      {error && (
        <div className="rounded-xl bg-rose-500/10 border border-rose-500/25 px-4 py-3 text-sm text-rose-400">
          {error}
        </div>
      )}

      {/* Market Status & Historical Backtest */}
      <section>
        <GlassPanel>
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <div className={`w-2 h-2 rounded-full ${marketOpen ? "bg-green-400" : "bg-amber-400"}`} />
              <span className="text-sm text-on-surface">
                {marketOpen === null
                  ? "Checking market status..."
                  : marketOpen
                  ? "Market Open — Live Signals Active"
                  : "Market Closed — Historical Backtest Available"}
              </span>
            </div>
            {!marketOpen && (
              <GradientButton onClick={runBacktest} disabled={backtestRunning} size="sm">
                <Play size={12} />
                {backtestRunning ? "Running..." : "Run 20-Year Backtest"}
              </GradientButton>
            )}
          </div>

          {!marketOpen && !backtestResult && !backtestRunning && (
            <p className="mt-3 text-xs text-on-surface-variant">
              Running historical backtest (2006-2026) on FMP data — simulated trades until market opens at 9:30 AM ET
            </p>
          )}

          {backtestResult && (
            <div className="mt-4">
              <HistoricalBacktest data={backtestResult} />
            </div>
          )}
        </GlassPanel>
      </section>

      {/* Strategy selector */}
      <section>
        <h2 className="text-sm font-semibold text-on-surface-variant uppercase tracking-wide mb-3">
          Strategy
        </h2>
        <StrategyCard
          strategies={strategies}
          selectedId={strategyId}
          onSelect={setStrategyId}
          loading={strategiesLoading}
        />
      </section>

      {/* Main grid: signals + sidebar */}
      <div className="grid grid-cols-1 lg:grid-cols-4 gap-6">
        {/* Signal feed */}
        <div className="lg:col-span-3">
          <div className="flex items-center justify-between mb-3">
            <h2 className="text-sm font-semibold text-on-surface-variant uppercase tracking-wide">
              Signals ({signals.length})
            </h2>

            {/* Bankroll input */}
            <div className="flex items-center gap-2">
              <span className="text-[10px] text-on-surface-variant flex items-center gap-1">
                <DollarSign size={10} /> Bankroll
              </span>
              <input
                type="number"
                value={bankroll}
                onChange={(e) => setBankroll(Number(e.target.value) || 0)}
                className="w-24 rounded-lg bg-surface-high border border-ghost-border px-2 py-1 text-xs font-mono text-on-surface focus:border-primary/40 focus:outline-none"
              />
            </div>
          </div>

          <SignalFeed signals={signals} loading={loading} />
        </div>

        {/* Sidebar */}
        <div className="space-y-4">
          <RiskDashboard calibration={calibration} loading={loading} />
          <PositionSizer />
          <CalibrationPanel report={calibration} loading={loading} lookbackDays={90} />
        </div>
      </div>
    </div>
  );
}

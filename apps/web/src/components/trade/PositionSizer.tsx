"use client";

import { useState } from "react";
import GlassPanel from "@/components/ui/GlassPanel";
import { Calculator, DollarSign, Percent, TrendingUp } from "lucide-react";

export default function PositionSizer() {
  const [bankroll, setBankroll] = useState(10000);
  const [edge, setEdge] = useState(15);
  const [kellyFraction, setKellyFraction] = useState(25);
  const [maxBet, setMaxBet] = useState(5000);

  const edgeDecimal = edge / 100;
  const kellyDecimal = kellyFraction / 100;
  const rawBet = bankroll * edgeDecimal * kellyDecimal;
  const bet = Math.min(rawBet, maxBet);
  const betPct = bankroll > 0 ? (bet / bankroll) * 100 : 0;
  const fullKelly = bankroll * edgeDecimal;
  const fullKellyPct = bankroll > 0 ? (fullKelly / bankroll) * 100 : 0;

  return (
    <GlassPanel>
      <h3 className="text-sm font-semibold text-on-surface flex items-center gap-2 mb-3">
        <Calculator size={16} className="text-primary" />
        Position Sizer
      </h3>

      <div className="space-y-3">
        {/* Bankroll */}
        <div>
          <label className="text-[10px] text-on-surface-variant flex items-center gap-1 mb-1">
            <DollarSign size={10} /> Bankroll
          </label>
          <input
            type="number"
            value={bankroll}
            onChange={(e) => setBankroll(Number(e.target.value) || 0)}
            className="w-full rounded-lg bg-surface-high border border-ghost-border px-3 py-1.5 text-sm font-mono text-on-surface focus:border-primary/40 focus:outline-none"
          />
        </div>

        {/* Edge */}
        <div>
          <label className="text-[10px] text-on-surface-variant flex items-center gap-1 mb-1">
            <TrendingUp size={10} /> Edge ({edge}%)
          </label>
          <input
            type="range"
            min={1}
            max={100}
            value={edge}
            onChange={(e) => setEdge(Number(e.target.value))}
            className="w-full accent-primary"
          />
        </div>

        {/* Kelly Fraction */}
        <div>
          <label className="text-[10px] text-on-surface-variant flex items-center gap-1 mb-1">
            <Percent size={10} /> Kelly Fraction ({kellyFraction}%)
          </label>
          <input
            type="range"
            min={5}
            max={100}
            value={kellyFraction}
            onChange={(e) => setKellyFraction(Number(e.target.value))}
            className="w-full accent-primary"
          />
        </div>

        {/* Max Bet */}
        <div>
          <label className="text-[10px] text-on-surface-variant flex items-center gap-1 mb-1">
            <DollarSign size={10} /> Max Bet
          </label>
          <input
            type="number"
            value={maxBet}
            onChange={(e) => setMaxBet(Number(e.target.value) || 0)}
            className="w-full rounded-lg bg-surface-high border border-ghost-border px-3 py-1.5 text-sm font-mono text-on-surface focus:border-primary/40 focus:outline-none"
          />
        </div>

        {/* Result */}
        <div className="rounded-xl bg-primary/5 border border-primary/20 p-3">
          <div className="flex items-center justify-between">
            <span className="text-xs text-on-surface-variant">Kelly Bet</span>
            <span className="text-lg font-mono font-bold text-primary">
              ${bet.toFixed(2)}
            </span>
          </div>
          <div className="flex items-center justify-between mt-1">
            <span className="text-[10px] text-on-surface-variant">
              Full Kelly: ${fullKelly.toFixed(2)} ({fullKellyPct.toFixed(1)}%)
            </span>
            <span className="text-[10px] text-on-surface-variant">{betPct.toFixed(1)}% of bankroll</span>
          </div>
          {rawBet > maxBet && (
            <div className="mt-1 text-[10px] text-amber-400">
              Capped at max bet (${maxBet})
            </div>
          )}
        </div>
      </div>
    </GlassPanel>
  );
}

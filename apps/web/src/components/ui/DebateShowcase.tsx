"use client";

import { useState } from "react";

const AGENTS = [
  { name: "MACRO", role: "Interest rates, GDP, Fed policy", icon: "🏛️", stance: "bullish" },
  { name: "FUNDAMENTAL", role: "Earnings, margins, Piotroski F-Score", icon: "📊", stance: "bullish" },
  { name: "TECHNICAL", role: "Price action, RSI, moving averages", icon: "📈", stance: "bearish" },
  { name: "SENTIMENT", role: "News, insider activity, social buzz", icon: "📰", stance: "neutral" },
  { name: "GEOPOLITICAL", role: "Trade policy, regulation, global risk", icon: "🌍", stance: "cautious" },
  { name: "ADVERSARIAL", role: "Challenges every bull thesis", icon: "⚡", stance: "bearish" },
];

const STANCE_COLORS: Record<string, string> = {
  bullish: "text-tertiary bg-tertiary/10",
  bearish: "text-error bg-error/10",
  neutral: "text-primary bg-primary/10",
  cautious: "text-secondary bg-secondary/10",
};

export default function DebateShowcase() {
  const [hoveredAgent, setHoveredAgent] = useState<string | null>(null);

  return (
    <div className="relative">
      {/* Agent ring */}
      <div className="grid grid-cols-2 md:grid-cols-3 gap-3 max-w-3xl mx-auto">
        {AGENTS.map((agent) => {
          const stanceClass = STANCE_COLORS[agent.stance];
          const isHovered = hoveredAgent === agent.name;
          return (
            <div
              key={agent.name}
              onMouseEnter={() => setHoveredAgent(agent.name)}
              onMouseLeave={() => setHoveredAgent(null)}
              className={`rounded-xl p-4 transition-all duration-200 ghost-border ${
                isHovered ? "scale-105 bg-surface-high" : "bg-surface-low/40"
              } ${stanceClass}`}
            >
              <div className="flex items-center gap-2 mb-1">
                <span className="text-lg">{agent.icon}</span>
                <span className="font-semibold text-on-surface text-sm">{agent.name}</span>
              </div>
              <p className="text-xs text-on-surface-variant leading-relaxed">{agent.role}</p>
            </div>
          );
        })}
      </div>

      {/* Head Analyst */}
      <div className="mt-4 text-center">
        <div className="inline-flex items-center gap-2 rounded-xl bg-primary/10 ghost-border px-6 py-3">
          <span className="text-lg">⚖️</span>
          <span className="font-semibold text-on-surface">HEAD ANALYST</span>
          <span className="text-xs text-on-surface-variant">synthesizes the verdict</span>
        </div>
      </div>
    </div>
  );
}
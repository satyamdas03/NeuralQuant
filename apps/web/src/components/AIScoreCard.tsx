"use client";
import RegimeBadge from "@/components/ui/RegimeBadge";
import type { AIScore } from "@/lib/types";

function ScoreRing({ score }: { score: number }) {
  const pct = score / 10;
  const circumference = 2 * Math.PI * 45;
  const dash = pct * circumference;
  const color = score >= 7 ? "#4edea3" : score >= 4 ? "#bdf4ff" : "#ffb4ab";

  return (
    <svg width="120" height="120" viewBox="0 0 120 120" className="rotate-[-90deg]">
      <circle cx="60" cy="60" r="45" fill="none" stroke="var(--surface-container)" strokeWidth="10" />
      <circle
        cx="60" cy="60" r="45" fill="none"
        stroke={color} strokeWidth="10"
        strokeDasharray={`${dash} ${circumference}`}
        strokeLinecap="round"
        style={{ transition: "stroke-dasharray 0.8s ease" }}
      />
      <text
        x="60" y="60" textAnchor="middle" dominantBaseline="central"
        fontSize="28" fontWeight="bold" fill="var(--on-surface)"
        style={{ transform: "rotate(90deg)", transformOrigin: "60px 60px" }}
      >
        {score}
      </text>
    </svg>
  );
}

export function AIScoreCard({ data }: { data: AIScore }) {
  return (
    <div className="p-6 rounded-2xl ghost-border bg-surface-low/60 backdrop-blur-sm">
      <div className="flex items-start justify-between mb-4">
        <div>
          <h2 className="font-headline text-3xl font-bold text-on-surface">{data.ticker}</h2>
          <p className="text-sm text-on-surface-variant mt-1">{data.market} Market</p>
        </div>
        <RegimeBadge label={data.regime_label} />
      </div>

      <div className="flex items-center gap-8">
        <ScoreRing score={data.score_1_10} />
        <div className="flex flex-col gap-1">
          <p className="font-headline text-4xl font-bold text-on-surface">{data.score_1_10}<span className="text-xl text-on-surface-variant">/10</span></p>
          <p className="text-on-surface-variant text-sm">AI Score</p>
          <span className={`text-xs mt-1 font-medium ${
            data.confidence === "high" ? "text-tertiary" :
            data.confidence === "medium" ? "text-secondary" : "text-error"
          }`}>
            {data.confidence.toUpperCase()} CONFIDENCE
          </span>
        </div>
      </div>

      <p className="text-xs text-on-surface-variant mt-4">
        Updated {new Date(data.last_updated).toLocaleString()}
      </p>
    </div>
  );
}
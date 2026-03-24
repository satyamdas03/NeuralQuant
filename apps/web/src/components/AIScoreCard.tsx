"use client";
import { RegimeBadge } from "./RegimeBadge";
import type { AIScore } from "@/lib/types";

function ScoreRing({ score }: { score: number }) {
  const pct = score / 10;
  const circumference = 2 * Math.PI * 45;
  const dash = pct * circumference;
  const color = score >= 7 ? "#22c55e" : score >= 4 ? "#eab308" : "#ef4444";

  return (
    <svg width="120" height="120" viewBox="0 0 120 120" className="rotate-[-90deg]">
      <circle cx="60" cy="60" r="45" fill="none" stroke="#1f2937" strokeWidth="10" />
      <circle
        cx="60" cy="60" r="45" fill="none"
        stroke={color} strokeWidth="10"
        strokeDasharray={`${dash} ${circumference}`}
        strokeLinecap="round"
        style={{ transition: "stroke-dasharray 0.8s ease" }}
      />
      <text
        x="60" y="60" textAnchor="middle" dominantBaseline="central"
        fontSize="28" fontWeight="bold" fill="white"
        style={{ transform: "rotate(90deg)", transformOrigin: "60px 60px" }}
      >
        {score}
      </text>
    </svg>
  );
}

export function AIScoreCard({ data }: { data: AIScore }) {
  return (
    <div className="p-6 rounded-2xl border border-gray-800 bg-gray-900/60 backdrop-blur">
      <div className="flex items-start justify-between mb-4">
        <div>
          <h2 className="text-3xl font-bold">{data.ticker}</h2>
          <p className="text-gray-400 text-sm mt-1">{data.market} Market</p>
        </div>
        <RegimeBadge label={data.regime_label} />
      </div>

      <div className="flex items-center gap-8">
        <ScoreRing score={data.score_1_10} />
        <div className="flex flex-col gap-1">
          <p className="text-4xl font-bold">{data.score_1_10}<span className="text-xl text-gray-500">/10</span></p>
          <p className="text-gray-400 text-sm">AI Score</p>
          <span className={`text-xs mt-1 ${
            data.confidence === "high" ? "text-green-400" :
            data.confidence === "medium" ? "text-yellow-400" : "text-red-400"
          }`}>
            {data.confidence.toUpperCase()} confidence
          </span>
        </div>
      </div>

      <p className="text-xs text-gray-600 mt-4">
        Updated {new Date(data.last_updated).toLocaleString()}
      </p>
    </div>
  );
}

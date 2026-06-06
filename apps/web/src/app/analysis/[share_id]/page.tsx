"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import { api } from "@/lib/api";
import { trackEvent, EVENT, trackApiEvent } from "@/lib/analytics";
import GlassPanel from "@/components/ui/GlassPanel";
import GradientButton from "@/components/ui/GradientButton";
import { TrendingUp, TrendingDown, Minus, Eye, ChevronDown, ChevronUp, ArrowRight, AlertTriangle } from "lucide-react";

type AgentOutput = {
  agent: string;
  stance: string;
  conviction: string;
  thesis: string;
  key_points?: string[];
};

export default function ShareAnalysisPage() {
  const params = useParams();
  const shareId = params.share_id as string;
  const [data, setData] = useState<Record<string, unknown> | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [expandedAgents, setExpandedAgents] = useState<Set<string>>(new Set());

  useEffect(() => {
    if (!shareId) return;
    setLoading(true);
    api.getShareAnalysis(shareId)
      .then((result) => {
        setData(result);
        trackEvent(EVENT.ANALYSIS_VIEWED, { share_id: shareId, ticker: String(result.ticker || "") });
        trackApiEvent("analysis_viewed", { share_id: shareId }).catch(() => {});
      })
      .catch((e) => setError(e instanceof Error ? e.message : "Analysis not found"))
      .finally(() => setLoading(false));
  }, [shareId]);

  if (loading) {
    return (
      <div className="min-h-screen bg-[#0a0a0f] flex items-center justify-center">
        <div className="text-center">
          <div className="inline-block h-8 w-8 animate-spin rounded-full border-2 border-accent border-t-transparent" />
          <p className="mt-4 text-on-surface-variant">Loading analysis...</p>
        </div>
      </div>
    );
  }

  if (error || !data) {
    return (
      <div className="min-h-screen bg-[#0a0a0f] flex items-center justify-center p-4">
        <GlassPanel className="max-w-md text-center p-8">
          <AlertTriangle className="mx-auto mb-4 h-12 w-12 text-red-400" />
          <h2 className="font-headline text-xl font-bold text-on-surface">Analysis Not Found</h2>
          <p className="mt-2 text-on-surface-variant">
            This analysis link may have expired or doesn&apos;t exist.
          </p>
          <Link href="/" className="mt-6 inline-block">
            <GradientButton>Go to NeuralQuant</GradientButton>
          </Link>
        </GlassPanel>
      </div>
    );
  }

  const ticker = String(data.ticker || "");
  const market = String(data.market || "US");
  const verdict = String(data.verdict || "HOLD");
  const score = Number(data.score ?? 5);
  const analystResponse = (data.analyst_response || {}) as Record<string, unknown>;
  const viewCount = Number(data.view_count ?? 0);

  const headVerdict = String(analystResponse.head_analyst_verdict || verdict);
  const investmentThesis = String(analystResponse.investment_thesis || "");
  const bullCase = String(analystResponse.bull_case || "");
  const bearCase = String(analystResponse.bear_case || "");
  const riskFactors = (analystResponse.risk_factors || []) as string[];
  const agentOutputs = (analystResponse.agent_outputs || []) as AgentOutput[];
  const consensusScore = Number(analystResponse.consensus_score ?? score) / 10;

  const verdictColor = headVerdict.includes("BUY") || headVerdict === "BULL"
    ? "text-green-400"
    : headVerdict.includes("SELL") || headVerdict === "BEAR"
    ? "text-red-400"
    : "text-yellow-400";

  const verdictBg = headVerdict.includes("BUY") || headVerdict === "BULL"
    ? "bg-green-400/10 border-green-400/30"
    : headVerdict.includes("SELL") || headVerdict === "BEAR"
    ? "bg-red-400/10 border-red-400/30"
    : "bg-yellow-400/10 border-yellow-400/30";

  const VerdictIcon = headVerdict.includes("BUY") || headVerdict === "BULL"
    ? TrendingUp
    : headVerdict.includes("SELL") || headVerdict === "BEAR"
    ? TrendingDown
    : Minus;

  const toggleAgent = (name: string) => {
    setExpandedAgents((prev) => {
      const next = new Set(prev);
      if (next.has(name)) next.delete(name);
      else next.add(name);
      return next;
    });
  };

  return (
    <div className="min-h-screen bg-[#0a0a0f] text-on-surface">
      {/* Header */}
      <div className="border-b border-ghost-border bg-surface-high/50 backdrop-blur-sm">
        <div className="mx-auto max-w-3xl px-4 py-4 flex items-center justify-between">
          <Link href="/" className="font-headline text-lg font-bold tracking-tight">
            <span className="text-accent">Neural</span>Quant
          </Link>
          <Link href={`/signup?from_share=${shareId}`} className="text-sm text-on-surface-variant hover:text-accent transition-colors">
            Sign Up Free
          </Link>
        </div>
      </div>

      <main className="mx-auto max-w-3xl px-4 py-8 space-y-6">
        {/* Verdict Hero */}
        <GlassPanel className={`p-6 text-center ${verdictBg} border`}>
          <div className="flex items-center justify-center gap-3 mb-2">
            <span className="font-headline text-3xl font-extrabold tracking-tight">{ticker}</span>
            <VerdictIcon className={`h-8 w-8 ${verdictColor}`} />
          </div>
          <div className={`font-headline text-2xl font-bold ${verdictColor}`}>
            {headVerdict}
          </div>
          <div className="mt-2 text-4xl font-bold font-mono text-on-surface">
            {score.toFixed(1)}<span className="text-lg text-on-surface-variant">/10</span>
          </div>
          <div className="mt-2 flex items-center justify-center gap-4 text-sm text-on-surface-variant">
            <span className="flex items-center gap-1"><Eye className="h-3.5 w-3.5" /> {viewCount} views</span>
            <span>Consensus: {(consensusScore * 10).toFixed(0)}%</span>
          </div>
        </GlassPanel>

        {/* Investment Thesis */}
        {investmentThesis && (
          <GlassPanel className="p-5">
            <h3 className="font-headline text-lg font-bold mb-2">Investment Thesis</h3>
            <p className="text-sm leading-relaxed text-on-surface-variant">{investmentThesis}</p>
          </GlassPanel>
        )}

        {/* Bull / Bear */}
        <div className="grid gap-4 md:grid-cols-2">
          {bullCase && (
            <GlassPanel className="p-5 border-green-400/20">
              <h3 className="font-headline text-lg font-bold text-green-400 mb-2">Bull Case</h3>
              <p className="text-sm text-on-surface-variant">{bullCase}</p>
            </GlassPanel>
          )}
          {bearCase && (
            <GlassPanel className="p-5 border-red-400/20">
              <h3 className="font-headline text-lg font-bold text-red-400 mb-2">Bear Case</h3>
              <p className="text-sm text-on-surface-variant">{bearCase}</p>
            </GlassPanel>
          )}
        </div>

        {/* Risk Factors */}
        {riskFactors.length > 0 && (
          <GlassPanel className="p-5">
            <h3 className="font-headline text-lg font-bold mb-2">Key Risk Factors</h3>
            <ul className="space-y-1">
              {riskFactors.map((rf, i) => (
                <li key={i} className="text-sm text-on-surface-variant flex items-start gap-2">
                  <span className="text-red-400 mt-0.5">•</span> {rf}
                </li>
              ))}
            </ul>
          </GlassPanel>
        )}

        {/* Agent Outputs (Accordion) */}
        {agentOutputs.length > 0 && (
          <GlassPanel className="p-5">
            <h3 className="font-headline text-lg font-bold mb-3">Agent Perspectives</h3>
            <div className="space-y-2">
              {agentOutputs.map((agent) => (
                <div key={agent.agent} className="border border-ghost-border rounded-lg">
                  <button
                    onClick={() => toggleAgent(agent.agent)}
                    className="w-full flex items-center justify-between px-4 py-3 text-sm font-medium text-on-surface hover:bg-surface-higher/50 transition-colors"
                  >
                    <span className="flex items-center gap-2">
                      <span className={`inline-block h-2 w-2 rounded-full ${
                        agent.stance?.toUpperCase().includes("BULL") ? "bg-green-400" :
                        agent.stance?.toUpperCase().includes("BEAR") ? "bg-red-400" :
                        "bg-yellow-400"
                      }`} />
                      <span>{agent.agent}</span>
                      <span className="text-on-surface-variant">({agent.stance}, {agent.conviction})</span>
                    </span>
                    {expandedAgents.has(agent.agent) ? <ChevronUp className="h-4 w-4" /> : <ChevronDown className="h-4 w-4" />}
                  </button>
                  {expandedAgents.has(agent.agent) && (
                    <div className="px-4 pb-3 text-sm text-on-surface-variant">
                      <p>{agent.thesis}</p>
                      {agent.key_points && agent.key_points.length > 0 && (
                        <ul className="mt-2 space-y-1">
                          {agent.key_points.map((kp, i) => (
                            <li key={i} className="flex items-start gap-1.5">
                              <span className="text-on-surface-variant">→</span> {kp}
                            </li>
                          ))}
                        </ul>
                      )}
                    </div>
                  )}
                </div>
              ))}
            </div>
          </GlassPanel>
        )}

        {/* CTA */}
        <div className="text-center py-8 space-y-4">
          <h3 className="font-headline text-xl font-bold">Run your own AI analysis</h3>
          <p className="text-on-surface-variant text-sm">
            NeuralQuant&apos;s 7-agent PARA-DEBATE system analyzes any stock from 7 perspectives simultaneously.
          </p>
          <Link href={`/stocks/${ticker}?market=${market}`}>
            <GradientButton>
              Analyze {ticker} <ArrowRight className="ml-2 h-4 w-4" />
            </GradientButton>
          </Link>
          <p className="text-xs text-on-surface-variant pt-4">
            NeuralQuant is a research tool, not SEBI-registered investment advice.
          </p>
        </div>
      </main>
    </div>
  );
}
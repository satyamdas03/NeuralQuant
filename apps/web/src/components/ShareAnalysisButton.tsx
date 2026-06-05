"use client";

import { useState } from "react";
import { Share2, Link, Check, Loader2, X } from "lucide-react";
import { api } from "@/lib/api";
import { trackEvent, EVENT, trackApiEvent } from "@/lib/analytics";
import type { AnalystResponse } from "@/lib/types";

interface ShareAnalysisButtonProps {
  ticker: string;
  market: string;
  report: AnalystResponse;
  score?: Record<string, unknown> | null;
  meta?: Record<string, unknown> | null;
  sentiment?: Record<string, unknown> | null;
  verdict?: string;
  compositeScore?: number;
}

export default function ShareAnalysisButton({
  ticker,
  market,
  report,
  score,
  meta,
  sentiment,
  verdict,
  compositeScore,
}: ShareAnalysisButtonProps) {
  const [sharing, setSharing] = useState(false);
  const [shared, setShared] = useState(false);
  const [shareUrl, setShareUrl] = useState("");
  const [showDialog, setShowDialog] = useState(false);
  const [copied, setCopied] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleShare = async () => {
    setSharing(true);
    setError(null);
    try {
      const result = await api.createShareAnalysis({
        ticker,
        market,
        analyst_response: report,
        score_data: score || undefined,
        meta_data: meta || undefined,
        sentiment_data: sentiment || undefined,
        verdict: verdict || "HOLD",
        score: compositeScore ?? 5,
      });
      setShareUrl(result.url);
      setShared(true);
      setShowDialog(true);
      trackEvent(EVENT.ANALYSIS_SHARED, { ticker, share_id: result.share_id });
      trackApiEvent("analysis_shared", { ticker, share_id: result.share_id }).catch(() => {});
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to create share link");
    } finally {
      setSharing(false);
    }
  };

  const copyToClipboard = async () => {
    try {
      await navigator.clipboard.writeText(shareUrl);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch {
      // Fallback: select input text
      const input = document.querySelector<HTMLInputElement>("#share-url-input");
      input?.select();
    }
  };

  const nativeShare = async () => {
    if (navigator.share) {
      try {
        await navigator.share({
          title: `${ticker} — AI Analysis | NeuralQuant`,
          text: `Check out this AI-powered analysis of ${ticker}`,
          url: shareUrl,
        });
      } catch {
        // User cancelled or share failed — ignore
      }
    } else {
      copyToClipboard();
    }
  };

  return (
    <>
      <button
        onClick={shared ? () => setShowDialog(true) : handleShare}
        disabled={sharing}
        className="flex items-center gap-2 rounded-lg border border-ghost-border bg-surface-high px-4 py-2 text-sm font-medium text-on-surface transition-colors hover:border-accent/40 hover:bg-surface-higher disabled:opacity-50"
      >
        {sharing ? (
          <Loader2 className="h-4 w-4 animate-spin" />
        ) : (
          <Share2 className="h-4 w-4" />
        )}
        {sharing ? "Sharing..." : shared ? "Share Link" : "Share Analysis"}
      </button>

      {showDialog && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4" onClick={() => setShowDialog(false)}>
          <div
            className="w-full max-w-md rounded-xl border border-ghost-border bg-surface-high p-6 shadow-2xl"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="mb-4 flex items-center justify-between">
              <h3 className="font-headline text-lg font-bold text-on-surface">Share Analysis</h3>
              <button onClick={() => setShowDialog(false)} className="text-on-surface-variant hover:text-on-surface">
                <X className="h-5 w-5" />
              </button>
            </div>

            <p className="mb-4 text-sm text-on-surface-variant">
              Anyone with this link can view the full PARA-DEBATE analysis for{" "}
              <span className="font-semibold text-accent">{ticker}</span> — no login required.
            </p>

            <div className="mb-4 flex items-center gap-2">
              <input
                id="share-url-input"
                type="text"
                readOnly
                value={shareUrl}
                className="flex-1 rounded-lg border border-ghost-border bg-surface-low px-3 py-2 text-sm text-on-surface"
              />
              <button
                onClick={copyToClipboard}
                className="flex items-center gap-1 rounded-lg border border-ghost-border bg-surface-high px-3 py-2 text-sm font-medium text-on-surface transition-colors hover:bg-surface-higher"
              >
                {copied ? <Check className="h-4 w-4 text-green-400" /> : <Link className="h-4 w-4" />}
                {copied ? "Copied!" : "Copy"}
              </button>
            </div>

            {typeof navigator.share === "function" && (
              <button
                onClick={nativeShare}
                className="w-full rounded-lg bg-accent px-4 py-2.5 text-sm font-semibold text-surface-low transition-colors hover:bg-accent/90"
              >
                <Share2 className="mr-2 inline h-4 w-4" />
                Share via...
              </button>
            )}

            {error && (
              <p className="mt-3 text-sm text-red-400">{error}</p>
            )}

            <p className="mt-4 text-xs text-on-surface-variant">
              NeuralQuant is a research tool, not SEBI-registered investment advice.
            </p>
          </div>
        </div>
      )}
    </>
  );
}
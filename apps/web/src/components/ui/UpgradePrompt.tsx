"use client";

import { useState, useEffect, useCallback } from "react";
import Link from "next/link";
import { X, ArrowRight, Zap } from "lucide-react";

/**
 * UpgradePrompt — shows a CTA when the API returns 429 (rate limit)
 * or 402 (payment required).
 *
 * Usage: Call `showUpgrade()` from anywhere via the exported function,
 * or the component auto-detects 429/402 from fetch responses.
 */
let _setUpgradeVisible: ((v: boolean, tier?: string, reason?: string) => void) | null = null;

export function showUpgrade(reason?: string, tier?: string) {
  _setUpgradeVisible?.(true, tier, reason);
}

export default function UpgradePrompt() {
  const [visible, setVisible] = useState(false);
  const [tier, setTier] = useState<string>("investor");
  const [reason, setReason] = useState<string>("");

  useEffect(() => {
    _setUpgradeVisible = setVisible;
    return () => { _setUpgradeVisible = null; };
  }, []);

  // Listen for 429/402 from API responses globally
  useEffect(() => {
    const origFetch = window.fetch;
    window.fetch = async (...args: Parameters<typeof fetch>) => {
      const res = await origFetch(...args);
      if (res.status === 429) {
        setVisible(true);
        setReason("You've reached your daily query limit");
        setTier("investor");
      } else if (res.status === 402) {
        setVisible(true);
        setReason("This feature requires a paid plan");
        setTier("investor");
      }
      return res;
    };
    return () => { window.fetch = origFetch; };
  }, []);

  const dismiss = useCallback(() => setVisible(false), []);

  if (!visible) return null;

  return (
    <div className="fixed inset-0 z-[100] flex items-center justify-center bg-black/60 backdrop-blur-sm">
      <div className="relative max-w-md w-full mx-4 glass border border-border-glow p-8">
        <button
          onClick={dismiss}
          className="absolute top-4 right-4 text-text-muted hover:text-text-primary transition-colors"
          aria-label="Close"
        >
          <X size={20} />
        </button>

        <div className="flex items-center gap-3 mb-4">
          <div className="w-10 h-10 rounded-lg bg-primary-fixed/10 flex items-center justify-center">
            <Zap size={20} className="text-primary-fixed" />
          </div>
          <div>
            <h3 className="font-headline text-lg font-bold text-text-primary">Upgrade to continue</h3>
            <p className="text-sm text-text-muted">{reason}</p>
          </div>
        </div>

        <div className="mt-4 space-y-3">
          <div className="rounded-lg bg-primary-fixed/5 border border-primary-fixed/20 p-4">
            <p className="font-semibold text-primary-fixed text-sm">
              {tier === "investor" ? "Investor — $9/mo" : tier === "pro" ? "Pro — $29/mo" : "Investor — $9/mo"}
            </p>
            <ul className="mt-2 text-xs text-text-muted space-y-1">
              <li>✓ 100 AI queries/day</li>
              <li>✓ 10 watchlists</li>
              <li>✓ Full PARA-DEBATE analysis</li>
              <li>✓ US + India markets</li>
            </ul>
          </div>

          <Link
            href="/pricing"
            onClick={dismiss}
            className="flex items-center justify-center gap-2 w-full bg-primary-fixed text-background font-mono text-[12px] font-bold tracking-[0.1em] uppercase px-6 py-4 hover:shadow-[0_0_30px_rgba(0,255,178,0.4)] transition-all duration-300"
          >
            View plans <ArrowRight size={16} />
          </Link>

          <button
            onClick={dismiss}
            className="w-full text-center text-xs text-text-muted hover:text-text-primary transition-colors py-2"
          >
            Continue with free tier
          </button>
        </div>
      </div>
    </div>
  );
}
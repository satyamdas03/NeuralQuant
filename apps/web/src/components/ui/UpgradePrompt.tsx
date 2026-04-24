"use client";

import Link from "next/link";

interface UpgradePromptProps {
  feature?: string;
  currentTier?: string;
}

export default function UpgradePrompt({ feature, currentTier = "free" }: UpgradePromptProps) {
  const featureLabel = feature ? ` ${feature}` : "";

  return (
    <div className="rounded-2xl ghost-border bg-surface-low/40 p-8 text-center">
      <div className="text-3xl mb-3">🔒</div>
      <h3 className="font-headline text-xl font-bold">
        {featureLabel} requires an upgrade
      </h3>
      <p className="mt-2 text-on-surface-variant text-sm max-w-md mx-auto">
        You&apos;ve reached your {currentTier} tier daily limit. Upgrade to Investor for
        100 queries/day, 25 watchlists, and more.
      </p>
      <div className="mt-6 flex flex-wrap justify-center gap-3">
        <Link
          href="/pricing"
          className="px-6 py-3 rounded-xl bg-gradient-to-r from-[#c1c1ff] to-[#bdf4ff] text-[#0f0f1a] font-semibold text-sm hover:opacity-90 transition-opacity"
        >
          See pricing plans
        </Link>
      </div>
    </div>
  );
}
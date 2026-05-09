"use client";

interface Props {
  feature?: string;
  reason?: string;
}

export default function UpgradeNudge({ feature, reason }: Props) {
  const msg = reason || (feature
    ? `${feature} is available on the Investor plan and above.`
    : "Upgrade to Investor for unlimited AI queries and full market data.");

  return (
    <div className="rounded-xl bg-gradient-to-r from-primary/10 to-tertiary/10 border border-primary/20 p-3 flex items-center gap-3">
      <span className="text-lg">⚡</span>
      <p className="text-xs text-on-surface-variant flex-1">{msg}</p>
      <a
        href="/pricing"
        className="shrink-0 px-3 py-1.5 rounded-lg bg-primary text-on-primary text-xs font-medium hover:bg-primary/90 transition-colors"
      >
        Upgrade
      </a>
    </div>
  );
}
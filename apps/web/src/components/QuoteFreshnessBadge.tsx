"use client";
import type { QuoteStatus } from "@/lib/types";

/**
 * F-01: shown when the API marks a quote stale. The API also withholds the
 * numeric price for stale quotes, so the badge explains why it is missing.
 */
export function isQuoteStale(q: { stale?: boolean | null; quote_status?: QuoteStatus | null }): boolean {
  return q.stale === true || q.quote_status === "quote_stale";
}

function formatAsOf(asOf: string | null | undefined): string | null {
  if (!asOf) return null;
  const d = new Date(asOf);
  if (Number.isNaN(d.getTime())) return null;
  return d.toISOString().slice(0, 10);
}

export function QuoteFreshnessBadge({
  stale,
  quoteStatus,
  asOf,
}: {
  stale?: boolean | null;
  quoteStatus?: QuoteStatus | null;
  asOf?: string | null;
}) {
  if (!isQuoteStale({ stale, quote_status: quoteStatus })) return null;
  const day = formatAsOf(asOf);
  return (
    <div
      role="status"
      data-testid="quote-stale-badge"
      className="inline-flex items-center gap-2 px-2.5 py-1 text-xs font-medium ghost-border text-error bg-error/10"
    >
      <span>Quote stale</span>
      <span className="text-on-surface-variant">
        {day ? `last data ${day} · price not shown` : "data time unknown · price not shown"}
      </span>
    </div>
  );
}

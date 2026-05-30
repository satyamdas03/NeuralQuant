const PLAUSIBLE_DOMAIN = process.env.NEXT_PUBLIC_PLAUSIBLE_DOMAIN;

// ── Event name constants ────────────────────────────────────────────
export const EVENT = {
  // Page views (auto-tracked by AnalyticsRouteTracker)
  PAGEVIEW: "pageview",

  // Auth
  AUTH_STARTED: "auth_started",
  AUTH_COMPLETED: "auth_completed",
  AUTH_FAILED: "auth_failed",

  // Upgrade / pricing
  UPGRADE_CLICKED: "upgrade_clicked",
  CHECKOUT_STARTED: "checkout_started",
  CHECKOUT_COMPLETED: "checkout_completed",

  // Feature usage
  QUERY_SUBMITTED: "query_submitted",
  SCREENER_USED: "screener_used",
  ALERT_CREATED: "alert_created",
  BACKTEST_RUN: "backtest_run",
  WATCHLIST_STOCK_ADDED: "watchlist_stock_added",
  WATCHLIST_STOCK_REMOVED: "watchlist_stock_removed",
  TIER_VIEWED: "tier_viewed",
  TERMINAL_USED: "terminal_used",
  COMPARE_USED: "compare_used",
  SOURCES_VIEWED: "sources_viewed",
} as const;

export type EventName = (typeof EVENT)[keyof typeof EVENT];

/**
 * Track a custom event in Plausible Analytics.
 * Safe to call server-side — will no-op.
 */
export function trackEvent(name: EventName | string, props?: Record<string, string | number | boolean>) {
  if (typeof window === "undefined" || !PLAUSIBLE_DOMAIN) return;
  // Plausible only accepts string props — coerce
  const stringProps: Record<string, string> | undefined = props
    ? Object.fromEntries(Object.entries(props).map(([k, v]) => [k, String(v)]))
    : undefined;
  window.plausible?.(name, { props: stringProps });
}

declare global {
  interface Window {
    plausible?: (event: string, options?: { props?: Record<string, string> }) => void;
  }
}
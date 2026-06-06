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
  ANALYSIS_SHARED: "analysis_shared",
  ANALYSIS_VIEWED: "analysis_viewed",
  SIGNUP_FROM_SHARE: "signup_from_share",
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

// ── Backend analytics (POST /api/analytics/track) ────────────────────

type AnalyticsEvent =
  | 'analysis_run'
  | 'analysis_shared'
  | 'analysis_viewed'
  | 'screener_used'
  | 'morgan_query'
  | 'signup_completed'
  | 'astra_session'
  | 'signup_from_share'
  | 'page_view'
  | 'pricing_viewed'
  | 'methodology_viewed';

interface AnalyticsProperties {
  [key: string]: string | number | boolean | null;
}

export async function trackApiEvent(
  eventType: AnalyticsEvent,
  properties: AnalyticsProperties = {}
): Promise<void> {
  try {
    await fetch('/api/analytics/track', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ event_type: eventType, properties }),
    });
  } catch {
    // Silent fail — never break the UI for analytics
  }
}

// Convenience wrappers
export const analytics = {
  analysisRun: (ticker: string, market: string) =>
    trackApiEvent('analysis_run', { ticker, market }),

  analysisShared: (ticker: string, shareId: string) =>
    trackApiEvent('analysis_shared', { ticker, share_id: shareId }),

  analysisViewed: (shareId: string) =>
    trackApiEvent('analysis_viewed', { share_id: shareId }),

  screenerUsed: (market: string, filters: string) =>
    trackApiEvent('screener_used', { market, filters }),

  morganQuery: (query: string) =>
    trackApiEvent('morgan_query', { query_length: query.length }),

  signupCompleted: (method: string) =>
    trackApiEvent('signup_completed', { method }),

  astraSession: (sessionId: string) =>
    trackApiEvent('astra_session', { session_id: sessionId }),

  signupFromShare: (shareId: string) =>
    trackApiEvent('signup_from_share', { share_id: shareId }),

  pageView: (path: string) =>
    trackApiEvent('page_view', { path }),

  pricingViewed: () =>
    trackApiEvent('pricing_viewed'),

  methodologyViewed: () =>
    trackApiEvent('methodology_viewed'),
};
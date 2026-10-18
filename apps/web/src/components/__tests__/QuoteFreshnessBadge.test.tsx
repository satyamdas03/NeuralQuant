// F-01: a stale quote payload must show a visible stale badge and no price.
import { afterEach, describe, expect, it } from "vitest";
import { cleanup, render, screen } from "@testing-library/react";
import { StockMetaBar } from "@/components/StockMetaBar";
import { AIScoreCard } from "@/components/AIScoreCard";
import type { AIScore, StockMeta } from "@/lib/types";

afterEach(cleanup);

// Shape of GET /stocks/TCS/meta?market=IN for a stale row after the T2 API fix.
const staleMeta = {
  ticker: "TCS",
  name: "Tata Consultancy Services Limited",
  market_cap: 8918585573376,
  market_cap_fmt: "₹8.92 LCr",
  pe_ttm: 17.4,
  pb_ratio: 7.5,
  beta: 1.54,
  week_52_high: 3350,
  week_52_low: 1976.8,
  earnings_date: null,
  analyst_target: null,
  analyst_recommendation: null,
  sector: "Technology",
  industry: "Information Technology Services",
  dividend_yield: null,
  current_price: null,
  change_pct: null,
  cached_at: "2026-09-03T01:04:47.299141+00:00",
  stale: true,
  quote_status: "quote_stale",
} as unknown as StockMeta;

const staleScore: AIScore = {
  ticker: "TCS.NS",
  market: "IN",
  composite_score: 0.5,
  score_1_10: 5,
  regime_id: 1,
  regime_label: "Risk-On",
  sub_scores: { quality: 0.5, momentum: 0.5, short_interest: 0.5, value: 0.5, low_vol: 0.5 },
  top_drivers: [],
  confidence: "medium",
  last_updated: "2026-10-17T02:00:00+00:00",
  current_price: null,
  change_pct: null,
  stale: true,
  quote_status: "quote_stale",
  price_as_of: "2026-09-03T01:04:47.299141+00:00",
} as AIScore;

describe("stale quote badge", () => {
  it("meta bar shows the stale badge with the data date", () => {
    render(<StockMetaBar meta={staleMeta} market="IN" />);
    const badge = screen.getByTestId("quote-stale-badge");
    expect(badge.textContent).toContain("Quote stale");
    expect(badge.textContent).toContain("2026-09-03");
    expect(document.body.textContent).not.toContain("2348");
  });

  it("score card shows the stale badge", () => {
    render(<AIScoreCard data={staleScore} />);
    expect(screen.getByTestId("quote-stale-badge").textContent).toContain("Quote stale");
  });

  it("fresh payload shows no badge", () => {
    const fresh = { ...staleMeta, stale: false, quote_status: "ok", current_price: 2156 } as StockMeta;
    render(<StockMetaBar meta={fresh} market="IN" />);
    expect(screen.queryByTestId("quote-stale-badge")).toBeNull();
  });
});

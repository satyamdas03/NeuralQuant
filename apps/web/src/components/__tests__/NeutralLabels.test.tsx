// B5: public UI must not render buy/sell/hold/avoid advice labels.
import { afterEach, describe, expect, it } from "vitest";
import { cleanup, render } from "@testing-library/react";
import VerdictBanner from "@/components/ui/VerdictBanner";
import { AgentDebatePanel } from "@/components/AgentDebatePanel";
import IRSZoneBadge from "@/components/IRSZoneBadge";
import { StockMetaBar } from "@/components/StockMetaBar";
import { irsBand, neutralBand } from "@/lib/neutralLabels";
import type { AnalystResponse, QuantFactorScores, StockMeta } from "@/lib/types";

afterEach(cleanup);

const ADVICE = /\b(STRONG BUY|STRONG SELL|BUY|SELL|HOLD|AVOID|HARD SELL|INVESTMENT READY)\b/i;

describe("neutralBand", () => {
  it("maps every advice label to a neutral band", () => {
    expect(neutralBand("STRONG BUY")).toBe("Upper band");
    expect(neutralBand("buy")).toBe("Upper band");
    expect(neutralBand("strong_buy")).toBe("Upper band");
    expect(neutralBand("HOLD")).toBe("Middle band");
    expect(neutralBand("SELL")).toBe("Lower band");
    expect(neutralBand("STRONG SELL")).toBe("Lower band");
    expect(neutralBand("AVOID")).toBe("Lower band");
    expect(neutralBand("something else")).toBe("Unrated");
    expect(irsBand(70)).toBe("Upper band");
    expect(irsBand(50)).toBe("Middle band");
    expect(irsBand(10)).toBe("Lower band");
  });
});

describe("rendered components show no advice labels", () => {
  it("VerdictBanner", () => {
    for (const v of ["STRONG BUY", "BUY", "HOLD", "SELL", "STRONG SELL"]) {
      const { container, unmount } = render(<VerdictBanner verdict={v} confidence={70} timeframe="Medium-term" />);
      expect(container.textContent).not.toMatch(ADVICE);
      unmount();
    }
  });

  it("AgentDebatePanel head analyst", () => {
    const report = {
      ticker: "AAPL", head_analyst_verdict: "STRONG BUY", investment_thesis: "Thesis.",
      bull_case: "", bear_case: "", risk_factors: [], agent_outputs: [], consensus_score: 0.6,
    } as AnalystResponse;
    const { container } = render(<AgentDebatePanel report={report} />);
    expect(container.textContent).toContain("Upper band");
    expect(container.textContent).not.toMatch(ADVICE);
  });

  it("IRSZoneBadge low score", () => {
    const scores = { irs_pct: 12, g_score: -6, risk_eff_score: -4, growth_score: -1,
      return_score: -1, valuation_score: -1, risk_score: -2, composite: -5,
      is_loss_making: false, valuation_sweet_spot: false } as unknown as QuantFactorScores;
    const { container } = render(<IRSZoneBadge scores={scores} ticker="XYZ" market="US" />);
    expect(container.textContent).toContain("Lower band");
    expect(container.textContent).not.toMatch(ADVICE);
  });

  it("StockMetaBar analyst consensus", () => {
    const meta = { ticker: "AAPL", name: "Apple Inc.", analyst_recommendation: "strong_buy",
      analyst_consensus: "BUY", market_cap_fmt: "$5T" } as unknown as StockMeta;
    const { container } = render(<StockMetaBar meta={meta} market="US" />);
    expect(container.textContent).toContain("Upper band");
    expect(container.textContent).not.toMatch(ADVICE);
  });
});

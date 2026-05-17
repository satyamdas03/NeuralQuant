"use client";

import { createContext, useContext, useState, useCallback, useEffect } from "react";
import { Joyride, type Step, type EventData, STATUS, EVENTS } from "react-joyride";

type WalkthroughContextType = {
  startTour: () => void;
  isRunning: boolean;
};

const WalkthroughContext = createContext<WalkthroughContextType>({
  startTour: () => {},
  isRunning: false,
});

export function useWalkthrough() {
  return useContext(WalkthroughContext);
}

const TOUR_STEPS: Step[] = [
  // ── Dashboard ──
  {
    target: "#dashboard-market-indices",
    title: "Market Indices",
    content: "Real-time snapshot of major US and Indian stock indices. See how NIFTY 50, S&P 500, SENSEX and more are performing at a glance. This is your pulse on global markets.",
    placement: "bottom",
    skipBeacon: true,
  },
  {
    target: "#dashboard-news-panel",
    title: "Market Summary",
    content: "Top financial news curated from Yahoo Finance. Understand what's moving markets today — earnings, policy changes, and macro events that affect your portfolio.",
    placement: "right",
  },
  {
    target: "#dashboard-equity-sectors",
    title: "Equity Sector Heatmap",
    content: "Visual breakdown of all 11 US equity sectors. Darker colors = stronger performance. Spot rotation trends — money flowing from Tech to Energy, or defensive sectors rallying?",
    placement: "left",
  },
  {
    target: "#dashboard-market-movers",
    title: "Market Movers",
    content: "Top gainers, losers, and most active stocks by volume. Find what's spiking on unusual activity — often the first signal of breaking news or institutional accumulation.",
    placement: "left",
  },
  {
    target: "#dashboard-forecast-picks",
    title: "Top ForeCast Picks",
    content: "QuantAlpha's AI composite scores ranking the highest-conviction stocks. Each score blends fundamentals, technicals, sentiment, and macro fit into a single 1-10 rating.",
    placement: "left",
  },
  {
    target: "#dashboard-social-buzz",
    title: "Social Sentiment",
    content: "What traders are talking about on StockTwits and social platforms. Gauge retail sentiment momentum — are crowds euphoric, fearful, or spotting something early?",
    placement: "left",
  },

  // ── Ask AI / Query ──
  {
    target: "#query-input-area",
    title: "Ask AI Anything",
    content: "Ask QuantAlpha any financial question in plain English. Portfolio allocation, stock deep dives, market scenarios — the AI pulls live data from FMP, yfinance, and news sources to answer with verified numbers.",
    placement: "top",
  },

  // ── Screener ──
  {
    target: "#screener-filters",
    title: "Smart Screening",
    content: "Filter thousands of US and Indian stocks by AI score, sector, market cap, and more. The AI composite score combines 5 factors: quality, momentum, value, sentiment, and macro fit.",
    placement: "bottom",
  },
  {
    target: "#screener-debate-btn",
    title: "PARA-DEBATE Analysis",
    content: "Launch a 6-agent adversarial debate on any stock. MACRO, FUNDAMENTAL, TECHNICAL, SENTIMENT, GEOPOLITICAL, and ADVERSARIAL agents argue bull vs bear — then a HEAD ANALYST synthesizes the verdict with live data verification.",
    placement: "left",
  },

  // ── Stock Detail ──
  {
    target: "#stock-meta-card",
    title: "Stock Intelligence Card",
    content: "Everything you need in one card: live price, P/E ratio, beta, market cap, sector, and dividend yield. All data verified from FMP Premium and marked [VERIFIED] when sourced from live APIs.",
    placement: "right",
  },
  {
    target: "#stock-debate-section",
    title: "Adversarial Debate Verdict",
    content: "See the full PARA-DEBATE output — bull case, bear case, risk factors, catalysts, and a final HOLD/BUY/SELL verdict with confidence level. Every number cross-checked against live data.",
    placement: "top",
  },

  // ── Performance ──
  {
    target: "#performance-score-breakdown",
    title: "AI Score Methodology",
    content: "Understand exactly how QuantAlpha computes its 1-10 rating. Each factor (quality, momentum, value, sentiment, macro) is scored independently, then blended with dynamic weights based on market regime.",
    placement: "bottom",
  },

  // ── Sidebar ──
  {
    target: "#sidebar-nav",
    title: "Navigation Hub",
    content: "Your command center. Dashboard for market overview, Ask AI for questions, Screener for stock discovery, Stocks for deep dives, Terminal for direct data access, Performance for methodology, and Trade for strategy automation.",
    placement: "right",
  },
];

const joyrideStyles = {
  options: {
    primaryColor: "#c1c1ff",
    backgroundColor: "#12121f",
    textColor: "#e0e0e0",
    arrowColor: "#12121f",
    overlayColor: "rgba(0, 0, 0, 0.65)",
    spotlightShadow: "0 0 30px rgba(193, 193, 255, 0.3)",
    beaconSize: 36,
    zIndex: 10000,
  },
  tooltip: {
    borderRadius: 12,
    padding: "20px 24px",
  },
  tooltipTitle: {
    fontSize: 15,
    fontWeight: 700,
    fontFamily: "var(--font-headline), system-ui, sans-serif",
  },
  tooltipContent: {
    fontSize: 13,
    lineHeight: 1.6,
    color: "#a0a0b0",
    paddingTop: 6,
  },
  buttonNext: {
    background: "linear-gradient(135deg, #c1c1ff, #bdf4ff)",
    color: "#0f0f1a",
    borderRadius: 8,
    padding: "8px 18px",
    fontSize: 13,
    fontWeight: 600,
    border: "none",
  },
  buttonBack: {
    color: "#a0a0b0",
    fontSize: 13,
    marginRight: 8,
  },
  buttonSkip: {
    color: "#666",
    fontSize: 12,
  },
};

export default function WalkthroughProvider({ children }: { children: React.ReactNode }) {
  const [run, setRun] = useState(false);
  const [isRunning, setIsRunning] = useState(false);
  const [steps, setSteps] = useState<Step[]>(TOUR_STEPS);

  // Only show tour when explicitly triggered (after WelcomeModal closes or user requests)
  const startTour = useCallback(() => {
    setSteps(filterAvailableSteps(TOUR_STEPS));
    setRun(true);
    setIsRunning(true);
  }, []);

  const handleCallback = useCallback(
    (data: EventData) => {
      const { status, type } = data;

      if (type === EVENTS.TOUR_END) {
        localStorage.setItem("nq_walkthrough_done", "1");
      }

      if (
        [STATUS.FINISHED, STATUS.SKIPPED].includes(status as "finished" | "skipped")
      ) {
        setRun(false);
        setIsRunning(false);
        localStorage.setItem("nq_walkthrough_done", "1");
      }
    },
    []
  );

  // Auto-start on first visit after welcome modal would have closed
  useEffect(() => {
    const onboardingSeen = localStorage.getItem("nq_onboarding_seen");
    const walkthroughDone = localStorage.getItem("nq_walkthrough_done");

    if (onboardingSeen && !walkthroughDone) {
      // Delay so WelcomeModal renders first, then tour starts after it closes
      const timer = setTimeout(() => {
        setSteps(filterAvailableSteps(TOUR_STEPS));
        setRun(true);
        setIsRunning(true);
      }, 2000);
      return () => clearTimeout(timer);
    }
  }, []);

  return (
    <WalkthroughContext.Provider value={{ startTour, isRunning }}>
      {children}
      <Joyride
        steps={steps}
        run={run}
        continuous
        scrollToFirstStep
        styles={joyrideStyles}
        onEvent={handleCallback}
        locale={{
          back: "Back",
          close: "Close",
          last: "Got it!",
          next: "Next",
          skip: "Skip tour",
        }}
        options={{
          showProgress: true,
          overlayClickAction: false,
          buttons: ["back", "skip", "primary"],
        }}
      />
    </WalkthroughContext.Provider>
  );
}

/** Filter tour steps to only those whose target elements exist in the DOM. */
function filterAvailableSteps(allSteps: Step[]): Step[] {
  if (typeof document === "undefined") return allSteps;
  return allSteps.filter((step) => {
    const target = typeof step.target === "string" ? step.target : null;
    if (!target) return true;
    return !!document.querySelector(target);
  });
}

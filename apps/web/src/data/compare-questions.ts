export type Winner = "neuralquant" | "partial" | "none";

export interface CompareQuestion {
  id: string;
  question: string;
  category: string;
  responses: {
    neuralquant: string;
    chatgpt: string;
    claude: string;
    grok: string;
  };
  winner: Winner;
  verdict: string;
}

export const COMPARE_QUESTIONS: CompareQuestion[] = [
  {
    id: "q1",
    question: "What's the composite score for AAPL right now?",
    category: "Real-Time Scores",
    responses: {
      neuralquant:
        "AAPL: ForeCast Score 7.2/10 — Quality 8 (high gross margin 46%, Piotroski 7), Momentum 9 (strong 12-1 return), Value 4 (above-median P/E), Low-Vol 6, Short-Interest 7. Regime: Risk-On. Sector-adjusted within Technology.",
      chatgpt:
        "I don’t have real-time stock scores. As of my last knowledge update, Apple’s fundamentals include a P/E ratio around 30, strong cash flows, and consistent revenue growth. I’d need to check current prices and financial data for an up-to-date assessment.",
      claude:
        "I can’t access live market data or compute composite scores. Apple (AAPL) has historically shown strong fundamentals — high margins, consistent earnings growth, and a large cash position. For real-time analysis, I’d recommend checking financial data platforms.",
      grok:
        "AAPL is trading around $198. The P/E ratio is about 33x, which is above the S&P 500 average. Revenue growth has been modest. [No composite scoring system available.]",
    },
    winner: "neuralquant",
    verdict:
      "Only NeuralQuant provides real-time composite scores with factor breakdowns and regime context.",
  },
  {
    id: "q2",
    question: "Is the market in a bull or bear regime right now?",
    category: "Regime Detection",
    responses: {
      neuralquant:
        "Current regime: Risk-On. HMM posterior probabilities — Risk-On: 72%, Late-Cycle: 18%, Bear: 7%, Recovery: 3%. Key indicators: VIX at 14.2 (low), HY spread tightening, SPX above 200-day MA. Momentum factor weight increased to 0.30.",
      chatgpt:
        "Based on general market conditions, we appear to be in a bull market. The S&P 500 has been trending upward, and investor sentiment is generally positive. However, I don’t have real-time regime classification data.",
      claude:
        "Market regime classification requires real-time volatility, yield curve, and breadth data. Without access to live indicators, I can note that bull markets are typically characterized by rising prices, low volatility, and positive breadth — but I cannot classify the current regime.",
      grok:
        "The market seems to be doing well based on recent data. VIX is relatively low and the S&P 500 has been hitting highs. That’s generally considered a bull market environment. [No quantitative regime model.]",
    },
    winner: "neuralquant",
    verdict:
      "NeuralQuant’s HMM provides posterior probabilities and factor reweighting — no other AI offers this.",
  },
  {
    id: "q3",
    question: "Which Indian midcap stocks have strong insider buying?",
    category: "India Markets",
    responses: {
      neuralquant:
        "Based on NSE Bhavcopy delivery data — TATAPOWER.NS (delivery % at 42%, strong institutional accumulation), INFY.NS (delivery 38%). Delivery percentages above 35% indicate smart money accumulation. Combined with quality scores: TATAPOWER Quality 6, INFY Quality 8.",
      chatgpt:
        "I don’t have access to real-time Indian stock market data or insider buying information for midcap stocks. For Indian market analysis, I’d recommend checking NSE India, Moneycontrol, or Screener.in for delivery percentage data.",
      claude:
        "I cannot access NSE Bhavcopy data or real-time Indian stock delivery percentages. For Indian midcap insider activity, you’d need to check SEBI filings, NSE India’s corporate actions section, or financial news platforms like Economic Times.",
      grok:
        "Indian midcap stocks with insider buying would include companies where promoters are increasing their stakes. I don’t have current specific data on Indian insider transactions. [No India market data or delivery % tracking.]",
    },
    winner: "neuralquant",
    verdict:
      "NeuralQuant uniquely covers Indian markets with Bhavcopy delivery data — competitors have no India coverage.",
  },
  {
    id: "q4",
    question: "What factors drove NVDA’s score change this month?",
    category: "Factor Analysis",
    responses: {
      neuralquant:
        "NVDA score moved from 6.8 → 8.1 this month. Drivers: Momentum surged from 6 → 9 (12-1 return jumped on earnings beat), Quality held at 8 (gross margin 78%), Low-Vol improved 5 → 7 (realized vol dropped post-earnings), Short-Interest dropped from 8 → 5 (short float decreased from 1.2% to 0.8%). Regime: Risk-On favors momentum weighting.",
      chatgpt:
        "NVIDIA has seen significant price movements recently, driven by strong earnings results and AI demand. The stock’s momentum has been positive. For detailed factor analysis with score changes, you’d need a quantitative analysis platform that tracks multi-factor models over time.",
      claude:
        "I don’t have the ability to track score changes over time or decompose factor contributions. NVIDIA’s recent performance has been driven by AI/GPU demand, strong earnings, and positive analyst sentiment, but I cannot provide a multi-factor attribution analysis.",
      grok:
        "NVDA has been performing well due to AI demand and strong earnings. The stock price has gone up significantly. [No factor decomposition or score tracking capability.]",
    },
    winner: "neuralquant",
    verdict:
      "Only NeuralQuant decomposes score changes into individual factor movements with regime context.",
  },
  {
    id: "q5",
    question: "What’s the short interest situation on TSLA?",
    category: "Alternative Data",
    responses: {
      neuralquant:
        "TSLA Short-Interest factor: 3/10 (high short interest, bearish signal). Short float: 3.2% (above market avg). Days to cover: 1.8. Combined with insider selling (2 recent Form 4 sells from CFO and CTO), the short-interest + insider cluster gives a bearish divergence signal. Adversarial agent flags this as a concern.",
      chatgpt:
        "Tesla’s short interest has historically been one of the highest among large-cap stocks. As of recent data, the short interest ratio and days to cover can be found on financial data platforms like Finviz, Ortex, or S3 Partners. I don’t have real-time short interest data.",
      claude:
        "I don’t have access to real-time short interest data for TSLA. Short interest information is available from FINRA, exchange short interest reports, and platforms like Ortex and S3 Partners. Tesla has historically attracted significant short interest due to its high valuation and CEO-related volatility.",
      grok:
        "TSLA short interest is available on various financial sites. Tesla has always had notable short interest due to its volatile nature and high valuation. [No real-time short interest or insider cluster scoring.]",
    },
    winner: "neuralquant",
    verdict:
      "NeuralQuant combines short interest with SEC Form 4 insider data — a signal no general AI can access.",
  },
  {
    id: "q6",
    question: "Should I buy IWM given the current macro environment?",
    category: "Multi-Agent Debate",
    responses: {
      neuralquant:
        "PARA-DEBATE Verdict: HOLD. MACRO agent: Bullish (HY spreads tight, Fed dovish). FUNDAMENTAL agent: Neutral (IWM P/E 18x, mid-range). TECHNICAL agent: Bearish (below 50-day MA, RSI 42). SENTIMENT agent: Neutral (retail flows flat). GEOPOLITICAL agent: Cautious (tariff uncertainty). ADVERSARIAL agent: Challenges bullish case — small caps underperform in late-cycle. HEAD ANALYST: Mixed signals warrant caution. Regime is Risk-On but deteriorating. Wait for IWM to reclaim $220.",
      chatgpt:
        "IWM (iShares Russell 2000 ETF) tracks small-cap US stocks. The decision to buy depends on your investment timeline, risk tolerance, and macro outlook. Small caps can outperform in economic recoveries but may struggle in high-rate environments. Consider dollar-cost averaging and diversification.",
      claude:
        "Investment decisions should be based on your personal financial situation, risk tolerance, and investment timeline. IWM provides small-cap exposure, which tends to perform well in economic recoveries but can be volatile. I’d recommend consulting a financial advisor for personalized advice.",
      grok:
        "IWM could be interesting if you believe small caps will recover. The macro environment matters — lower interest rates tend to help small caps. But there’s risk if the economy slows. [No structured multi-perspective analysis.]",
    },
    winner: "neuralquant",
    verdict:
      "PARA-DEBATE provides a structured 6-analyst debate with a final verdict — competitors give generic advice.",
  },
];

export const CATEGORY_ICONS: Record<string, string> = {
  "Real-Time Scores": "Activity",
  "Regime Detection": "GitBranch",
  "India Markets": "Globe",
  "Factor Analysis": "BarChart3",
  "Alternative Data": "FileSearch",
  "Multi-Agent Debate": "Swords",
};
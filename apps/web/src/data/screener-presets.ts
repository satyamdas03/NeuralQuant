export interface ScreenerPreset {
  id: string;
  name: string;
  description: string;
  filters: Record<string, number>;
  icon: string;
}

export const PRESETS: ScreenerPreset[] = [
  {
    id: "momentum_breakout",
    name: "Momentum Breakout",
    description: "Stocks surging on strong price trends. High momentum percentile means these stocks are outperforming peers over the past 12 months — classic trend-following picks that ride upward breakouts.",
    filters: { min_score: 7, min_momentum: 70 },
    icon: "TrendingUp",
  },
  {
    id: "value_play",
    name: "Value Play",
    description: "Undervalued stocks with solid fundamentals. Low P/E ratios relative to sector peers suggest the market hasn't caught up yet — these are Warren Buffett-style picks trading below intrinsic value.",
    filters: { min_score: 5, min_quality: 70 },
    icon: "DollarSign",
  },
  {
    id: "dividend_income",
    name: "Dividend Income",
    description: "High-quality, low-volatility stocks for steady income. These companies have strong balance sheets, stable earnings, and lower price swings — ideal for conservative investors prioritizing capital preservation and regular dividends.",
    filters: { min_quality: 60, min_score: 5, min_low_vol: 60 },
    icon: "Banknote",
  },
  {
    id: "quality_compound",
    name: "Quality Compound",
    description: "Long-term compounders with the best balance sheets. High quality scores mean strong profitability, consistent margins, and low debt — the kind of businesses that compound wealth over decades, not days.",
    filters: { min_quality: 80, min_score: 7 },
    icon: "Gem",
  },
  {
    id: "contrarian_bet",
    name: "Contrarian Bet",
    description: "Beaten-down stocks with sound fundamentals. Low momentum but decent quality — these are potential turnaround candidates where the market has overreacted, creating a margin of safety for patient investors.",
    filters: { min_quality: 50, max_momentum: 40 },
    icon: "RotateCcw",
  },
];
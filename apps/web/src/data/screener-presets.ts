export interface ScreenerPreset {
  id: string;
  name: string;
  description: string;
  filters: Record<string, number>;
  icon: string;
}

export const PRESETS: ScreenerPreset[] = [
  { id: "momentum_breakout", name: "Momentum Breakout", description: "Strong upward momentum", filters: { min_score: 7, min_momentum: 70 }, icon: "TrendingUp" },
  { id: "value_play", name: "Value Play", description: "Undervalued quality", filters: { min_score: 5, min_quality: 70 }, icon: "DollarSign" },
  { id: "dividend_income", name: "Dividend Income", description: "High-quality low-vol", filters: { min_quality: 60, min_score: 5, min_low_vol: 60 }, icon: "Banknote" },
  { id: "quality_compound", name: "Quality Compound", description: "Long-term compounders", filters: { min_quality: 80, min_score: 7 }, icon: "Gem" },
  { id: "contrarian_bet", name: "Contrarian Bet", description: "Beaten down but sound", filters: { min_quality: 50, max_momentum: 40 }, icon: "RotateCcw" },
];
export type Market = "US" | "IN" | "GLOBAL";
export type Stance = "BULL" | "BEAR" | "NEUTRAL";
export type Conviction = "HIGH" | "MEDIUM" | "LOW";
export type ConfidenceLevel = "high" | "medium" | "low";
export type Verdict = "STRONG BUY" | "BUY" | "HOLD" | "SELL" | "STRONG SELL";
export type RegimeLabel = "Risk-On" | "Late-Cycle" | "Bear" | "Recovery";

export interface FeatureDriver {
  name: string;
  contribution: number;
  value: string;
  direction: "positive" | "negative" | "neutral";
}

export interface SubScores {
  quality: number;
  momentum: number;
  short_interest: number;
  value: number;
  low_vol: number;
}

export interface AIScore {
  ticker: string;
  market: Market;
  composite_score: number;
  score_1_10: number;
  regime_id: number;
  regime_label: RegimeLabel;
  sub_scores: SubScores;
  top_drivers: FeatureDriver[];
  confidence: ConfidenceLevel;
  last_updated: string;
}

export interface AgentOutput {
  agent: string;
  stance: Stance;
  conviction: Conviction;
  thesis: string;
  key_points: string[];
}

export interface AnalystResponse {
  ticker: string;
  head_analyst_verdict: Verdict;
  investment_thesis: string;
  bull_case: string;
  bear_case: string;
  risk_factors: string[];
  agent_outputs: AgentOutput[];
  consensus_score: number;
}

export interface ScreenerRequest {
  market?: Market;
  min_score?: number;
  max_results?: number;
  tickers?: string[];
}

export interface ScreenerResponse {
  regime_label: RegimeLabel;
  regime_id: number;
  results: AIScore[];
  total: number;
}

export interface AnalystRequest {
  ticker: string;
  market?: Market;
}

export interface QueryRequest {
  question: string;
  ticker?: string;
  market?: Market;
}

export interface QueryResponse {
  answer: string;
  data_sources: string[];
  follow_up_questions: string[];
}

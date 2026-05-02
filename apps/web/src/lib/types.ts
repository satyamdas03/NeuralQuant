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
  insider?: number;
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
  preset?: string;
  min_momentum?: number;
  min_quality?: number;
  min_low_vol?: number;
  max_momentum?: number;
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
  history?: ConversationMessage[];
}

export interface QueryResponse {
  answer: string;
  data_sources: string[];
  follow_up_questions: string[];
}

export interface IndexData {
  symbol: string;
  name: string;
  price: number;
  change_pct: number;
  change_abs: number;
}

export interface NewsItem {
  title: string;
  publisher: string;
  url: string;
  time: string;
}

export interface SectorData {
  symbol: string;
  name: string;
  change_pct: number;
}

export interface MarketOverview {
  indices: IndexData[];
  futures: IndexData[];
}

export interface MarketNews {
  news: NewsItem[];
}

export interface MarketSectors {
  sectors: SectorData[];
}

export interface Mover {
  ticker: string;
  price: number;
  change_pct: number;
  change_abs: number;
  volume: number;
}

export interface MarketMovers {
  gainers: Mover[];
  losers: Mover[];
  active: Mover[];
}

export interface NewsDeskItem {
  title: string;
  publisher: string;
  url: string;
  time: string;
  category: "us_markets" | "india" | "earnings" | "macro" | "insider";
  tickers: string[];
  sentiment: "bullish" | "bearish" | "neutral";
}

export interface NewsDeskResponse {
  sentiment: "bullish" | "bearish" | "neutral";
  headlines: NewsDeskItem[];
  trending: string[];
}

export interface ChartBar {
  date: string;
  close: number;
  open: number;
  high: number;
  low: number;
  volume: number;
}

export interface StockChart {
  ticker: string;
  period: string;
  data: ChartBar[];
  period_change_pct: number;
}

export interface StockMeta {
  ticker: string;
  name: string;
  market_cap: number | null;
  market_cap_fmt: string | null;
  pe_ttm: number | null;
  pb_ratio: number | null;
  beta: number | null;
  week_52_high: number | null;
  week_52_low: number | null;
  earnings_date: string | null;
  analyst_target: number | null;
  analyst_recommendation: string | null;
  sector: string | null;
  industry: string | null;
  dividend_yield: number | null;
  current_price: number | null;
}

export interface ConversationMessage {
  role: "user" | "assistant";
  content: string;
}

export interface SentimentHeadline {
  title: string;
  url: string;
  publisher: string;
  score: number;
}

export interface SentimentResponse {
  ticker: string;
  market: Market;
  aggregate_score: number;
  label: "Bullish" | "Bearish" | "Neutral";
  n_headlines: number;
  headlines: SentimentHeadline[];
}

export interface BacktestRequest {
  ticker: string;
  market?: Market;
  strategy?: "sma_crossover";
  fast?: number;
  slow?: number;
  period?: "1y" | "2y" | "5y" | "10y" | "max";
  initial_capital?: number;
}

export interface BacktestPoint {
  date: string;
  equity: number;
}

export interface BacktestResponse {
  ticker: string;
  strategy: string;
  final_equity: number;
  total_return_pct: number;
  buy_hold_return_pct: number;
  sharpe: number;
  max_drawdown_pct: number;
  n_trades: number;
  n_days: number;
  equity_curve: BacktestPoint[];
}

export type AlertType = "score_change" | "regime_change" | "threshold";

export interface AlertSubscription {
  id: string;
  ticker: string;
  market: "US" | "IN";
  alert_type: AlertType;
  threshold: number | null;
  min_delta: number;
  last_triggered_at: string | null;
  created_at: string;
}

export interface AlertDelivery {
  id: string;
  ticker: string;
  market: "US" | "IN";
  alert_type: AlertType;
  old_value: number | null;
  new_value: number | null;
  delivered_at: string;
}


// ── Structured Query Response (v2) ──────────────────────────────────────────

export interface MetricItem {
  name: string;
  value: string;
  benchmark?: string | null;
  status: "positive" | "negative" | "neutral";
}

export interface ScenarioItem {
  label: string;
  probability: number;
  target: string;
  thesis: string;
}

export interface AllocationItem {
  ticker: string;
  weight: number;
  rationale: string;
  why_not_alt: string;
}

export interface ComparisonItem {
  ticker: string;
  metric: string;
  ours: string;
  theirs: string;
  edge: string;
}

export interface ReasoningBlock {
  why_this: string;
  why_not_alt: string;
  edge_summary: string;
  second_best: string;
  confidence_gap: string;
}

export interface StructuredQueryResponse {
  verdict: string;
  confidence: number;
  timeframe: string;
  summary: string;
  metrics: MetricItem[];
  reasoning: ReasoningBlock;
  scenarios: ScenarioItem[];
  allocations: AllocationItem[];
  comparisons: ComparisonItem[];
  data_sources: string[];
  follow_up_questions: string[];
  route: "SNAP" | "REACT" | "DEEP";
}


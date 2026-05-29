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

export interface AnjaliScores {
  growth_score: number | null;        // -4 to +4 vs index peers
  return_score: number | null;        // -4 to +4
  valuation_score: number | null;     // -4 to +4 (Q2=+1 sweet spot)
  risk_score: number | null;          // -4 to +4 (Q4=+1 sweet spot)
  composite: number | null;           // -16 to +16
  is_loss_making: boolean;            // True if any loss flag set
  valuation_sweet_spot: boolean;      // True if Q2 valuation (score 0.5-1.5)
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
  anjali?: AnjaliScores | null;  // Anjali Value Screener scores (null if not available)
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
  // Anjali Value Screener filters
  min_anjali_composite?: number;   // minimum Anjali composite score
  valuation_sweet_spot?: boolean;  // only Q2 valuation stocks
  loss_making?: boolean;           // exclude loss-making companies
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

export interface UserProfile {
  risk_profile: "conservative" | "balanced" | "aggressive";
  time_horizon: "<1yr" | "1-3yr" | "3-5yr" | "5yr+";
  goal: "wealth_building" | "retirement" | "education" | "passive_income" | "tax_saving";
  investable_amount?: string;
  updated_at?: string;
  email_market_wrap?: boolean;
}

export interface QueryRequest {
  question: string;
  ticker?: string;
  market?: Market;
  history?: ConversationMessage[];
  profile?: UserProfile;
  clarification_answers?: string[];
  session_key?: string;
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
  analyst_consensus: string | null;
  analyst_count: number | null;
  dividend_history: Array<{ date: string; dividend: number; yield_pct: number }> | null;
  altman_z_score: number | null;
  piotroski_score: number | null;
  insider_buys: number | null;
  insider_sells: number | null;
  dcf_value: number | null;
  dividend_yield_pct: number | null;
  yield_curve_2y: number | null;
  yield_curve_10y: number | null;
  yield_curve_spread: number | null;
}

export interface AnalystConsensus {
  consensus: string | null;
  consensus_rating: number | null;
  target_consensus: number | null;
  target_median: number | null;
  target_high: number | null;
  target_low: number | null;
  analyst_count: number | null;
  buy_count: number | null;
  hold_count: number | null;
  sell_count: number | null;
}

export interface ShareOwnership {
  float_shares: number | null;
  outstanding_shares: number | null;
  short_interest: number | null;
  short_ratio: number | null;
  institutional_ownership_pct: number | null;
  insider_ownership_pct: number | null;
}

export interface OptionsSnapshot {
  enabled: boolean;
  ticker: string;
  data: {
    consensus: AnalystConsensus | null;
    ownership: ShareOwnership | null;
  };
  error?: string;
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
  period?: "1y" | "2y" | "3y" | "5y" | "10y" | "max";
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

export interface ScoreBreakdownItem {
  score: number;
  count: number;
  hit_rate: number;
  avg_return_pct: number;
}

export interface TopStockItem {
  ticker: string;
  name?: string;
  score_1_10: number;
  composite_score: number;
  return_3m_pct?: number | null;
}

export interface AccuracyResponse {
  hit_rate_at_7plus: number;
  hit_rate_at_5plus: number;
  baseline_hit_rate: number;
  mean_return_top_decile: number;
  mean_return_bottom_decile: number;
  top_minus_bottom_spread: number;
  sharpe_top_quartile: number;
  max_drawdown_top_quartile: number;
  win_rate_top_quartile: number;
  observation_count: number;
  period_start: string;
  period_end: string;
  avg_stocks_per_period: number;
  methodology: string;
  comparison: string;
  note: string;
  is_fallback?: boolean;
  score_breakdown?: ScoreBreakdownItem[];
  top_stocks_snapshot?: TopStockItem[];
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

export interface StockSummary {
  ticker: string;
  name: string | null;
  price: number | null;
  change_pct: number | null;
  pe_ttm: number | null;
  eps_ttm: number | null;
  pb_ratio: number | null;
  market_cap: number | null;
  week_52_high: number | null;
  week_52_low: number | null;
  analyst_target: number | null;
  analyst_recommendation: string | null;
  beta: number | null;
  sector: string | null;
  forecast_score: number | null;
  currency: string;
  // FMP Premium enrichment fields
  analyst_consensus: string | null;
  analyst_buy_pct: number | null;
  analyst_target_avg: number | null;
  analyst_target_high: number | null;
  analyst_target_low: number | null;
  analyst_revenue_est: number | null;
  analyst_eps_est: number | null;
  analyst_count: number | null;
  altman_z_score: number | null;
  piotroski_score: number | null;
  insider_buys: number | null;
  insider_sells: number | null;
  insider_shares_bought: number | null;
  insider_shares_sold: number | null;
  dividend_latest: number | null;
  dividend_yield_pct: number | null;
  next_earnings_date: string | null;
  next_earnings_eps_est: number | null;
  dcf_value: number | null;
  // OpenBB enrichment fields
  iv_percentile: number | null;
  put_call_ratio: number | null;
  implied_volatility: number | null;
  yield_curve_2y: number | null;
  yield_curve_10y: number | null;
  yield_curve_spread: number | null;
  anjali?: AnjaliScores | null;  // Anjali Value Screener scores
}

// ── Portfolio Output Types (Phase 1) ──────────────────────────────────────────

export interface MarketContextCard {
  label: string;
  value: string;
  change?: string;
  sentiment?: string;
}

export interface AllocationSegment {
  label: string;
  percentage: number;
  color?: string;
  rationale?: string;
}

export interface PortfolioStockCard {
  ticker: string;
  name?: string;
  allocation_pct: number;
  entry_price?: string;
  target_price?: string;
  stop_loss?: string;
  risk_reward?: string;
  rationale?: string;
  confidence?: number;
  sector?: string;
  price_unavailable?: boolean;
}

export interface ScenarioCard {
  label: string;
  probability_pct?: number;
  outcome?: string;
  description?: string;
  color?: string;
}

export interface ActionPrompt {
  label: string;
  prompt_text: string;
  icon?: string;
}

export interface StructuredQueryResponse {
  verdict: string;
  confidence: number;
  timeframe: string;
  summary: string;
  stock_summary: StockSummary | null;
  metrics: MetricItem[];
  reasoning: ReasoningBlock;
  scenarios: ScenarioItem[];
  allocations: AllocationItem[];
  comparisons: ComparisonItem[];
  data_sources: string[];
  follow_up_questions: string[];
  route: "SNAP" | "REACT" | "DEEP";

  // Phase 1 portfolio fields (all optional)
  market_context?: MarketContextCard[];
  allocation_breakdown?: AllocationSegment[];
  portfolio_stocks?: PortfolioStockCard[];
  scenario_analysis?: ScenarioCard[];
  action_prompts?: ActionPrompt[];
  sebi_disclaimer?: string;
  is_portfolio_response?: boolean;
  profiler_needed?: boolean;
  clarification_needed?: boolean;
  clarification_questions?: ClarificationQuestion[];
  clarification_context?: string;
}

export interface ClarificationQuestion {
  question: string;
  options: string[];
  question_type: string;
}

// ── Terminal View ────────────────────────────────────────────────────────────
export interface TerminalParam {
  name: string;
  type: "string" | "number" | "date" | "enum" | "select";
  required: boolean;
  default?: string;
  description: string;
  options?: string[];
}

export interface TerminalEndpoint {
  id: string;
  path: string;
  label: string;
  description: string;
  category: string;
  params: TerminalParam[];
}

export interface TerminalCategory {
  id: string;
  label: string;
  icon: string;
  color: string;
}

export interface TerminalQueryResult {
  data: unknown;
  meta: {
    path: string;
    params: Record<string, string>;
    timestamp: string;
  };
}

export interface TerminalHealth {
  online: boolean;
  url: string;
  enabled: boolean;
}

// ── Trade Signals ────────────────────────────────────────────────────────────

export interface TradeSignal {
  ticker: string;
  market: Market;
  sector: string;
  composite_score: number;
  edge: number;
  direction: "bullish" | "bearish" | "neutral";
  bet: number;
  capped: boolean;
  current_price: number | null;
  pe_ttm: number | null;
  analyst_target: number | null;
  market_cap: number | null;
  strategy: string;
  kelly_fraction: number;
}

export interface TradeStrategy {
  id: string;
  name: string;
  description: string;
  icon: string;
  risk_profile: "conservative" | "balanced" | "aggressive";
  kelly_fraction: number;
  min_edge_score: number;
  max_positions: number;
  max_bet: number;
}

export interface TradeSignalsResponse {
  signals: TradeSignal[];
  strategy: TradeStrategy;
  n_signals: number;
  bankroll: number;
  fallback?: boolean;
  error?: string;
  drawdown: {
    total_pnl_today: number;
    limit_breached: boolean;
    warning_level: string;
  };
}

export interface CalibrationReport {
  hit_rate: number;
  avg_pnl: number;
  total_pnl: number;
  sharpe: number;
  profit_factor: number;
  n_trades: number;
  n_winners: number;
  n_losers: number;
  lookback_days: number;
}

export interface BacktestMetrics {
  total_return_pct: number;
  cagr_pct: number;
  sharpe: number;
  max_drawdown_pct: number;
  n_trades: number;
  years: number;
  initial_capital: number;
  final_equity: number;
}

export interface BacktestTrade {
  date: string;
  ticker: string;
  action: string;
  price: number;
  shares: number;
}

export interface BacktestResponse {
  equity_curve: { date: string; equity: number }[];
  trades: BacktestTrade[];
  metrics: BacktestMetrics;
  error?: string;
}

export interface RiskProfileConfig {
  profile: string;
  kelly_fraction: number;
  daily_loss_limit: number;
  max_bet: number;
  max_positions: number;
  description: string;
}


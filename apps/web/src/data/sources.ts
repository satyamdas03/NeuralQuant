export type DataSourceCategory =
  | "price_data"
  | "macro"
  | "alternative"
  | "news"
  | "india";

export interface DataSource {
  name: string;
  category: DataSourceCategory;
  coverage: ("US" | "IN" | "Global")[];
  description: string;
  icon: string;
}

export const SOURCES: DataSource[] = [
  {
    name: "Yahoo Finance",
    category: "price_data",
    coverage: ["US", "IN"],
    description:
      "OHLCV prices, fundamentals, market caps for 1,000+ tickers across NYSE, NASDAQ, and NSE",
    icon: "CandlestickChart",
  },
  {
    name: "FMP Premium",
    category: "price_data",
    coverage: ["US", "IN"],
    description:
      "Batch quotes, key metrics, income statements, balance sheets, analyst estimates, and consensus grades",
    icon: "Database",
  },
  {
    name: "FRED (Federal Reserve)",
    category: "macro",
    coverage: ["US"],
    description:
      "High-yield spreads, CPI, Fed funds rate, 2Y/10Y yield curve, ISM PMI",
    icon: "Landmark",
  },
  {
    name: "NSE Bhavcopy",
    category: "india",
    coverage: ["IN"],
    description:
      "End-of-day delivery percentages, OHLCV data, and corporate actions for NSE-listed stocks",
    icon: "BarChart3",
  },
  {
    name: "SEC EDGAR Form 4",
    category: "alternative",
    coverage: ["US"],
    description:
      "Real-time insider buying/selling filings — cluster scoring for corporate insiders",
    icon: "FileSearch",
  },
  {
    name: "News Aggregation",
    category: "news",
    coverage: ["US", "IN"],
    description:
      "Headlines from Yahoo Finance, Reuters, Economic Times — VADER sentiment scoring",
    icon: "Newspaper",
  },
  {
    name: "India VIX",
    category: "india",
    coverage: ["IN"],
    description:
      "Volatility index for India market regime detection — replaces US VIX for NSE",
    icon: "Activity",
  },
  {
    name: "US VIX",
    category: "macro",
    coverage: ["US"],
    description:
      "CBOE Volatility Index — key input for US regime detection and low-volatility factor",
    icon: "TrendingDown",
  },
  {
    name: "Reddit",
    category: "alternative",
    coverage: ["US", "IN"],
    description:
      "r/wallstreetbets, r/stocks, r/IndiaInvestments sentiment — bullish/bearish signal extraction",
    icon: "MessageSquare",
  },
  {
    name: "StockTwits",
    category: "alternative",
    coverage: ["US"],
    description:
      "Real-time ticker sentiment streams — bullish/bearish emoji classification",
    icon: "Hash",
  },
  {
    name: "DuckDB DataStore",
    category: "price_data",
    coverage: ["US", "IN"],
    description:
      "Zero-copy columnar cache — nightly score recomputation across full universe",
    icon: "Database",
  },
  {
    name: "QuantFactor Screener",
    category: "alternative",
    coverage: ["US", "IN"],
    description:
      "Cross-sectional quintile scoring across growth, return, valuation, and risk dimensions — 1,816 stocks",
    icon: "BarChart3",
  },
  {
    name: "Finnhub",
    category: "price_data",
    coverage: ["US", "IN"],
    description:
      "Real-time quotes, company news, insider transactions, and financials for US and international markets",
    icon: "CandlestickChart",
  },
  {
    name: "HMM Regime Detector",
    category: "alternative",
    coverage: ["US"],
    description:
      "4-state Hidden Markov Model (Risk-On, Late-Cycle, Bear, Recovery) — dynamic factor weighting",
    icon: "GitBranch",
  },
  {
    name: "SEC EDGAR Filings",
    category: "price_data",
    coverage: ["US"],
    description:
      "10-K, 10-Q financial statements for fundamental quality scoring (Piotroski F-Score)",
    icon: "FileText",
  },
];

export const CATEGORY_LABELS: Record<DataSourceCategory, string> = {
  price_data: "Price Data",
  macro: "Macro & Rates",
  alternative: "Alternative Signals",
  news: "News & Sentiment",
  india: "India-Specific",
};

export const CATEGORY_COLORS: Record<DataSourceCategory, string> = {
  price_data: "bg-secondary/10 text-secondary",
  macro: "bg-primary/10 text-primary",
  alternative: "bg-tertiary/10 text-tertiary",
  news: "bg-primary/10 text-primary",
  india: "bg-tertiary/10 text-tertiary",
};
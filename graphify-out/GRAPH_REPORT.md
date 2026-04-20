# Graph Report - C:/Users/point/projects/stockpredictor  (2026-04-12)

## Corpus Check
- 117 files · ~65,210 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 479 nodes · 624 edges · 79 communities detected
- Extraction: 80% EXTRACTED · 20% INFERRED · 0% AMBIGUOUS · INFERRED: 126 edges (avg confidence: 0.5)
- Token cost: 0 input · 0 output

## Community Hubs (Navigation)
- [[_COMMUNITY_Data Layer & Connectors|Data Layer & Connectors]]
- [[_COMMUNITY_Signal Engine Core|Signal Engine Core]]
- [[_COMMUNITY_PARA-DEBATE Agent System|PARA-DEBATE Agent System]]
- [[_COMMUNITY_Live Data Pipeline & FRED|Live Data Pipeline & FRED]]
- [[_COMMUNITY_Platform Concepts & Docs|Platform Concepts & Docs]]
- [[_COMMUNITY_Analyst Routes & Schemas|Analyst Routes & Schemas]]
- [[_COMMUNITY_LightGBM Ranker & Backtest|LightGBM Ranker & Backtest]]
- [[_COMMUNITY_NL Query Engine|NL Query Engine]]
- [[_COMMUNITY_DataBroker & Rate Limiting|DataBroker & Rate Limiting]]
- [[_COMMUNITY_EDGAR Insider Signals|EDGAR Insider Signals]]
- [[_COMMUNITY_Report Generator (JS)|Report Generator (JS)]]
- [[_COMMUNITY_Report Generator (Python)|Report Generator (Python)]]
- [[_COMMUNITY_Backtest Tests|Backtest Tests]]
- [[_COMMUNITY_Market Overview Routes|Market Overview Routes]]
- [[_COMMUNITY_Head Analyst Agent|Head Analyst Agent]]
- [[_COMMUNITY_Momentum Factor|Momentum Factor]]
- [[_COMMUNITY_Momentum Factor Tests|Momentum Factor Tests]]
- [[_COMMUNITY_Backtest Runner|Backtest Runner]]
- [[_COMMUNITY_Stock Detail Routes|Stock Detail Routes]]
- [[_COMMUNITY_Market Dashboard UI|Market Dashboard UI]]
- [[_COMMUNITY_Community 20|Community 20]]
- [[_COMMUNITY_Community 21|Community 21]]
- [[_COMMUNITY_Community 22|Community 22]]
- [[_COMMUNITY_Community 23|Community 23]]
- [[_COMMUNITY_Community 24|Community 24]]
- [[_COMMUNITY_Community 25|Community 25]]
- [[_COMMUNITY_Community 26|Community 26]]
- [[_COMMUNITY_Community 27|Community 27]]
- [[_COMMUNITY_Community 28|Community 28]]
- [[_COMMUNITY_Community 29|Community 29]]
- [[_COMMUNITY_Community 30|Community 30]]
- [[_COMMUNITY_Community 31|Community 31]]
- [[_COMMUNITY_Community 32|Community 32]]
- [[_COMMUNITY_Community 33|Community 33]]
- [[_COMMUNITY_Community 34|Community 34]]
- [[_COMMUNITY_Community 35|Community 35]]
- [[_COMMUNITY_Community 36|Community 36]]
- [[_COMMUNITY_Community 37|Community 37]]
- [[_COMMUNITY_Community 38|Community 38]]
- [[_COMMUNITY_Community 39|Community 39]]
- [[_COMMUNITY_Community 40|Community 40]]
- [[_COMMUNITY_Community 41|Community 41]]
- [[_COMMUNITY_Community 42|Community 42]]
- [[_COMMUNITY_Community 43|Community 43]]
- [[_COMMUNITY_Community 44|Community 44]]
- [[_COMMUNITY_Community 45|Community 45]]
- [[_COMMUNITY_Community 46|Community 46]]
- [[_COMMUNITY_Community 47|Community 47]]
- [[_COMMUNITY_Community 48|Community 48]]
- [[_COMMUNITY_Community 49|Community 49]]
- [[_COMMUNITY_Community 50|Community 50]]
- [[_COMMUNITY_Community 51|Community 51]]
- [[_COMMUNITY_Community 52|Community 52]]
- [[_COMMUNITY_Community 53|Community 53]]
- [[_COMMUNITY_Community 54|Community 54]]
- [[_COMMUNITY_Community 55|Community 55]]
- [[_COMMUNITY_Community 56|Community 56]]
- [[_COMMUNITY_Community 57|Community 57]]
- [[_COMMUNITY_Community 58|Community 58]]
- [[_COMMUNITY_Community 59|Community 59]]
- [[_COMMUNITY_Community 60|Community 60]]
- [[_COMMUNITY_Community 61|Community 61]]
- [[_COMMUNITY_Community 62|Community 62]]
- [[_COMMUNITY_Community 63|Community 63]]
- [[_COMMUNITY_Community 64|Community 64]]
- [[_COMMUNITY_Community 65|Community 65]]
- [[_COMMUNITY_Community 66|Community 66]]
- [[_COMMUNITY_Community 67|Community 67]]
- [[_COMMUNITY_Community 68|Community 68]]
- [[_COMMUNITY_Community 69|Community 69]]
- [[_COMMUNITY_Community 70|Community 70]]
- [[_COMMUNITY_Community 71|Community 71]]
- [[_COMMUNITY_Community 72|Community 72]]
- [[_COMMUNITY_Community 73|Community 73]]
- [[_COMMUNITY_Community 74|Community 74]]
- [[_COMMUNITY_Community 75|Community 75]]
- [[_COMMUNITY_Community 76|Community 76]]
- [[_COMMUNITY_Community 77|Community 77]]
- [[_COMMUNITY_Community 78|Community 78]]

## God Nodes (most connected - your core abstractions)
1. `UniverseSnapshot` - 17 edges
2. `BaseAnalystAgent` - 14 edges
3. `ParaDebateOrchestrator` - 14 edges
4. `FREDConnector` - 14 edges
5. `OHLCVBar` - 13 edges
6. `DataStore` - 12 edges
7. `SignalEngine` - 12 edges
8. `RegimeDetector` - 12 edges
9. `AgentOutput` - 10 edges
10. `SignalRanker` - 10 edges

## Surprising Connections (you probably didn't know these)
- `Base agent class for NeuralQuant PARA-DEBATE analyst team.` --uses--> `AgentOutput`  [INFERRED]
  C:\Users\point\projects\stockpredictor\apps\api\src\nq_api\agents\base.py → C:\Users\point\projects\stockpredictor\apps\api\src\nq_api\schemas.py
- `One analyst in the PARA-DEBATE panel.` --uses--> `AgentOutput`  [INFERRED]
  C:\Users\point\projects\stockpredictor\apps\api\src\nq_api\agents\base.py → C:\Users\point\projects\stockpredictor\apps\api\src\nq_api\schemas.py
- `HEAD ANALYST — not a BaseAnalystAgent subclass (different run interface).` --uses--> `AgentOutput`  [INFERRED]
  C:\Users\point\projects\stockpredictor\apps\api\src\nq_api\agents\head_analyst.py → C:\Users\point\projects\stockpredictor\apps\api\src\nq_api\schemas.py
- `Fetch a single FRED series; returns None on any error (retired/missing series, e` --uses--> `MacroSnapshot`  [INFERRED]
  C:\Users\point\projects\stockpredictor\packages\data\src\nq_data\macro\fred_connector.py → C:\Users\point\projects\stockpredictor\packages\data\src\nq_data\models.py
- `Lazy singleton for ParaDebateOrchestrator — avoids 7 agent instantiations per re` --uses--> `ParaDebateOrchestrator`  [INFERRED]
  C:\Users\point\projects\stockpredictor\apps\api\src\nq_api\deps.py → C:\Users\point\projects\stockpredictor\apps\api\src\nq_api\agents\orchestrator.py

## Communities

### Community 0 - "Data Layer & Connectors"
Cohesion: 0.07
Nodes (20): FundamentalSnapshot, MacroSnapshot, NewsItem, OHLCVBar, NSEBhavCopyConnector, NSE Bhavcopy downloader. Completely free, no API key. Bhavcopy URL pattern: http, Convert value to float, treating NaN/None as default., Download and parse Bhavcopy for a given date. (+12 more)

### Community 1 - "Signal Engine Core"
Cohesion: 0.07
Nodes (28): get_orchestrator(), Lazy singleton for ParaDebateOrchestrator — avoids 7 agent instantiations per re, Signal Engine Orchestrator — computes all 10 signals and produces a ranked unive, Get current market regime from macro snapshot., Compute all signals and return regime-weighted composite scores.         Returns, SignalEngine, 4-State Hidden Markov Model for market regime detection. States:   1 = Risk-On /, Return soft posterior probabilities. Shape: (n_rows, n_regimes). (+20 more)

### Community 2 - "PARA-DEBATE Agent System"
Cohesion: 0.08
Nodes (18): ABC, AdversarialAgent, BaseAnalystAgent, _build_user_message(), Base agent class for NeuralQuant PARA-DEBATE analyst team., One analyst in the PARA-DEBATE panel., BaseAnalystAgent, FundamentalAgent (+10 more)

### Community 3 - "Live Data Pipeline & FRED"
Cohesion: 0.16
Nodes (22): _add_value_and_lowvol_percentiles(), build_real_snapshot(), fetch_fundamentals_batch(), _fetch_one(), fetch_real_macro(), _LiveMacro, _piotroski_from_info(), prewarm_cache() (+14 more)

### Community 4 - "Platform Concepts & Docs"
Cohesion: 0.12
Nodes (25): 5-Factor Quant Model, NeuralQuant Platform, PARA-DEBATE Protocol, Adversarial Agent Design, AskAI Improvements Plan, Backtest Results (2021Q4â€“2025Q4), Competitive Positioning, Deployment Architecture (+17 more)

### Community 5 - "Analyst Routes & Schemas"
Cohesion: 0.16
Nodes (20): POST /analyst — runs PARA-DEBATE and returns full analyst report., BaseModel, AgentOutput, AIScore, AnalystRequest, AnalystResponse, ConversationMessage, FeatureDriver (+12 more)

### Community 6 - "LightGBM Ranker & Backtest"
Cohesion: 0.11
Nodes (16): LightGBM LambdaRank — cross-sectional stock ranking model. Framing: learning-to-, Train LambdaRank on panel data.         df: DataFrame with feature_cols, target_, Return ranking scores. Higher = better expected return., SignalRanker, make_synthetic_data(), IC should be positive when predictions correlate with actual returns., Make fake factor + return data for testing., test_ic_is_positive_with_signal() (+8 more)

### Community 7 - "NL Query Engine"
Cohesion: 0.26
Nodes (15): _detect_tickers_in_question(), _enrich_with_platform_data(), _fetch_dynamic_nse_stock(), _fetch_india_macro(), _fetch_relevant_news(), _parse_query_response(), POST /query — natural language financial query endpoint., Pull recent headlines from yfinance for context injection. (+7 more)

### Community 8 - "DataBroker & Rate Limiting"
Cohesion: 0.19
Nodes (8): acquire(), DataBroker, Central rate-limit manager. All data connectors must go through this., SourceConfig, When burst capacity exceeded, DataBroker should call time.sleep., DataBroker should pace requests to stay within rate limits., test_broker_enforces_rate_limit(), test_broker_rate_limits_when_saturated()

### Community 9 - "EDGAR Insider Signals"
Cohesion: 0.17
Nodes (8): compute_insider_cluster_score(), Form4Connector, SEC EDGAR Form 4 insider trading signals. Free API: https://efts.sec.gov/LATEST/, Fetch Form 4 filings for a ticker from EDGAR full-text search.          Returns, Return parsed insider transaction events. Override _fetch_raw in tests., Score from 0.0 to 1.0 based on insider buying cluster.     Algorithm:     - Coun, A cluster of insider buys should return positive signal score., test_form4_cluster_signal()

### Community 10 - "Report Generator (JS)"
Cohesion: 0.21
Nodes (4): callout(), cell(), hcell(), shading()

### Community 11 - "Report Generator (Python)"
Cohesion: 0.27
Nodes (5): HR(), P(), NeuralQuant — Business Intelligence & Competitive Analysis Report Generates a pr, section(), sub()

### Community 12 - "Backtest Tests"
Cohesion: 0.22
Nodes (9): make_v8_csv(), Unit tests for the backtest runner. Tests the data loading/mapping and the walk-, Create a minimal V8-format CSV for testing., V8 CSV columns are correctly renamed to NeuralQuant signal names., r"""\\N values in Return column must be treated as NaN, not crash., walk_forward_validate runs end-to-end and returns expected keys., test_backtest_runs_with_synthetic_data(), test_load_and_map_v8_data() (+1 more)

### Community 13 - "Market Overview Routes"
Cohesion: 0.28
Nodes (6): data_quality(), market_overview(), market_sectors(), _pct_change(), GET /market — live market data via yfinance., Shows live data quality: how many tickers are real vs synthetic, full macro snap

### Community 14 - "Head Analyst Agent"
Cohesion: 0.36
Nodes (2): HeadAnalystAgent, HEAD ANALYST — not a BaseAnalystAgent subclass (different run interface).

### Community 15 - "Momentum Factor"
Cohesion: 0.29
Nodes (6): apply_crash_protection(), compute_momentum_12_1(), compute_momentum_cross_sectional(), Returns True when momentum should be suppressed (crash risk high).     Triggers, Cross-sectional momentum ranking.     universe: DataFrame with ticker, momentum_, Classic 12-1 momentum: return from 12 months ago to 1 month ago.     Skips most

### Community 16 - "Momentum Factor Tests"
Cohesion: 0.38
Nodes (5): make_price_series(), In bear regime (SPX below 200MA), crash-protection flag should be True., test_crash_protection_disables_momentum_in_bear(), test_momentum_12_1_positive(), test_momentum_12_1_skips_last_month()

### Community 17 - "Backtest Runner"
Cohesion: 0.38
Nodes (6): load_historical_data(), load_v8_csv(), main(), Backtest runner — validates signal engine on historical quarters. Uses walk-forw, Load a V8-format CSV and normalise it for the backtest runner., Load all CSV files from data_dir and concatenate.

### Community 18 - "Stock Detail Routes"
Cohesion: 0.53
Nodes (4): _fmt_mcap(), get_stock_chart(), get_stock_meta(), _yf_sym()

### Community 19 - "Market Dashboard UI"
Cohesion: 0.33
Nodes (0): 

### Community 20 - "Community 20"
Cohesion: 0.73
Nodes (5): addToWatchlist(), getWatchlist(), isWatchlisted(), removeFromWatchlist(), toggleWatchlist()

### Community 21 - "Community 21"
Cohesion: 0.33
Nodes (5): compute_piotroski_score(), compute_quality_composite(), Quality Composite Signal — IC ~0.06-0.08. Components:   1. Piotroski F-Score (0-, Compute Piotroski F-Score (0-9) from fundamental data dictionary.     Higher = b, Compute cross-sectional quality composite for a universe of stocks.     Input Da

### Community 22 - "Community 22"
Cohesion: 0.47
Nodes (5): make_fundamental(), Quality composite should return percentile ranks across a universe., test_piotroski_score_high_quality(), test_piotroski_score_low_quality(), test_quality_composite_cross_sectional_rank()

### Community 23 - "Community 23"
Cohesion: 0.53
Nodes (5): main(), print_ic_table(), print_separator(), Backtest report generator. Reads the IC CSV output from run_backtest.py and prin, Print a formatted IC by-period table with rolling mean.

### Community 24 - "Community 24"
Cohesion: 0.7
Nodes (4): _mock_analyst_response(), _patch_analyst(), test_analyst_post_returns_report(), test_analyst_verdict_is_valid()

### Community 25 - "Community 25"
Cohesion: 0.6
Nodes (3): _mock_all_agents(), test_orchestrator_adversarial_is_always_bear(), test_orchestrator_returns_analyst_response()

### Community 26 - "Community 26"
Cohesion: 0.5
Nodes (3): _mock_engine_result(), Minimal engine output for a single ticker., test_get_stock_score_returns_ai_score()

### Community 27 - "Community 27"
Cohesion: 0.4
Nodes (0): 

### Community 28 - "Community 28"
Cohesion: 0.83
Nodes (3): _mock_engine_for_universe(), test_screener_filters_by_min_score(), test_screener_returns_ranked_list()

### Community 29 - "Community 29"
Cohesion: 0.67
Nodes (0): 

### Community 30 - "Community 30"
Cohesion: 0.67
Nodes (0): 

### Community 31 - "Community 31"
Cohesion: 0.67
Nodes (0): 

### Community 32 - "Community 32"
Cohesion: 0.67
Nodes (0): 

### Community 33 - "Community 33"
Cohesion: 0.67
Nodes (0): 

### Community 34 - "Community 34"
Cohesion: 0.67
Nodes (0): 

### Community 35 - "Community 35"
Cohesion: 1.0
Nodes (2): make_mock_snapshot(), test_engine_returns_ranked_universe()

### Community 36 - "Community 36"
Cohesion: 1.0
Nodes (0): 

### Community 37 - "Community 37"
Cohesion: 1.0
Nodes (0): 

### Community 38 - "Community 38"
Cohesion: 1.0
Nodes (0): 

### Community 39 - "Community 39"
Cohesion: 1.0
Nodes (0): 

### Community 40 - "Community 40"
Cohesion: 1.0
Nodes (0): 

### Community 41 - "Community 41"
Cohesion: 1.0
Nodes (0): 

### Community 42 - "Community 42"
Cohesion: 1.0
Nodes (0): 

### Community 43 - "Community 43"
Cohesion: 1.0
Nodes (0): 

### Community 44 - "Community 44"
Cohesion: 1.0
Nodes (0): 

### Community 45 - "Community 45"
Cohesion: 1.0
Nodes (0): 

### Community 46 - "Community 46"
Cohesion: 1.0
Nodes (0): 

### Community 47 - "Community 47"
Cohesion: 1.0
Nodes (0): 

### Community 48 - "Community 48"
Cohesion: 1.0
Nodes (0): 

### Community 49 - "Community 49"
Cohesion: 1.0
Nodes (0): 

### Community 50 - "Community 50"
Cohesion: 1.0
Nodes (0): 

### Community 51 - "Community 51"
Cohesion: 1.0
Nodes (0): 

### Community 52 - "Community 52"
Cohesion: 1.0
Nodes (0): 

### Community 53 - "Community 53"
Cohesion: 1.0
Nodes (0): 

### Community 54 - "Community 54"
Cohesion: 1.0
Nodes (0): 

### Community 55 - "Community 55"
Cohesion: 1.0
Nodes (0): 

### Community 56 - "Community 56"
Cohesion: 1.0
Nodes (0): 

### Community 57 - "Community 57"
Cohesion: 1.0
Nodes (0): 

### Community 58 - "Community 58"
Cohesion: 1.0
Nodes (0): 

### Community 59 - "Community 59"
Cohesion: 1.0
Nodes (0): 

### Community 60 - "Community 60"
Cohesion: 1.0
Nodes (0): 

### Community 61 - "Community 61"
Cohesion: 1.0
Nodes (0): 

### Community 62 - "Community 62"
Cohesion: 1.0
Nodes (0): 

### Community 63 - "Community 63"
Cohesion: 1.0
Nodes (0): 

### Community 64 - "Community 64"
Cohesion: 1.0
Nodes (0): 

### Community 65 - "Community 65"
Cohesion: 1.0
Nodes (0): 

### Community 66 - "Community 66"
Cohesion: 1.0
Nodes (0): 

### Community 67 - "Community 67"
Cohesion: 1.0
Nodes (0): 

### Community 68 - "Community 68"
Cohesion: 1.0
Nodes (0): 

### Community 69 - "Community 69"
Cohesion: 1.0
Nodes (0): 

### Community 70 - "Community 70"
Cohesion: 1.0
Nodes (0): 

### Community 71 - "Community 71"
Cohesion: 1.0
Nodes (0): 

### Community 72 - "Community 72"
Cohesion: 1.0
Nodes (0): 

### Community 73 - "Community 73"
Cohesion: 1.0
Nodes (0): 

### Community 74 - "Community 74"
Cohesion: 1.0
Nodes (0): 

### Community 75 - "Community 75"
Cohesion: 1.0
Nodes (0): 

### Community 76 - "Community 76"
Cohesion: 1.0
Nodes (0): 

### Community 77 - "Community 77"
Cohesion: 1.0
Nodes (1): Next.js Public SVG Assets

### Community 78 - "Community 78"
Cohesion: 1.0
Nodes (1): Obsidian Knowledge Graph Vault

## Knowledge Gaps
- **35 isolated node(s):** `GET /market — live market data via yfinance.`, `Shows live data quality: how many tickers are real vs synthetic, full macro snap`, `Minimal engine output for a single ticker.`, `NeuralQuant — Business Intelligence & Competitive Analysis Report Generates a pr`, `Central rate-limit manager. All data connectors must go through this.` (+30 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **Thin community `Community 36`** (2 nodes): `screener.py`, `run_screener()`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 37`** (2 nodes): `layout.tsx`, `RootLayout()`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 38`** (2 nodes): `page.tsx`, `QueryPage()`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 39`** (2 nodes): `page.tsx`, `load()`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 40`** (2 nodes): `FeatureAttribution.tsx`, `FeatureAttribution()`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 41`** (2 nodes): `PriceChart.tsx`, `CustomTooltip()`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 42`** (2 nodes): `RegimeBadge.tsx`, `RegimeBadge()`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 43`** (2 nodes): `ScoreBreakdown.tsx`, `ScoreBreakdown()`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 44`** (2 nodes): `StockMetaBar.tsx`, `MetaItem()`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 45`** (2 nodes): `Badge()`, `badge.tsx`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 46`** (2 nodes): `cn()`, `button.tsx`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 47`** (2 nodes): `input.tsx`, `Input()`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 48`** (2 nodes): `skeleton.tsx`, `Skeleton()`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 49`** (2 nodes): `tabs.tsx`, `cn()`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 50`** (2 nodes): `apiFetch()`, `api.ts`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 51`** (2 nodes): `utils.ts`, `cn()`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 52`** (2 nodes): `conftest.py`, `tmp_store()`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 53`** (2 nodes): `test_macro.py`, `test_fred_connector_builds_snapshot()`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 54`** (1 nodes): `universe.py`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 55`** (1 nodes): `__init__.py`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 56`** (1 nodes): `__init__.py`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 57`** (1 nodes): `__init__.py`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 58`** (1 nodes): `__init__.py`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 59`** (1 nodes): `next-env.d.ts`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 60`** (1 nodes): `next.config.ts`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 61`** (1 nodes): `AgentDebatePanel.tsx`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 62`** (1 nodes): `hero-buttons.tsx`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 63`** (1 nodes): `ScreenerTable.tsx`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 64`** (1 nodes): `types.ts`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 65`** (1 nodes): `__init__.py`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 66`** (1 nodes): `__init__.py`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 67`** (1 nodes): `__init__.py`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 68`** (1 nodes): `__init__.py`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 69`** (1 nodes): `__init__.py`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 70`** (1 nodes): `__init__.py`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 71`** (1 nodes): `__init__.py`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 72`** (1 nodes): `__init__.py`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 73`** (1 nodes): `conftest.py`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 74`** (1 nodes): `__init__.py`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 75`** (1 nodes): `__init__.py`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 76`** (1 nodes): `__init__.py`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 77`** (1 nodes): `Next.js Public SVG Assets`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 78`** (1 nodes): `Obsidian Knowledge Graph Vault`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `MacroSnapshot` connect `Community 0` to `Community 3`, `Community 5`?**
  _High betweenness centrality (0.053) - this node is a cross-community bridge._
- **Why does `FREDConnector` connect `Community 3` to `Community 0`?**
  _High betweenness centrality (0.048) - this node is a cross-community bridge._
- **Why does `AgentOutput` connect `Community 5` to `Community 2`, `Community 14`?**
  _High betweenness centrality (0.048) - this node is a cross-community bridge._
- **Are the 16 inferred relationships involving `UniverseSnapshot` (e.g. with `_LiveMacro` and `Phase 3 real data builder — 100% live data, zero synthetic fallbacks where avoid`) actually correct?**
  _`UniverseSnapshot` has 16 INFERRED edges - model-reasoned connections that need verification._
- **Are the 7 inferred relationships involving `BaseAnalystAgent` (e.g. with `AdversarialAgent` and `AgentOutput`) actually correct?**
  _`BaseAnalystAgent` has 7 INFERRED edges - model-reasoned connections that need verification._
- **Are the 11 inferred relationships involving `ParaDebateOrchestrator` (e.g. with `Lazy singleton for ParaDebateOrchestrator — avoids 7 agent instantiations per re` and `AgentOutput`) actually correct?**
  _`ParaDebateOrchestrator` has 11 INFERRED edges - model-reasoned connections that need verification._
- **Are the 10 inferred relationships involving `FREDConnector` (e.g. with `_LiveMacro` and `Phase 3 real data builder — 100% live data, zero synthetic fallbacks where avoid`) actually correct?**
  _`FREDConnector` has 10 INFERRED edges - model-reasoned connections that need verification._
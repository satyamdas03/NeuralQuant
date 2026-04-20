<!-- converted from NeuralQuant_Report.docx -->




NeuralQuant
Business & Competitive Intelligence Report
Version 3.0  —  March 2026


AI-Powered Stock Intelligence Platform
5-Factor Quant Engine  ·  7-Agent PARA-DEBATE  ·  US & India  ·  100% Live Data

# 1. Executive Summary
NeuralQuant is a full-stack AI stock intelligence platform that delivers institutional-grade quantitative research at retail price. It combines a 5-factor signal engine (Quality, Momentum, Value, Low-Volatility, Short Interest) with a 7-agent PARA-DEBATE system powered by Claude Sonnet 4.6 to produce explainable, opinionated investment intelligence for both US and Indian (NSE) equity markets — backed entirely by live data from FRED and yfinance.

## Key Numbers at a Glance
- 50 US stocks + 50 NSE stocks scored in real time
- 19 live data sources: FRED (HY spreads, CPI, yields), yfinance (prices, fundamentals, news)
- 7 AI agents running in parallel per analysis, synthesised by a HEAD ANALYST
- 5-factor model with rank-normalised 1–10 scores — zero synthetic data
- Multi-turn NL query that cites the platform’s own live scores and prices

Core thesis: The gap in the market is not data — Bloomberg and FactSet have data. The gap is affordable, explainable, AI-debated conviction. NeuralQuant fills that gap.
# 2. Competitive Landscape
The following table benchmarks NeuralQuant against eight established competitors across key dimensions that matter most to retail and professional investors.


## NeuralQuant vs Perplexity Finance
Perplexity Finance is a general-purpose LLM with financial news access. It cannot run a screener, produce a factor score, or cite proprietary signals. NeuralQuant’s query engine injects live macro data (VIX, HY spreads, CPI, Fed funds), screener rankings, and 52-week price ranges before every LLM call — making every answer data-grounded and citable.
## NeuralQuant vs Danelfin
Danelfin scores stocks using 100+ ML features but operates as a black box — users cannot see why NVDA scores 8/10. NeuralQuant exposes all five factor percentiles, the regime label, and confidence — giving actionable conviction rather than an opaque number.
## NeuralQuant vs Bloomberg Terminal
Bloomberg provides the deepest institutional data at $2,000+/month per seat — inaccessible to retail investors. NeuralQuant delivers 80–90% of actionable insight (live macro, fundamentals, factor scores, AI synthesis) at 1–50% of the cost.
# 3. Unique Selling Propositions (USPs)
## USP 1 — PARA-DEBATE: 7-Agent AI Conviction Engine
Most AI finance tools wrap a single LLM call. NeuralQuant runs seven specialised agents concurrently via asyncio — MACRO, FUNDAMENTAL, TECHNICAL, SENTIMENT, GEOPOLITICAL, ADVERSARIAL, and HEAD ANALYST — each with its own system prompt and data slice. The HEAD ANALYST synthesises their outputs into a structured verdict with a conviction score, key bull/bear points, and an explicit risk assessment. This architecture produces genuinely conflicted, nuanced analysis rather than confident-sounding hallucinations.
## USP 2 — Self-Aware NL Query Engine
The natural language query endpoint is the only LLM-powered financial query system that automatically detects whether the user’s question needs the platform’s own screener data and injects it before the LLM call. Ask “what are your top picks right now?” and the system fetches live screener rankings, factor percentiles, and injects them as structured context. No other AI finance product achieves this loop between LLM and its own quantitative backend.
## USP 3 — 5-Factor Quant Model with Rank-Normalised Scoring
NeuralQuant implements the full academic factor zoo — Piotroski F-score quality, Jegadeesh-Titman momentum, P/E + P/B value, realised-volatility low-vol, and short-float short-interest — with cross-sectional percentile ranking that guarantees a meaningful 1–10 spread. Scores are computed within a 20-stock reference universe per market.
## USP 4 — 100% Live Data Pipeline
Every score is computed from live data at request time. FRED provides HY credit spreads, CPI, Fed funds rate, and 10Y/2Y yields. yfinance provides prices, fundamentals, and real-time news headlines. No batch job, no overnight stale cache. The 4-hour fundamental cache and 1-hour macro cache refresh continuously in a ThreadPoolExecutor with 12 workers.
## USP 5 — India (NSE) Market Coverage
No direct competitor at this price point covers NSE stocks with the same depth. NeuralQuant scores 50 NSE stocks with the same 5-factor model, regime detection, and PARA-DEBATE analysis. India’s 90M+ Demat account market has no equivalent tool in this price range.
## USP 6 — Full Explainability at Every Layer
Every 1–10 score shows the five underlying factor percentiles. Every PARA-DEBATE analysis shows each agent’s perspective. Every NL query response cites its data sources. No black boxes — this builds user trust and supports investment decision documentation for RIAs.
# 4. Known Drawbacks & Honest Limitations
A credible business document must acknowledge what the platform does not yet do well. All limitations below have clear Phase 4/5 fixes.

# 5. Why People Should Use NeuralQuant
## For the Retail Investor
Most retail investors make stock decisions based on social media or a quick P/E glance. NeuralQuant gives them the same five factors quantitative hedge funds use — at a price they can afford. They get a clear 1–10 score, a regime-aware context, and an AI debate that surfaces the bear case they might not have considered.
## For the Registered Investment Advisor (RIA)
RIAs need to document their investment thesis. NeuralQuant’s PARA-DEBATE output gives them a structured, citable analysis per stock — MACRO, FUNDAMENTAL, TECHNICAL, SENTIMENT, GEOPOLITICAL perspectives — that can be included in client reports. At $49–$99/month, it costs less than one hour of a junior analyst’s time.
## For the Quant Researcher
The /screener and /stocks API endpoints expose raw factor percentiles, composite scores, regime IDs, and confidence as JSON. Quant researchers can pipe NeuralQuant’s signals into their own models, backtest regime-conditional strategies, or use India NSE data as a diversification signal.
## For the Indian Investor
The NSE market is underserved by Western analytics tools. NeuralQuant scores 50 top NSE stocks with the same rigour as US equities — live yfinance fundamentals, Jegadeesh-Titman momentum, P/B value, and short-interest signals — plus a query engine that understands Indian market context.
# 6. Monetisation Strategy
## 6.1 Pricing Tiers


## 6.2 Revenue Streams
- Subscription SaaS — primary revenue; recurring, predictable, high gross margin
- API Usage Overage — $0.01/call above tier limit; scales naturally with power users
- Data Licensing — NSE factor scores licensed to Indian brokerages and robo-advisors
- White-Label — NeuralQuant engine embedded in third-party platforms under revenue share
- Affiliate / Referral — brokerage referrals (Zerodha, IBKR) on account opens via the platform

## 6.3 Revenue Projections (Conservative)
Assumes 5% monthly user growth, 8% free-to-paid conversion, and $30 average ARPU at Month 24:


At Month 24, a $1M ARR run-rate at 85% gross margin positions NeuralQuant for a Seed or Series A raise at a 5-10x ARR multiple ($5-10M valuation).


## 6.4 Unit Economics
- Estimated COGS per paid user: ~$2–3/month (Claude API + yfinance data + hosting)
- Gross margin target: 85–90% at scale
- CAC: $15–25 via content marketing + SEO + community
- LTV at $30 ARPU, 18-month avg. retention: $540 — LTV:CAC ratio of ~25x
# 7. Go-To-Market Strategy
## Phase 1: Seed Community (Months 1–3)
Target finance-forward communities: r/IndiaInvestments, r/stocks, r/quantfinance, Substack finance newsletters, and Indian stock trading Telegram groups. Release a free tier with generous limits. Publish weekly ‘NeuralQuant Weekly’ reports showcasing the PARA-DEBATE output on trending stocks. Goal: 1,000 free signups, 50 paid conversions.
## Phase 2: Paid Conversion Engine (Months 4–9)
Gate PARA-DEBATE behind the Investor tier. Use the free tier as a loss leader — users who see a PARA-DEBATE preview will convert to unlock the full debate. Partner with mid-sized Indian stock trading communities for co-branded content. Launch an affiliate program. Goal: 200 paid users, $5,000 MRR.
## Phase 3: Enterprise & API (Months 10+)
Pitch the API tier to fintech startups building robo-advisors or portfolio tools. Approach Indian brokerages (Zerodha, Groww, Angel One) with a data licensing proposal for NSE factor scores. Explore white-label for wealth management platforms. Goal: 2 enterprise contracts, $20,000+ MRR.
# 8. Technology Moat
Technology moats in AI products compound over time. NeuralQuant’s defensibility comes from five overlapping sources:


# 9. Risks & Mitigations


# 10. Conclusion
NeuralQuant occupies a genuinely underserved position in the financial intelligence market: sophisticated enough for professional use, affordable enough for retail, and explainable enough for both. Its combination of a 5-factor quantitative model, a 7-agent AI debate system, live macro data integration, and India NSE coverage creates a product with multiple overlapping defensibilities.

The largest risk is not technical — it is distribution. The platform needs to reach the communities that will benefit from it most. With a well-executed free tier, a content-led growth motion, and a clear API monetisation path, NeuralQuant is positioned to reach $1M ARR within 24 months.

The question is not whether the market needs a tool like this. The question is who builds it best, fastest, and at the right price point. NeuralQuant is already there.
## Summary Scorecard


| Platform | AI Analysis | Quant Model | Live Data | India | Price/mo | Explainable |
| --- | --- | --- | --- | --- | --- | --- |
| NeuralQuant | 7-Agent PARA-DEBATE | 5-Factor + Regime | FRED + yfinance | ✓ 50 NSE | Free–$99 | ✓ Full |
| Perplexity Finance | General LLM Q&A | None | News + web | ✘ | Free–$20 | ✘ Black box |
| Danelfin | ML score | 100+ features | Delayed | ✘ | $30–$150 | Partial |
| FactSet Mercury | GPT-4 wrapper | FactSet data | Full institutional | ✓ Global | $500+ | ✘ |
| Simply Wall St | Rule templates | None | EOD | Partial | $15–$30 | Partial |
| Trade Ideas | Holly AI signals | Momentum only | Real-time US | ✘ | $84–$167 | ✘ |
| Seeking Alpha | Contributor + AI | Quant ratings | Delayed | ✘ | $19–$240 | Partial |
| Bloomberg Terminal | None native | B-QUANT Python | Full real-time | ✓ Global | $2,000+ | ✘ |
| Yahoo Finance | None | None | 15-min delay | ✓ BSE/NSE | Free–$25 | ✘ |
| Limitation | Severity | Planned Fix |
| --- | --- | --- |
| ISM PMI not on FRED’s free tier — defaults to neutral 51.0 | Medium | Phase 4: alternative PMI source |
| Universe limited to 100 stocks (50 US + 50 NSE) | Medium | Phase 4: expand to 500 US + 200 NSE |
| No intraday scoring — refreshes on request, not streamed | Low | Phase 5: WebSocket streaming |
| Sector-agnostic quality (banks use same gross margin model) | Medium | Phase 4: sector-adjusted factors (ROE/NIM for banks) |
| No user auth or persistent watchlists | High (UX) | Phase 4: Supabase auth + watchlists |
| HMM regime uses heuristic rules, not fitted historical model | Medium | Phase 4: fitted HMM on FRED history |
| No earnings calendar or insider transaction signals | Low | Phase 5: EDGAR Form 4 wiring |
| Tier | Price/mo | Features | Target User |
| --- | --- | --- | --- |
| Free | $0 | 10 stock scores/day, screener top 5, NL query (3/day) | Casual retail, discovery |
| Investor | $19 | Unlimited scores, screener top 20, NL query (50/day), PARA-DEBATE (5/day) | Active retail investor |
| Pro | $49 | All Investor + full PARA-DEBATE, India NSE, API (1K calls/mo) | Serious investor / RIA |
| API | $99 | 10K API calls/month, all endpoints, raw factor data, bulk screener | Developers, quant researchers |
| Enterprise | Custom | Unlimited API, SLA, dedicated support, white-label option | Hedge funds, fintech platforms |
| Month | Free Users | Paid Users | Avg. ARPU | MRR | ARR Run-Rate |
| --- | --- | --- | --- | --- | --- |
| 1 | 500 | 40 | $22 | $880 | $10,560 |
| 3 | 1,100 | 88 | $25 | $2,200 | $26,400 |
| 6 | 2,800 | 224 | $27 | $6,048 | $72,576 |
| 12 | 7,400 | 590 | $30 | $17,700 | $212,400 |
| 18 | 16,000 | 1,280 | $33 | $42,240 | $506,880 |
| 24 | 30,000 | 2,400 | $35 | $84,000 | $1,008,000 |
| Moat | Description | Replication Difficulty |
| --- | --- | --- |
| PARA-DEBATE Architecture | 7-agent concurrent debate with HEAD ANALYST synthesis — prompt engineering + orchestration know-how baked over many iterations | Medium — 3–6 months |
| Self-Aware Query Loop | LLM detects when to fetch its own screener and injects structured data pre-call — a non-obvious architectural pattern | Low-Medium — 1–3 months |
| 5-Factor Live Pipeline | FRED + yfinance integrated data pipeline with regime detection and cross-sectional ranking, tuned for real market conditions | Medium — 4–8 months |
| India NSE Coverage | Deep NSE data pipeline, Indian market regime awareness, Nifty/Sensex context, and Indian community distribution | Medium — 2–4 months |
| User Trust & Feedback Loop | As users query the platform, the most useful follow-up questions and edge cases surface for product improvement | High — takes 12+ months |
| Risk | Likelihood | Impact | Mitigation |
| --- | --- | --- | --- |
| yfinance rate limits or API changes | Medium | High | Abstract data layer; fallback to Alpha Vantage / Polygon.io |
| Anthropic API cost spikes at scale | Low | Medium | Cache LLM responses for identical queries; tier-gate PARA-DEBATE |
| Regulatory: investment advice without licence | Medium | High | All outputs labelled educational, not financial advice; no buy/sell orders executed |
| Competitor replication by Perplexity or Bloomberg | Low | High | Speed of iteration + India moat + community lock-in |
| yfinance data quality issues | Medium | Medium | Show data freshness timestamps; fallback labels; _is_real flag in data pipeline |
| LLM hallucination in PARA-DEBATE | Low | Medium | All claims grounded in injected structured data; HEAD ANALYST cross-checks agents |
| Section | Key Takeaway |
| --- | --- |
| Executive Summary | Institutional quant + AI debate at retail price. 100% live data. |
| Competitive Landscape | Outperforms every sub-$100/mo tool on explainability, depth, and India coverage. |
| USPs | 6 defensible differentiators: PARA-DEBATE, self-aware NL query, 5-factor model, live data, NSE, explainability. |
| Drawbacks | 7 honest limitations — all with clear Phase 4/5 fixes. No existential risks. |
| Why Use It | Serves 4 personas: retail investor, RIA, quant researcher, Indian investor. |
| Monetisation | 5 tiers + 5 revenue streams. $84K MRR projected at Month 24. |
| GTM | Community-led → paid conversion → enterprise/API. India-first distribution edge. |
| Technology Moat | 5 compounding moats. Deepest: user trust and India NSE pipeline. |
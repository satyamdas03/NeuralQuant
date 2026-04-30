# PARA-DEBATE + Ask AI Quality Improvement — Design Spec

**Date:** 2026-04-30
**Status:** Approved
**Scope:** Phase 1 — data accuracy, agent enrichment, Ask AI context quality

---

## Problem Statement

PARA-DEBATE has 5 critical data gaps making agents produce unreliable verdicts:
1. TECHNICAL agent nearly non-functional (5 sparse fields, crash_protection never set)
2. SENTIMENT agent has zero real data (insider_cluster_score hardcoded 0.5, news_sentiment always N/A, social_sentiment never provided)
3. FUNDAMENTAL agent missing ROE, revenue_growth, debt_equity, FCF yield from context (available in score_cache but not wired)
4. ADVERSARIAL agent only sees bull_thesis concatenation, not individual specialist outputs — cannot find weaknesses in arguments it never sees
5. India market has no macro context (no Nifty VIX, RBI rate, INR/USD)

Ask AI has 3 issues:
1. News is headlines only (no article body for context)
2. Comparison uses screener rank adjacency, not sector-based peer comparison
3. No persistent conversation memory (4 turns / 1500 chars, in-memory only)

Architectural bugs:
- HEAD ANALYST weighting sums to 125% (should be 100%)
- HEAD ANALYST has key name mismatches (return_on_equity vs roe, gross_margin vs gross_profit_margin)

---

## Approach: Pipeline-by-Pipeline (Approach A)

Fix each data pipeline end-to-end, one at a time. Each pipeline = data source → cache/API → agent context → agent output → HEAD ANALYST. Each step independently testable and deployable.

**Order:**
1. Finnhub integration (shared client, rate limiting, caching)
2. TECHNICAL agent enrichment (RSI, MACD, ATR, SMA, volume from Finnhub)
3. SENTIMENT agent enrichment (insider + news sentiment from Finnhub)
4. FUNDAMENTAL agent enrichment (wire existing score_cache columns)
5. ADVERSARIAL context fix (pass all specialist outputs)
6. HEAD ANALYST weighting fix (normalize to 100%, fix key mapping)
7. India macro context (Nifty VIX, RBI rate, INR/USD)
8. Ask AI: news enrichment (Finnhub full summaries)
9. Ask AI: sector-based comparison
10. Ask AI: persistent conversation memory (Supabase)

---

## Step 1: Finnhub Integration

### New Module: `nq_api/data/finnhub.py`

```python
class FinnhubClient:
    """Finnhub API client with rate limiting and caching."""
    
    BASE_URL = "https://finnhub.io/api/v1"
    
    def __init__(self):
        self.api_key = os.environ.get("FINNHUB_API_KEY")
        self._cache: dict[str, tuple[float, Any]] = {}  # key → (timestamp, data)
        self._cache_ttls = {
            "quote": 300,      # 5 min
            "indicator": 900,  # 15 min
            "news": 1800,      # 30 min
            "insider": 3600,   # 1 hour
            "candle": 900,     # 15 min
        }
        self._rate_limiter = TokenBucketRateLimiter(rate=1.0, burst=60)
    
    async def get_quote(self, ticker: str) -> dict | None
    async def get_indicators(self, ticker: str) -> dict | None  # RSI, MACD, ATR, SMA
    async def get_candles(self, ticker: str, resolution: str = "D", days: int = 200) -> list[dict] | None
    async def get_news(self, ticker: str, days: int = 7) -> list[dict] | None
    async def get_insider_sentiment(self, ticker: str) -> dict | None
    async def get_news_sentiment(self, ticker: str) -> dict | None  # Finnhub news sentiment endpoint
    
    # Internal
    async def _request(self, endpoint: str, params: dict) -> dict | None
    def _cache_get(self, key: str) -> Any | None
    def _cache_set(self, key: str, data: Any, ttl_category: str)
```

### Rate Limiting

- Token bucket: 1 call/sec steady state, burst to 60/min
- Free tier: 60 calls/min, US + India supported
- Finnhub API key in `.env` as `FINNHUB_API_KEY`
- If rate limited, fall back to score_cache data (graceful degradation)

### Caching Strategy

- In-process dict cache (no Redis dependency)
- TTLs: quote=5min, indicator=15min, candle=15min, news=30min, insider=1h
- Nightly GHA pre-warms score_cache so most requests hit cache first
- Finnhub only called for live queries when cache miss or expired
- Cache key format: `{category}:{ticker}` (e.g., `indicator:AAPL`)

### India Ticker Support

- NSE tickers: `RELIANCE.NS`, `TCS.NS`, `INFY.NS`
- BSE tickers: `RELIANCE.BSE` (fallback)
- Nifty 50 index: `^NSEI`
- India VIX: `^VNIFTY`
- INR/USD forex: `INRUSD`

---

## Step 2: TECHNICAL Agent Enrichment

### Current State (broken)

```python
# apps/api/src/nq_api/agents/technical.py
context = {
    "momentum_raw": row.get("momentum_raw"),          # from score_cache
    "momentum_percentile": row.get("momentum_percentile"),
    "spx_vs_200ma": spx_data,                          # SPX only, no India
    "regime": regime_label,                             # from signal engine
    "crash_protection": None,                          # NEVER SET
}
```

### After

```python
# Finnhub indicators wired in
context = {
    # Existing (score_cache fallback)
    "momentum_raw": row.get("momentum_raw"),
    "momentum_percentile": row.get("momentum_percentile"),
    "regime": regime_label,
    
    # New from Finnhub (with score_cache fallback)
    "rsi_14": indicators.get("rsi_14") or row.get("rsi_14"),
    "macd_line": indicators.get("macd_line"),
    "macd_signal": indicators.get("macd_signal"),
    "macd_histogram": indicators.get("macd_hist"),
    "atr_14": indicators.get("atr_14"),
    "sma_50": indicators.get("sma_50"),
    "sma_200": indicators.get("sma_200"),
    "price_vs_sma50": current_price / indicators.get("sma_50") if indicators.get("sma_50") else None,
    "price_vs_sma200": current_price / indicators.get("sma_200") if indicators.get("sma_200") else None,
    "volume_20d_avg": indicators.get("volume_20d_avg"),
    "volume_today": indicators.get("volume_today"),
    "volume_ratio": indicators.get("volume_today") / indicators.get("volume_20d_avg") if indicators.get("volume_20d_avg") else None,
    
    # Market-specific
    "index_vs_200ma": spx_data if market == "US" else nifty_data,  # India support
    "crash_protection": _compute_crash_protection(indicators),  # ACTUALLY COMPUTED
}
```

### crash_protection Computation

```python
def _compute_crash_protection(indicators: dict) -> str:
    """Compute crash protection signal from technical indicators."""
    signals = []
    rsi = indicators.get("rsi_14")
    macd_hist = indicators.get("macd_hist")
    atr = indicators.get("atr_14")
    price = indicators.get("current_price")
    
    if rsi and rsi > 80:
        signals.append("RSI overbought (>80)")
    if macd_hist is not None and macd_hist < 0:
        signals.append("MACD bearish crossover")
    if atr and price and (atr / price) > 0.04:
        signals.append("High volatility (ATR/Price >4%)")
    
    if not signals:
        return "No crash signals"
    return "CAUTION: " + ", ".join(signals)
```

### Fallback Chain

1. Finnhub live indicators (if available, <15min old)
2. score_cache columns (nightly computed)
3. Hardcoded safe defaults ("insufficient data")

---

## Step 3: SENTIMENT Agent Enrichment

### Current State (broken)

```python
# apps/api/src/nq_api/agents/sentiment.py
context = {
    "insider_cluster_score": 0.5,      # HARDCODED
    "news_sentiment": "N/A",            # ALWAYS N/A
    "social_sentiment": None,           # NEVER PROVIDED
}
```

### After

```python
context = {
    # From Finnhub insider
    "insider_cluster_score": insider_data.get("cluster_score", 0.5),
    "insider_net_buy_ratio": insider_data.get("net_buy_ratio"),
    "insider_transactions": insider_data.get("recent_transactions", []),  # last 5
    "insider_summary": insider_data.get("summary"),  # "3 officers bought $2.1M in last 30 days"
    
    # From Finnhub news sentiment
    "news_sentiment": news_data.get("sentiment_label", "neutral"),  # bullish/bearish/neutral
    "news_sentiment_score": news_data.get("sentiment_score", 0.0),   # -1 to 1
    "news_buzz": news_data.get("buzz", 0.0),                         # 0 to 2
    "news_articles": news_data.get("articles", [])[:5],             # top 5 articles
    
    # Social — Finnhub doesn't provide this, mark as unavailable
    "social_sentiment": "data_unavailable",
}
```

### insider_cluster_score Computation

```python
def _compute_insider_score(transactions: list[dict]) -> float:
    """Score 0-1 based on insider buying vs selling patterns."""
    if not transactions:
        return 0.5  # neutral default
    
    buy_volume = sum(t["amount"] for t in transactions if t["type"] == "buy")
    sell_volume = sum(t["amount"] for t in transactions if t["type"] == "sell")
    total = buy_volume + sell_volume
    
    if total == 0:
        return 0.5
    
    # Heavy buying = high score, heavy selling = low score
    # 0.5 = neutral, scale to 0-1
    ratio = buy_volume / total
    return round(ratio, 2)
```

### News Sentiment

Finnhub provides `/news-sentiment` endpoint returning:
- `buzz` (0-2): articles per day vs historical average
- `sentiment_score` (-1 to 1): weighted sentiment of recent articles
- `sentiment_label`: bullish/bearish/neutral

---

## Step 4: FUNDAMENTAL Agent Enrichment

### Wiring Existing score_cache Columns

No new API needed. score_cache already has these columns (from migration 005) that aren't being passed to the FUNDAMENTAL agent:

```python
# Add to FUNDAMENTAL agent context builder
new_fields = {
    "revenue_growth_yoy": row.get("revenue_growth_yoy"),
    "debt_equity": row.get("debt_equity"),
    "piotroski": row.get("piotroski"),
    "gross_profit_margin": row.get("gross_profit_margin"),
    "pb_ratio": row.get("pb_ratio"),
    "pe_ttm": row.get("pe_ttm"),
    "market_cap": row.get("market_cap"),
    "roe": row.get("roe"),           # add to score_cache if missing
    "fcf_yield": row.get("fcf_yield"), # add to score_cache if missing
}
```

### FCF Yield and ROE

If not in score_cache, compute from yfinance data during nightly_score.py:
- `ROE = net_income / total_stockholder_equity`
- `FCF_yield = free_cash_flow / market_cap`

Add `roe` and `fcf_yield` to score_cache schema (migration 006) and nightly_score.py computation.

---

## Step 5: ADVERSARIAL Context Fix

### Current (broken)

```python
# orchestrator.py builds bull_thesis by concatenating BULL stances
bull_thesis = "\n".join([f"{agent}: {output['stance']}" for agent, output in outputs.items() if output['stance'] != 'BEAR'])
adversarial_context = {"bull_thesis": bull_thesis}
```

### After

```python
# Pass ALL specialist outputs to ADVERSARIAL
specialist_outputs = {}
for agent_name, output in outputs.items():
    if agent_name != "adversarial":
        specialist_outputs[agent_name] = {
            "stance": output["stance"],
            "confidence": output.get("confidence"),
            "key_points": output.get("key_points", []),
            "data": output.get("data", {}),
        }

bull_thesis = "\n".join([...])  # keep for backward compat
bear_thesis = "\n".join([...])  # NEW: aggregated bear stances

adversarial_context = {
    "specialist_outputs": specialist_outputs,
    "bull_thesis": bull_thesis,
    "bear_thesis": bear_thesis,
}
```

ADVERSARIAL agent prompt updated to:
- Review each specialist's data and arguments individually
- Find contradictions between specialists
- Identify overconfidence (high confidence with weak data)
- Challenge assumptions that multiple specialists share
- Generate specific counter-arguments with data references

---

## Step 6: HEAD ANALYST Weighting Fix

### Current Bug

```python
weights = {
    "macro": 0.15,         # 15%
    "fundamental": 0.25,   # 25%
    "technical": 0.20,     # 20%
    "sentiment": 0.15,     # 15%
    "geopolitical": 0.15, # 15%
    "adversarial": 0.25,   # 25%
    "regime": 0.10,        # 10%
}
# Total = 125% — WRONG
```

### After (normalized to 100%)

```python
weights = {
    "macro": 0.12,         # 12%
    "fundamental": 0.20,   # 20%
    "technical": 0.16,     # 16%
    "sentiment": 0.12,     # 12%
    "geopolitical": 0.12, # 12%
    "adversarial": 0.20,   # 20%
    "regime": 0.08,        # 8%
}
# Total = 100% ✓
```

### Key Mapping Fix

```python
def _safe_get(data: dict, *keys, default=None):
    """Get value from dict trying multiple key names."""
    for key in keys:
        if key in data:
            return data[key]
    return default

# Use everywhere in head_analyst.py
roe = _safe_get(data, "return_on_equity", "roe")
gross_margin = _safe_get(data, "gross_margin", "gross_profit_margin")
```

Add logging when expected keys are missing to catch future mismatches.

---

## Step 7: India Macro Context

### New Data Sources

```python
# In macro.py, add India-specific data
INDIA_INDICATORS = {
    "nifty_50": "^NSEI",           # Nifty 50 index
    "nifty_200ma": computed from candles,
    "india_vix": "^VNIFTY",         # India VIX
    "rbi_repo_rate": 6.50,          # Hardcoded, update monthly
    "inr_usd": "INRUSD",            # Forex pair
    "india_10y_yield": "~7.10",     # Hardcoded, update monthly
}
```

### Macro Agent Logic

```python
if market == "IN":
    indicators = await _fetch_india_indicators()
    # Use Nifty vs 200MA instead of SPX vs 200MA
    # Use RBI rate stance instead of Fed
    # Use INR/USD strength instead of DXY
    # Use India VIX instead of US VIX
else:
    indicators = await _fetch_us_indicators()  # existing logic
```

### Hardcoded vs Live

- RBI repo rate: hardcoded (changes rarely, ~quarterly). Add to `.env` as `INDIA_RBI_RATE=6.50`
- India 10Y yield: hardcoded. `INDIA_10Y_YIELD=7.10`
- Nifty level, India VIX, INR/USD: live from Finnhub

---

## Step 8: Ask AI News Enrichment

### Current

```python
# _gather_news() returns list of {title, source}
# LLM gets only headlines
```

### After

```python
async def _gather_news(ticker: str, market: str) -> list[dict]:
    """Fetch news with full summaries from Finnhub."""
    finnhub = get_finnhub_client()
    articles = await finnhub.get_news(ticker, days=7)
    
    # Each article now includes:
    # - title
    # - summary (2-3 sentences from Finnhub)
    # - source
    # - url
    # - sentiment_score (from Finnhub news-sentiment)
    
    # If Finnhub summary empty, try Alpaca news as fallback
    for article in articles:
        if not article.get("summary"):
            article["summary"] = await _alpaca_news_fallback(ticker)
    
    return articles[:8]  # Top 8 articles
```

### LLM Context Change

```python
# Before: "Recent news: AAPL launches new iPhone | AAPL stock rises"
# After:  "Recent news:
#   1. AAPL launches new iPhone — Apple unveiled its latest iPhone lineup featuring AI capabilities..."
#   2. AAPL stock rises after strong Q3 earnings..."
```

---

## Step 9: Sector-Based Comparison

### Current

```python
# Comparison shows adjacent screener ranks
# "AAPL ranks #3, MSFT ranks #4, GOOG ranks #5"
```

### After

```python
async def _sector_comparison(ticker: str, market: str) -> dict:
    """Compare against sector median and top sector peer."""
    stock = read_one(ticker, market)
    sector = stock.get("sector", "Unknown")
    
    # Get sector peers from score_cache
    peers = _get_sector_peers(sector, market, limit=20)
    
    # Compute sector medians
    medians = _compute_sector_medians(peers)
    
    # Find top peer in sector (highest composite_score excluding this ticker)
    top_peer = max(p for p in peers if p["ticker"] != ticker, key=lambda p: p["composite_score"])
    
    return {
        "sector": sector,
        "sector_median_pe": medians["pe_ttm"],
        "sector_median_piotroski": medians["piotroski"],
        "sector_median_momentum": medians["momentum_percentile"],
        "stock_pe_vs_sector": stock["pe_ttm"] / medians["pe_ttm"] - 1,  # premium/discount %
        "stock_piotroski_vs_sector": stock["piotroski"] - medians["piotroski"],
        "top_sector_peer": {
            "ticker": top_peer["ticker"],
            "composite_score": top_peer["composite_score"],
            "pe_ttm": top_peer["pe_ttm"],
        }
    }
```

Sector medians cached in-process, refreshed every 15 minutes.

---

## Step 10: Persistent Conversation Memory

### Supabase Schema

```sql
-- Migration 006
CREATE TABLE IF NOT EXISTS public.conversations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    created_at TIMESTAMPTZ DEFAULT now(),
    user_hash TEXT NOT NULL,
    market TEXT DEFAULT 'US'
);

CREATE TABLE IF NOT EXISTS public.conversation_messages (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    conversation_id UUID REFERENCES public.conversations(id) ON DELETE CASCADE,
    role TEXT NOT NULL CHECK (role IN ('user', 'assistant')),
    content TEXT NOT NULL,
    structured JSONB,  -- StructuredQueryResponse JSON for assistant messages
    created_at TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX idx_conversation_messages_conv ON public.conversation_messages(conversation_id, created_at);
CREATE INDEX idx_conversations_user ON public.conversations(user_hash);
```

### Backend Flow

```python
# In query.py /v2/stream endpoint
conversation_id = request.conversation_id  # from frontend

# Load history
history = await load_conversation_history(conversation_id, limit=10)

# Build context from history (max 4000 chars)
context_messages = _build_context_from_history(history)

# After generating response, save to DB
await save_message(conversation_id, "user", query_text)
await save_message(conversation_id, "assistant", response_text, structured=response_json)
```

### Frontend Flow

```typescript
// Generate conversation_id on first visit, store in localStorage
// Send with each query: { query, market, conversation_id }
// On page load, fetch last 5 conversations for sidebar
// Display conversation history in sidebar/dropdown
```

### Context Injection

- Last 10 messages (vs current 4)
- Max 4000 chars (vs current 1500)
- Structured responses summarized: verdict + confidence + key metrics only
- No PII — user_hash is SHA256 of request IP, or random UUID from localStorage if no IP available

---

## Testing Strategy

Each step ships independently with tests:

1. **FinnhubClient**: Unit tests with mocked API responses. Rate limiter tests. Cache TTL tests.
2. **TECHNICAL enrichment**: Integration test — verify RSI, MACD, ATR, SMA fields populated. Fallback test — verify score_cache data used when Finnhub fails.
3. **SENTIMENT enrichment**: Integration test — verify insider_score computed from transactions. News sentiment test.
4. **FUNDAMENTAL enrichment**: Integration test — verify all score_cache columns wired. Verify missing columns gracefully handled.
5. **ADVERSARIAL fix**: Integration test — verify all specialist outputs in context. Verify bull + bear thesis both present.
6. **HEAD ANALYST fix**: Unit test — weights sum to 1.0. Key mapping test — both `roe` and `return_on_equity` resolve.
7. **India macro**: Integration test with IN market tickers. Verify Nifty data flows.
8. **News enrichment**: Integration test — summaries present. Fallback to Alpaca test.
9. **Sector comparison**: Unit test — sector median computation. Integration test — comparison vs sector.
10. **Conversation memory**: Integration test — save/load history. Verify 10-message context.

### Deployment Safety

- Each step deployed and tested on Render before next step begins
- Feature flags in `.env` for each new data source (`FINNHUB_ENABLED`, `CONVERSATION_MEMORY_ENABLED`)
- Graceful degradation: if Finnhub down, fall back to score_cache
- No breaking changes to existing API contracts

---

## Files Modified (New)

| File | Purpose |
|------|---------|
| `apps/api/src/nq_api/data/finnhub.py` | New Finnhub client with rate limiting + caching |
| `supabase/migrations/006_conversations.sql` | Conversations + messages tables |

## Files Modified (Existing)

| File | Changes |
|------|---------|
| `apps/api/src/nq_api/agents/technical.py` | Wire Finnhub indicators, compute crash_protection, add India index support |
| `apps/api/src/nq_api/agents/sentiment.py` | Wire Finnhub insider + news sentiment, remove hardcoded 0.5 |
| `apps/api/src/nq_api/agents/fundamental.py` | Wire existing score_cache columns (revenue_growth_yoy, debt_equity, etc.) |
| `apps/api/src/nq_api/agents/adversarial.py` | Accept specialist_outputs dict, bull + bear thesis |
| `apps/api/src/nq_api/agents/head_analyst.py` | Fix weights to 100%, fix key mapping, add logging |
| `apps/api/src/nq_api/agents/macro.py` | Add India macro indicators (Nifty, India VIX, RBI rate, INR/USD) |
| `apps/api/src/nq_api/orchestrator.py` | Pass all specialist outputs to ADVERSARIAL |
| `apps/api/src/nq_api/routes/query.py` | News enrichment (full summaries), conversation memory, sector comparison |
| `apps/api/src/nq_api/cache/score_cache.py` | Add sector median computation, roe/fcf_yield columns |
| `scripts/nightly_score.py` | Add roe and fcf_yield computation |
| `apps/web/src/components/NLQueryBox.tsx` | Send conversation_id, display history |
| `apps/web/src/lib/api.ts` | Pass conversation_id in query requests |

---

## Dependencies

- **Finnhub API key**: Required. Free tier (60 calls/min). Sign up at finnhub.io.
- **Supabase migration 006**: For conversations table.
- **No new infrastructure**: Uses existing Render backend, Supabase DB, Vercel frontend.

## Out of Scope (Phase 2)

- Social sentiment (Twitter/Reddit scraping)
- Real-time WebSocket updates
- Options flow data for TECHNICAL agent
- FII/DII flow data for India macro
- Voice input for Ask AI
- Multi-model consensus for HEAD ANALYST
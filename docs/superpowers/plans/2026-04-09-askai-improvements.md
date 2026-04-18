# AskAI Improvements Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Overhaul the NeuralQuant AskAI feature to fix 5 user-reported issues: out-of-universe stocks returning deflective answers, homepage query box having no memory, poor loading UX during cold start, India-focused queries polluted with irrelevant US macro, and AI responses being indirect/non-actionable.

**Architecture:** Three layers of change — (1) backend query engine gets dynamic stock fetching + India macro + system prompt rewrite, (2) homepage HomeQueryBox becomes a full chat component with history, (3) both chat surfaces get improved loading/cold-start animations.

**Tech Stack:** FastAPI + Anthropic Claude (backend), Next.js 16 + React (frontend), yfinance for dynamic stock data, FRED for macro.

---

## File Map

| File | What Changes |
|---|---|
| `apps/api/src/nq_api/routes/query.py` | Dynamic stock fetch, India macro, system prompt overhaul, market-aware macro injection |
| `apps/web/src/app/page.tsx` | Replace `HomeQueryBox` with full chat UI (history, bouncing dots, cold-start banner) |

---

## Task 1: Fix Dynamic Stock Fetching for Out-of-Universe Stocks

**Root cause:** `_detect_tickers_in_question()` only checks `US_DEFAULT | IN_DEFAULT`. TRENT, ZYDUSLIFE, DIXON, etc. are not in the universe → `mentioned_tickers` is empty → AI says "no NeuralQuant score injected" and deflects.

**Fix:** When an India-market query mentions a word that looks like an NSE ticker (2–10 uppercase letters) and it's not in the universe, attempt a live yfinance fetch for `WORD.NS` and inject price + fundamentals directly.

**Files:**
- Modify: `apps/api/src/nq_api/routes/query.py` (functions `_detect_tickers_in_question`, `_enrich_with_platform_data`)

- [ ] **Step 1: Add NSE dynamic lookup helper in query.py**

In `apps/api/src/nq_api/routes/query.py`, add this function after `_detect_tickers_in_question`:

```python
# NSE common stock name → ticker mappings (handles natural language names)
_NSE_NAME_MAP = {
    "TRENT": "TRENT.NS",
    "TITAN": "TITAN.NS",
    "ZOMATO": "ZOMATO.NS",
    "NYKAA": "NYKAA.NS",
    "PAYTM": "PAYTM.NS",
    "DMART": "DMART.NS",
    "ZYDUS": "ZYDUSLIFE.NS",
    "DIXON": "DIXON.NS",
    "IRCTC": "IRCTC.NS",
    "PIDILITE": "PIDILITIND.NS",
    "EICHER": "EICHERMOT.NS",
    "BAJAJ": "BAJFINANCE.NS",
    "HDFC": "HDFCBANK.NS",
    "ICICI": "ICICIBANK.NS",
    "KOTAK": "KOTAKBANK.NS",
    "RELIANCE": "RELIANCE.NS",
    "INFOSYS": "INFY.NS",
    "WIPRO": "WIPRO.NS",
    "HCLTECH": "HCLTECH.NS",
    "SUNPHARMA": "SUNPHARMA.NS",
    "DRREDDY": "DRREDDY.NS",
    "CIPLA": "CIPLA.NS",
    "MARUTI": "MARUTI.NS",
    "TATAMOTORS": "TATAMOTORS.NS",
    "TATASTEEL": "TATASTEEL.NS",
    "ADANI": "ADANIENT.NS",
    "HINDALCO": "HINDALCO.NS",
    "ONGC": "ONGC.NS",
    "NTPC": "NTPC.NS",
    "POWERGRID": "POWERGRID.NS",
    "COALINDIA": "COALINDIA.NS",
    "SBIN": "SBIN.NS",
    "AXISBANK": "AXISBANK.NS",
    "INDUSINDBANK": "INDUSINDBK.NS",
    "BAJAJFINSV": "BAJAJFINSV.NS",
    "NESTLEIND": "NESTLEIND.NS",
    "ASIANPAINTS": "ASIANPAINT.NS",
    "ULTRACEMCO": "ULTRACEMCO.NS",
    "SHREECEM": "SHREECEM.NS",
    "GRASIM": "GRASIM.NS",
    "TECHM": "TECHM.NS",
    "LTI": "LTIM.NS",
    "MPHASIS": "MPHASIS.NS",
    "PERSISTENT": "PERSISTENT.NS",
    "COFORGE": "COFORGE.NS",
    "HAPPIEST": "HAPPSTMNDS.NS",
    "TATAPOWER": "TATAPOWER.NS",
    "JSWENERGY": "JSWENERGY.NS",
    "POLYCAB": "POLYCAB.NS",
    "APLAPOLLO": "APLAPOLLO.NS",
}


def _fetch_dynamic_nse_stock(word: str) -> dict | None:
    """
    Try to fetch live data for an NSE stock not in our screener universe.
    word: uppercase stock name/ticker from user query.
    Returns a dict with price, fundamentals, or None if not found.
    """
    # Check direct name map first
    nse_sym = _NSE_NAME_MAP.get(word)
    if not nse_sym:
        # Try appending .NS directly
        nse_sym = f"{word}.NS"

    try:
        t = yf.Ticker(nse_sym)
        info = t.info
        price = info.get("currentPrice") or info.get("regularMarketPrice")
        if not price:
            return None  # Stock not found on yfinance

        return {
            "symbol": nse_sym,
            "display": word,
            "price": price,
            "currency": info.get("currency", "INR"),
            "change_pct": info.get("regularMarketChangePercent", 0),
            "week52_high": info.get("fiftyTwoWeekHigh"),
            "week52_low": info.get("fiftyTwoWeekLow"),
            "pe_ttm": info.get("trailingPE"),
            "pb_ratio": info.get("priceToBook"),
            "market_cap": info.get("marketCap"),
            "beta": info.get("beta"),
            "analyst_target": info.get("targetMeanPrice"),
            "analyst_recommendation": info.get("recommendationKey", "").upper(),
            "gross_margin": info.get("grossMargins"),
            "revenue_growth": info.get("revenueGrowth"),
            "sector": info.get("sector", ""),
            "longName": info.get("longName", word),
        }
    except Exception:
        return None
```

- [ ] **Step 2: Update `_detect_tickers_in_question` to catch out-of-universe stocks**

Replace the existing `_detect_tickers_in_question` function:

```python
def _detect_tickers_in_question(question: str, market: str = "US") -> tuple[list[str], list[str]]:
    """
    Returns (in_universe_tickers, out_of_universe_words).
    in_universe_tickers: known tickers found in question.
    out_of_universe_words: words that look like NSE tickers but aren't in universe.
    """
    from nq_api.universe import US_DEFAULT, IN_DEFAULT
    known = set(US_DEFAULT) | set(IN_DEFAULT)
    in_universe = []
    q_upper = question.upper()

    # Check known universe tickers
    for t in known:
        base = t.replace(".NS", "").replace(".BO", "")
        if re.search(r'\b' + re.escape(base) + r'\b', q_upper):
            in_universe.append(t)

    # For India queries, check for words that look like NSE tickers
    out_of_universe = []
    if market == "IN" or any(k in q_upper for k in _INDIA_KEYWORDS):
        for word in q_upper.split():
            clean = re.sub(r"[^A-Z]", "", word)
            if (3 <= len(clean) <= 12
                    and clean not in _STOP_WORDS
                    and clean not in known
                    and clean not in {t.replace(".NS","") for t in known}
                    and clean not in {"SHOULD", "INVEST", "INDIA", "INDIAN", "STOCK", "SHARE",
                                      "MARKET", "NIFTY", "SENSEX", "RUPEE", "LAKH", "CRORE",
                                      "MILLION", "BILLION", "WANT", "GIVE", "TELL", "BEST",
                                      "GOOD", "HIGH", "LARGE", "SMALL", "LONG", "TERM",
                                      "CURRENT", "TODAY", "YEAR", "MONTH", "WEEK"}):
                out_of_universe.append(clean)

    return in_universe[:5], out_of_universe[:3]
```

- [ ] **Step 3: Update `_enrich_with_platform_data` to use new signature and handle out-of-universe stocks**

Replace the full `_enrich_with_platform_data` function:

```python
def _enrich_with_platform_data(question: str, market: str) -> str | None:
    """
    Fetch NeuralQuant's own stock scores + movers when the question needs them.
    Also dynamically fetches data for stocks not in the screener universe.
    Returns a formatted context string, or None if not needed.
    """
    from nq_api.data_builder import build_real_snapshot, fetch_fundamentals_batch
    from nq_api.universe import UNIVERSE_BY_MARKET
    from nq_signals.engine import SignalEngine
    from nq_api.score_builder import row_to_ai_score, rank_scores_in_universe
    from nq_api.deps import get_signal_engine

    q_upper = question.upper()
    parts: list[str] = []

    # Determine which market to use
    target_market = "IN" if any(k in q_upper for k in _INDIA_KEYWORDS) else market

    needs_screener = any(k in q_upper for k in _SCREENER_KEYWORDS)
    in_universe_tickers, out_of_universe_words = _detect_tickers_in_question(question, target_market)
    needs_stock_scores = (
        in_universe_tickers
        or out_of_universe_words
        or any(k in q_upper for k in ["IS A BUY", "IS A SELL", "COMPARE", "VERSUS", "VS ", "OVERVALUED", "SHORT INTEREST"])
    )

    if not needs_screener and not needs_stock_scores:
        return None

    try:
        engine = get_signal_engine()

        if needs_screener or (not in_universe_tickers and not out_of_universe_words and needs_stock_scores):
            universe = UNIVERSE_BY_MARKET.get(target_market, UNIVERSE_BY_MARKET["US"])[:20]
            snapshot = build_real_snapshot(universe, target_market)
            result_df = engine.compute(snapshot)
            result_df = result_df.sort_values("composite_score", ascending=False).reset_index(drop=True)
            ranked = rank_scores_in_universe(result_df)
            top = result_df.head(10)
            lines = [f"NeuralQuant {target_market} Screener — Top 10 stocks right now:"]
            for i, (idx, row) in enumerate(top.iterrows()):
                sc = int(ranked.loc[idx]) if idx in ranked.index else 5
                q = row.get("quality_percentile", 0.5)
                m = row.get("momentum_percentile", 0.5)
                v = row.get("value_percentile", 0.5)
                si = row.get("short_interest_percentile", 0.5)
                lines.append(
                    f"  #{i+1} {row['ticker']}: {sc}/10 | "
                    f"Quality={q:.0%} Momentum={m:.0%} Value={v:.0%} LowSI={si:.0%} | "
                    f"Confidence: {row.get('regime_confidence', 0.5):.0%}"
                )
            parts.append("\n".join(lines))

        if in_universe_tickers:
            base_universe = UNIVERSE_BY_MARKET.get(target_market, UNIVERSE_BY_MARKET["US"])
            universe = list(dict.fromkeys(in_universe_tickers + base_universe))[:25]
            snapshot = build_real_snapshot(universe, target_market)
            result_df = engine.compute(snapshot)
            ranked = rank_scores_in_universe(result_df)
            lines = ["NeuralQuant scores for mentioned stocks:"]
            for t in in_universe_tickers:
                row_match = result_df[result_df["ticker"] == t]
                if not row_match.empty:
                    row = row_match.iloc[0]
                    idx = row_match.index[0]
                    sc = int(ranked.loc[idx]) if idx in ranked.index else 5
                    conf_label = "high" if row.get("regime_confidence", 0.5) > 0.7 else ("medium" if row.get("regime_confidence", 0.5) > 0.4 else "low")
                    lines.append(
                        f"  {t}: {sc}/10 (composite={row['composite_score']:.3f}) | "
                        f"Quality={row.get('quality_percentile', 0.5):.0%} "
                        f"Momentum={row.get('momentum_percentile', 0.5):.0%} "
                        f"Value={row.get('value_percentile', 0.5):.0%} "
                        f"LowVol={row.get('low_vol_percentile', 0.5):.0%} "
                        f"LowSI={row.get('short_interest_percentile', 0.5):.0%} | "
                        f"Confidence: {conf_label} | P/E={row.get('pe_ttm', 'N/A')} "
                        f"P/B={row.get('pb_ratio', 0):.1f} Beta={row.get('beta', 0):.2f}"
                    )
            parts.append("\n".join(lines))

        # Dynamic fetch for out-of-universe NSE stocks (e.g. TRENT, DIXON, ZYDUS)
        if out_of_universe_words:
            dynamic_lines = ["Live data for requested stocks (dynamically fetched from NSE):"]
            found_any = False
            for word in out_of_universe_words:
                data = _fetch_dynamic_nse_stock(word)
                if data:
                    found_any = True
                    pe_str = f"P/E={data['pe_ttm']:.1f}" if data.get("pe_ttm") else "P/E=N/A"
                    pb_str = f"P/B={data['pb_ratio']:.1f}" if data.get("pb_ratio") else "P/B=N/A"
                    beta_str = f"Beta={data['beta']:.2f}" if data.get("beta") else ""
                    target_str = f"Analyst target=₹{data['analyst_target']:.0f} ({data['analyst_recommendation']})" if data.get("analyst_target") else ""
                    chg_str = f"{data['change_pct']:+.2f}%" if data.get("change_pct") else ""
                    mcap = f"MCap=₹{data['market_cap']/1e9:.0f}B" if data.get("market_cap") else ""
                    dynamic_lines.append(
                        f"  {data['longName']} ({data['symbol']}): "
                        f"₹{data['price']:.2f} {chg_str} | "
                        f"52w ₹{data.get('week52_low', 0):.0f}–₹{data.get('week52_high', 0):.0f} | "
                        f"{pe_str} {pb_str} {beta_str} {mcap} | {target_str}"
                    )
                    # NOTE: NeuralQuant score not available for this stock (not in screener universe)
                    # but we have live price + fundamentals — the AI should use this to give a direct answer
            if found_any:
                dynamic_lines.append(
                    "  NOTE: Full NeuralQuant AI score unavailable for above stocks "
                    "(not in screener universe), but live price + fundamentals are injected above. "
                    "Use these numbers to give a direct, data-driven answer."
                )
                parts.append("\n".join(dynamic_lines))

        # Live prices for in-universe mentioned tickers
        if in_universe_tickers:
            try:
                price_lines = ["Live prices:"]
                for t in in_universe_tickers[:3]:
                    try:
                        info = yf.Ticker(t).info
                        price = info.get("currentPrice") or info.get("regularMarketPrice")
                        high52 = info.get("fiftyTwoWeekHigh")
                        low52 = info.get("fiftyTwoWeekLow")
                        target = info.get("targetMeanPrice")
                        chg = info.get("regularMarketChangePercent", 0)
                        if price:
                            price_lines.append(
                                f"  {t}: ${price:.2f} ({chg:+.2f}%) | "
                                f"52w ${low52:.2f}–${high52:.2f}"
                                + (f" | Analyst target ${target:.2f}" if target else "")
                            )
                    except Exception:
                        pass
                if len(price_lines) > 1:
                    parts.append("\n".join(price_lines))
            except Exception:
                pass

    except Exception as exc:
        return f"[Platform data unavailable: {exc}]"

    return "\n\n".join(parts) if parts else None
```

- [ ] **Step 4: Verify API starts and test Trent query**

```bash
curl -s -X POST http://127.0.0.1:8000/query \
  -H "Content-Type: application/json" \
  -d '{"question": "Should I invest in Trent?", "market": "IN"}' | \
  python -c "import sys,json; d=json.load(sys.stdin); print(d['answer'][:500])"
```

Expected: Answer mentions Trent's actual live price (₹XXXX), P/E, 52-week range — NOT Bharti or Maruti.

- [ ] **Step 5: Commit**

```bash
cd /c/Users/point/projects/stockpredictor
git add apps/api/src/nq_api/routes/query.py
git commit -m "feat: dynamic NSE stock fetch for out-of-universe queries (fixes Trent deflection)"
```

---

## Task 2: Add India-Specific Macro Context

**Root cause:** For India queries, the engine injects US macro (VIX, S&P 200-MA, HY spreads, 2s10s) which confuses users asking about Indian stocks. India-focused questions should see Nifty 50, INR/USD, and Indian market context.

**Files:**
- Modify: `apps/api/src/nq_api/routes/query.py` (function `run_nl_query`)

- [ ] **Step 1: Add India macro fetch helper**

Add this function after `_fetch_relevant_news` in `query.py`:

```python
def _fetch_india_macro() -> str | None:
    """Fetch India-specific market context: Nifty 50, INR/USD."""
    try:
        import yfinance as yf
        lines = []

        # Nifty 50
        nifty = yf.Ticker("^NSEI")
        hist = nifty.history(period="5d", auto_adjust=True)
        if len(hist) >= 2:
            nifty_price = float(hist["Close"].iloc[-1])
            nifty_prev = float(hist["Close"].iloc[-2])
            nifty_chg = (nifty_price - nifty_prev) / nifty_prev * 100
            lines.append(f"Nifty 50: {nifty_price:,.0f} ({nifty_chg:+.2f}% today)")

        # BSE Sensex
        sensex = yf.Ticker("^BSESN")
        hist2 = sensex.history(period="5d", auto_adjust=True)
        if len(hist2) >= 2:
            sensex_price = float(hist2["Close"].iloc[-1])
            sensex_prev = float(hist2["Close"].iloc[-2])
            sensex_chg = (sensex_price - sensex_prev) / sensex_prev * 100
            lines.append(f"BSE Sensex: {sensex_price:,.0f} ({sensex_chg:+.2f}% today)")

        # INR/USD exchange rate
        inr = yf.Ticker("USDINR=X")
        inr_hist = inr.history(period="5d", auto_adjust=True)
        if not inr_hist.empty:
            inr_rate = float(inr_hist["Close"].iloc[-1])
            lines.append(f"USD/INR: {inr_rate:.2f}")

        # India VIX
        india_vix = yf.Ticker("^INDIAVIX")
        vix_hist = india_vix.history(period="5d", auto_adjust=True)
        if not vix_hist.empty:
            ivix = float(vix_hist["Close"].iloc[-1])
            lines.append(f"India VIX: {ivix:.1f} ({'elevated' if ivix > 20 else 'normal'})")

        return "Indian Market Context: " + " | ".join(lines) if lines else None
    except Exception:
        return None
```

- [ ] **Step 2: Update `run_nl_query` to use market-aware macro injection**

In `run_nl_query`, replace the macro context building block:

```python
    # ── Market-aware macro context ──────────────────────────────────────────
    q_upper = req.question.upper()
    is_india_query = any(k in q_upper for k in _INDIA_KEYWORDS) or req.market == "IN"

    if is_india_query:
        # India-focused: inject Indian market context, suppress heavy US macro
        india_ctx = _fetch_india_macro()
        macro_ctx = india_ctx  # only Indian macro for India queries
        # Also inject basic US risk sentiment (VIX only, briefly)
        try:
            macro = fetch_real_macro()
            macro_ctx = (india_ctx or "") + (
                f" | Global risk: US VIX={macro.vix:.1f}"
                f", Fed funds={macro.fed_funds_rate:.2f}%"
                f", CPI={macro.cpi_yoy:.1f}%"
            )
        except Exception:
            pass
    else:
        # US/Global query: full macro context
        try:
            macro = fetch_real_macro()
            macro_ctx = (
                f"Live market conditions (as of {today}): "
                f"VIX={macro.vix:.1f}, "
                f"SPX vs 200-MA={macro.spx_vs_200ma*100:+.1f}%, "
                f"SPX 1-month return={macro.spx_return_1m*100:+.1f}%, "
                f"HY spread={macro.hy_spread_oas:.0f}bps, "
                f"10Y yield={macro.yield_10y:.2f}%, "
                f"2Y yield={macro.yield_2y:.2f}%, "
                f"2s10s spread={macro.yield_spread_2y10y*100:+.0f}bps, "
                f"ISM PMI={macro.ism_pmi:.1f}, "
                f"CPI YoY={macro.cpi_yoy:.1f}%, "
                f"Fed funds rate={macro.fed_funds_rate:.2f}%"
                + (" [FRED-sourced]" if macro.fred_sourced else " [partial]")
            )
        except Exception:
            macro_ctx = None
```

- [ ] **Step 3: Test India query**

```bash
curl -s -X POST http://127.0.0.1:8000/query \
  -H "Content-Type: application/json" \
  -d '{"question": "I want to invest 10 lakhs in Indian stocks, name specific shares", "market": "IN"}' | \
  python -c "import sys,json; d=json.load(sys.stdin); print(d['answer'][:600])"
```

Expected: Response mentions Nifty level, specific INR prices, no mention of S&P 200-MA or HY spreads as primary context.

- [ ] **Step 4: Commit**

```bash
git add apps/api/src/nq_api/routes/query.py
git commit -m "feat: India-specific macro context (Nifty, Sensex, INR/USD) for India queries"
```

---

## Task 3: System Prompt Overhaul — Actionable, Direct, Data-Heavy

**Root cause:** Current system prompt allows the AI to: (a) say "I don't have data" when data IS injected, (b) give hedge-everything indirect answers, (c) pepper India answers with US market statistics, (d) miss range projections.

**Files:**
- Modify: `apps/api/src/nq_api/routes/query.py` (constant `_SYSTEM`)

- [ ] **Step 1: Replace `_SYSTEM` prompt**

Replace the existing `_SYSTEM` constant with:

```python
_SYSTEM = """You are NeuralQuant — an institutional-grade AI stock intelligence engine. You have access to live data injected in every user message. Your job: give direct, data-driven, actionable answers. No hedging. No disclaimers. No detours.

## DATA YOU HAVE ACCESS TO
1. Live macro data: FRED (HY spreads, CPI, Fed funds, yield curve) + yfinance (VIX, SPX, Nifty, INR/USD)
2. NeuralQuant AI stock scores (1-10) for 50 US + 50 Indian NSE stocks
3. Live prices, 52-week ranges, analyst targets, P/E, P/B, beta
4. Real-time market headlines

## HARD RULES — NEVER VIOLATE
1. **NEVER say "I don't have data/scores for this stock" when price or fundamentals are injected above.** If live price is injected, USE IT. Quote exact numbers.
2. **NEVER deflect to a different stock when the user asks about a specific one.** If asked about Trent, answer about Trent — not Bharti, not Maruti.
3. **NEVER mention US indices (S&P 500, VIX, HY spreads, 2s10s) as primary context for India-specific questions.** For India queries: lead with Nifty/Sensex/INR, mention global risk only as a footnote.
4. **NEVER give indirect or vague investment advice.** If asked "which stocks to buy for ₹10L", name SPECIFIC stocks with specific rupee allocations.
5. **NEVER start with "Based on available data, I cannot..."** — you always have data. Use it.

## RESPONSE STYLE
- **Data-heavy, narrative-light.** Lead with numbers. Support with a brief directional thesis.
- **One clear direction.** Pick bull or bear. Don't say "on one hand... but on the other." Give a verdict and defend it.
- **Quantify everything.** Not "elevated risk" — say "15% downside risk if X scenario".
- **For price predictions:** Always give 3 scenarios:
  - Bear case: X% (trigger: [specific event])
  - Base case: X% (most likely path)
  - Bull case: X% (trigger: [specific event])
- **For portfolio allocation questions (e.g. "invest ₹10L in Indian stocks"):**
  - Name 4-6 specific stocks
  - Give exact rupee allocation per stock
  - Give entry price range
  - Give 3-month target
  - Give stop-loss level
- **For specific stock queries:** Lead with: score/10, current price, 1-line verdict (BUY / HOLD / AVOID), then justify with data.
- **Avoid:** Internal scoring jargon (don't say "Quality score 41%") — translate to plain English ("Strong balance sheet, improving margins").
- **For Indian stocks:** Use ₹ symbol, crore/lakh notation where appropriate.

## RESPONSE FORMAT
ANSWER: [Direct answer — numbers first, verdict clear, one direction]
DATA_SOURCES: [comma-separated: NeuralQuant Screener / FRED Macro / India Macro / Live News / yfinance]
FOLLOW_UP:
- [Specific follow-up question]
- [Specific follow-up question]
- [Specific follow-up question]"""
```

- [ ] **Step 2: Test TCS query for range projection**

```bash
curl -s -X POST http://127.0.0.1:8000/query \
  -H "Content-Type: application/json" \
  -d '{"question": "Give me a 1 month price projection for TCS", "market": "IN"}' | \
  python -c "import sys,json; d=json.load(sys.stdin); print(d['answer'][:800])"
```

Expected: Contains bear/base/bull case percentages, mentions actual TCS price, no US HY spread as primary metric.

- [ ] **Step 3: Test ₹10L India portfolio query**

```bash
curl -s -X POST http://127.0.0.1:8000/query \
  -H "Content-Type: application/json" \
  -d '{"question": "I want to invest 10 lakhs in Indian stocks. Name specific shares and justify", "market": "IN"}' | \
  python -c "import sys,json; d=json.load(sys.stdin); print(d['answer'][:1000])"
```

Expected: Lists 4-6 specific NSE stock names, rupee allocations, no mention of S&P as primary context.

- [ ] **Step 4: Commit**

```bash
git add apps/api/src/nq_api/routes/query.py
git commit -m "feat: overhaul system prompt — direct, data-heavy, bear/base/bull projections, India-aware"
```

---

## Task 4: HomeQueryBox Full Chat Upgrade (Context Window + Better UI)

**Root cause:** `HomeQueryBox` in `page.tsx` is a stateless single-question input — no conversation history, no multi-turn chat, no proper loading animation. It's the first thing users see but the weakest AskAI surface.

**Fix:** Replace the minimal `HomeQueryBox` with a full chat component that mirrors `NLQueryBox` behaviour: conversation history, bouncing-dots loading, multi-turn context, follow-up chips.

**Files:**
- Modify: `apps/web/src/app/page.tsx`

- [ ] **Step 1: Replace `HomeQueryBox` in `page.tsx`**

Find the `HomeQueryBox` function (lines ~157–209) and replace it entirely:

```tsx
// ─── Inline NL Query Box (full chat, with history) ────────────────────────────

interface HomeChatMessage {
  id: string;
  role: "user" | "assistant";
  content: string;
  sources?: string[];
  followUps?: string[];
  loading?: boolean;
}

function HomeQueryBox() {
  const [input, setInput] = useState("");
  const [messages, setMessages] = useState<HomeChatMessage[]>([]);
  const [loading, setLoading] = useState(false);
  const [slowLoad, setSlowLoad] = useState(false);
  const bottomRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);
  const slowTimer = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  const ask = async (question: string) => {
    const q = question.trim();
    if (!q || loading) return;
    setInput("");
    setSlowLoad(false);

    const userMsg: HomeChatMessage = { id: Date.now().toString(), role: "user", content: q };
    const placeholderId = (Date.now() + 1).toString();
    const placeholder: HomeChatMessage = { id: placeholderId, role: "assistant", content: "", loading: true };

    setMessages(prev => [...prev, userMsg, placeholder]);
    setLoading(true);

    // After 8s still loading → show cold-start warning
    slowTimer.current = setTimeout(() => setSlowLoad(true), 8000);

    // Build conversation history from prior completed turns
    const history = messages
      .filter(m => !m.loading)
      .map(m => ({ role: m.role as "user" | "assistant", content: m.content }));

    try {
      const res = await api.runQuery({ question: q, history });
      setMessages(prev =>
        prev.map(m =>
          m.id === placeholderId
            ? { ...m, content: res.answer, sources: res.data_sources, followUps: res.follow_up_questions, loading: false }
            : m
        )
      );
    } catch {
      setMessages(prev =>
        prev.map(m =>
          m.id === placeholderId
            ? { ...m, content: "Failed — backend may be starting up. Please try again in 30 seconds.", loading: false }
            : m
        )
      );
    } finally {
      setLoading(false);
      setSlowLoad(false);
      if (slowTimer.current) clearTimeout(slowTimer.current);
      setTimeout(() => inputRef.current?.focus(), 50);
    }
  };

  const clear = () => { setMessages([]); setInput(""); };

  return (
    <div className="bg-gray-900 border border-gray-800 rounded-xl overflow-hidden">
      <div className="px-5 py-3 border-b border-gray-800 flex items-center justify-between">
        <h2 className="font-semibold text-sm text-gray-300 uppercase tracking-wide">
          Ask anything about markets
        </h2>
        {messages.length > 0 && (
          <button onClick={clear} className="text-xs text-gray-600 hover:text-gray-400 transition-colors">
            Clear
          </button>
        )}
      </div>
      <div className="p-4 space-y-3">
        {/* Cold-start banner */}
        {slowLoad && (
          <div className="flex items-center gap-2 px-3 py-2 bg-amber-500/10 border border-amber-500/20 rounded-lg">
            <span className="w-2 h-2 rounded-full bg-amber-400 animate-pulse flex-shrink-0" />
            <span className="text-xs text-amber-400">
              Backend is warming up after inactivity — this first response takes ~60s. Hang tight.
            </span>
          </div>
        )}

        {/* Chat messages */}
        {messages.length > 0 && (
          <div className="space-y-3 max-h-[50vh] overflow-y-auto pr-1 scroll-smooth">
            {messages.map(msg => (
              <div key={msg.id} className={`flex ${msg.role === "user" ? "justify-end" : "justify-start"}`}>
                {msg.role === "user" ? (
                  <div className="max-w-[80%] bg-violet-600/20 border border-violet-500/20 rounded-2xl rounded-tr-sm px-3 py-2 text-sm text-gray-100">
                    {msg.content}
                  </div>
                ) : (
                  <div className="max-w-[95%] space-y-1.5">
                    <div className="flex items-start gap-2">
                      <div className="w-5 h-5 rounded-full bg-gradient-to-br from-violet-500 to-cyan-500 flex-shrink-0 flex items-center justify-center mt-0.5">
                        <span className="text-[9px] font-bold text-white">N</span>
                      </div>
                      <div className="bg-gray-800/60 border border-gray-700 rounded-2xl rounded-tl-sm px-3 py-2.5 text-sm text-gray-100 leading-relaxed">
                        {msg.loading ? (
                          <div className="flex gap-1.5 items-center py-0.5">
                            {[0, 1, 2].map(i => (
                              <span
                                key={i}
                                className="w-1.5 h-1.5 rounded-full bg-violet-400 animate-bounce"
                                style={{ animationDelay: `${i * 0.15}s` }}
                              />
                            ))}
                          </div>
                        ) : (
                          <p className="whitespace-pre-wrap">{msg.content}</p>
                        )}
                      </div>
                    </div>
                    {!msg.loading && msg.sources && msg.sources.length > 0 && (
                      <div className="ml-7 flex gap-1 flex-wrap">
                        {msg.sources.map(s => (
                          <span key={s} className="text-[10px] px-2 py-0.5 rounded-full bg-violet-500/10 text-violet-400 border border-violet-500/20">
                            {s}
                          </span>
                        ))}
                      </div>
                    )}
                    {!msg.loading && msg.followUps && msg.followUps.length > 0 && (
                      <div className="ml-7 flex flex-wrap gap-1.5">
                        {msg.followUps.map(fq => (
                          <button
                            key={fq}
                            onClick={() => ask(fq)}
                            className="text-xs px-2.5 py-1 bg-gray-800 hover:bg-gray-700 text-gray-400 hover:text-white rounded-full border border-gray-700 transition-colors"
                          >
                            {fq}
                          </button>
                        ))}
                      </div>
                    )}
                  </div>
                )}
              </div>
            ))}
            <div ref={bottomRef} />
          </div>
        )}

        {/* Input bar */}
        <div className="flex gap-2">
          <input
            ref={inputRef}
            value={input}
            onChange={e => setInput(e.target.value)}
            onKeyDown={e => e.key === "Enter" && !e.shiftKey && ask(input)}
            placeholder="e.g. What is the effect of Iran-US tensions on oil stocks?"
            className="flex-1 bg-gray-800 border border-gray-700 rounded-lg px-4 py-2.5 text-sm text-gray-100 placeholder-gray-500 focus:outline-none focus:border-violet-500"
            disabled={loading}
          />
          <button
            onClick={() => ask(input)}
            disabled={loading || !input.trim()}
            className="px-4 py-2.5 bg-violet-600 hover:bg-violet-500 disabled:opacity-40 rounded-lg text-sm font-medium transition-colors"
          >
            {loading ? (
              <span className="w-4 h-4 rounded-full border-2 border-white/30 border-t-white animate-spin block" />
            ) : "→"}
          </button>
        </div>
      </div>
    </div>
  );
}
```

Also add `useRef` to the imports at the top of `page.tsx` if not already present:
```tsx
import { useEffect, useState, useRef } from "react";
```

- [ ] **Step 2: Build frontend to check for errors**

```bash
cd /c/Users/point/projects/stockpredictor/apps/web && npm run build 2>&1 | tail -15
```

Expected: `✓ Generating static pages` — no TypeScript errors.

- [ ] **Step 3: Commit**

```bash
cd /c/Users/point/projects/stockpredictor
git add apps/web/src/app/page.tsx
git commit -m "feat: HomeQueryBox full chat upgrade — conversation history, cold-start banner, follow-ups"
```

---

## Task 5: Cold-Start Loading Animation on NLQueryBox (Ask AI Page)

**Root cause:** The `/query` page `NLQueryBox` already has bouncing dots, but no cold-start specific message. If the backend is cold, users see dots for 60s with no explanation.

**Files:**
- Modify: `apps/web/src/components/NLQueryBox.tsx`

- [ ] **Step 1: Add slow-load detection to NLQueryBox**

Add `slowLoad` state and timer to the `NLQueryBox` component. In the `ask` function, add:

```tsx
  const [slowLoad, setSlowLoad] = useState(false);
  const slowTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
```

In the `ask` function, before the API call, add:
```tsx
    setSlowLoad(false);
    slowTimer.current = setTimeout(() => setSlowLoad(true), 8000);
```

In the `finally` block, add:
```tsx
      setSlowLoad(false);
      if (slowTimer.current) clearTimeout(slowTimer.current);
```

- [ ] **Step 2: Add cold-start banner to NLQueryBox render**

In the `NLQueryBox` return, just above the input bar `<div className="flex gap-2">`, add:

```tsx
      {/* Cold-start warning */}
      {slowLoad && (
        <div className="flex items-center gap-2 px-3 py-2 bg-amber-500/10 border border-amber-500/20 rounded-lg">
          <span className="w-2 h-2 rounded-full bg-amber-400 animate-pulse flex-shrink-0" />
          <span className="text-xs text-amber-400">
            Backend warming up after inactivity (~60s first load). AI is thinking — please wait.
          </span>
        </div>
      )}
```

- [ ] **Step 3: Build and verify**

```bash
cd /c/Users/point/projects/stockpredictor/apps/web && npm run build 2>&1 | tail -10
```

Expected: Clean build.

- [ ] **Step 4: Commit**

```bash
cd /c/Users/point/projects/stockpredictor
git add apps/web/src/components/NLQueryBox.tsx
git commit -m "feat: cold-start warning banner in NLQueryBox after 8s wait"
```

---

## Task 6: Deploy and Smoke Test

- [ ] **Step 1: Push all commits to GitHub**

```bash
cd /c/Users/point/projects/stockpredictor && git push origin master 2>&1
```

- [ ] **Step 2: Deploy frontend to Vercel**

```bash
cd /c/Users/point/projects/stockpredictor/apps/web && vercel deploy --prod 2>&1 | tail -10
```

Expected: `Aliased: https://neuralquant.vercel.app`

- [ ] **Step 3: Trigger Render backend redeploy**

Go to render.com → NeuralQuant service → Manual Deploy → Deploy latest commit.

- [ ] **Step 4: Smoke test all fixes**

```bash
# Test 1: Trent (out-of-universe NSE stock)
curl -s -X POST http://127.0.0.1:8000/query \
  -H "Content-Type: application/json" \
  -d '{"question":"Should I invest in Trent?","market":"IN"}' | \
  python -c "import sys,json; d=json.load(sys.stdin); print('TRENT TEST:', d['answer'][:300])"

# Test 2: India portfolio allocation
curl -s -X POST http://127.0.0.1:8000/query \
  -H "Content-Type: application/json" \
  -d '{"question":"I want to invest 10 lakhs in Indian stocks, give specific recommendations","market":"IN"}' | \
  python -c "import sys,json; d=json.load(sys.stdin); print('INDIA PORTFOLIO:', d['answer'][:400])"

# Test 3: TCS range projection
curl -s -X POST http://127.0.0.1:8000/query \
  -H "Content-Type: application/json" \
  -d '{"question":"Give me a 1 month price projection for TCS with bear/base/bull","market":"IN"}' | \
  python -c "import sys,json; d=json.load(sys.stdin); print('TCS PROJECTION:', d['answer'][:400])"

# Test 4: Context window (two-turn)
# Send Q1
curl -s -X POST http://127.0.0.1:8000/query \
  -H "Content-Type: application/json" \
  -d '{"question":"Tell me about NVDA","market":"US"}' | \
  python -c "import sys,json; d=json.load(sys.stdin); print('NVDA Q1:', d['answer'][:200])"
```

Expected results:
- Trent: Contains "₹" + actual price + fundamentals, NO mention of Bharti/Maruti
- India portfolio: Lists 4+ specific NSE tickers with rupee allocations
- TCS: Bear/base/bull percentage ranges present
- NVDA: Score, price, clear verdict

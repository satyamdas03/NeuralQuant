"""
Deep test of NeuralQuant live site and API.
Run: python deep_test_live.py
"""
import requests, json, time, sys

API = "https://neuralquant.onrender.com"
SITE = "https://www.neuralquant.co"

results = []

def test(name, method, path, expected_status=200, timeout=30, payload=None, headers=None, extract=None):
    url = f"{API}{path}"
    start = time.time()
    status = None
    resp_text = ""
    error = None
    data = None
    try:
        if method == "GET":
            r = requests.get(url, timeout=timeout, headers=headers)
        else:
            r = requests.post(url, json=payload, timeout=timeout, headers=headers)
        status = r.status_code
        resp_text = r.text
        if r.headers.get("content-type", "").startswith("application/json"):
            data = r.json()
    except Exception as e:
        error = str(e)
    elapsed = time.time() - start

    extracted = {}
    if data and extract:
        for key, path_list in extract.items():
            try:
                val = data
                for p in path_list:
                    if isinstance(val, dict):
                        val = val.get(p)
                    elif isinstance(val, list) and isinstance(p, int):
                        val = val[p]
                    else:
                        val = None
                        break
                extracted[key] = val
            except Exception:
                extracted[key] = None

    results.append({
        "name": name,
        "status": status,
        "elapsed": round(elapsed, 2),
        "error": error,
        "extracted": extracted,
        "data": data,
        "resp_preview": resp_text[:500] if not data else ""
    })
    print(f"[{name}] status={status} time={elapsed:.2f}s error={error} extracted={json.dumps(extracted, default=str)}")

# 1. Health check
print("\n=== 1. Health ===")
test("health", "GET", "/health", timeout=10,
     extract={"status": ["status"]})

# 2. Stock scores
print("\n=== 2. Stock Scores ===")
test("score_AAPL", "GET", "/stocks/AAPL", timeout=30,
     extract={"score": ["score"], "price": ["price"], "pe": ["pe"], "beta": ["beta"], "verdict": ["verdict"], "name": ["name"]})

test("score_TCS_IN", "GET", "/stocks/TCS?market=IN", timeout=30,
     extract={"score": ["score"], "price": ["price"], "pe": ["pe"], "beta": ["beta"], "verdict": ["verdict"], "name": ["name"]})

test("score_NVDA", "GET", "/stocks/NVDA", timeout=30,
     extract={"score": ["score"], "price": ["price"], "pe": ["pe"], "beta": ["beta"], "verdict": ["verdict"], "name": ["name"]})

# 3. Stock meta
print("\n=== 3. Stock Meta ===")
test("meta_AAPL", "GET", "/stocks/AAPL/meta", timeout=30,
     extract={"sector": ["sector"], "industry": ["industry"], "market_cap": ["market_cap"], "dividend_yield": ["dividend_yield"]})

test("meta_TCS_IN", "GET", "/stocks/TCS/meta?market=IN", timeout=30,
     extract={"sector": ["sector"], "industry": ["industry"], "market_cap": ["market_cap"], "dividend_yield": ["dividend_yield"]})

# 4. Market overview
print("\n=== 4. Market Overview ===")
test("market_overview", "GET", "/market/overview", timeout=30,
     extract={"spy_change": ["spy", "change_percent"], "vix": ["vix", "value"], "trend": ["trend"]})

# 5. Sectors
print("\n=== 5. Sectors ===")
test("sectors", "GET", "/market/sectors", timeout=30,
     extract={"count": ["sectors"], "first_name": ["sectors", 0, "name"], "first_change": ["sectors", 0, "change_percent"]})

# 6. Movers
print("\n=== 6. Movers ===")
test("movers", "GET", "/market/movers", timeout=30,
     extract={"gainers_count": ["gainers"], "losers_count": ["losers"], "first_gainer": ["gainers", 0, "symbol"], "first_gainer_change": ["gainers", 0, "change_percent"]})

# 7. Screener preview
print("\n=== 7. Screener ===")
test("screener_value", "GET", "/screener/preview?preset=value_play", timeout=30,
     extract={"count": ["results"], "first_symbol": ["results", 0, "symbol"], "first_score": ["results", 0, "score"]})

# 8. Sentiment
print("\n=== 8. Sentiment ===")
test("sentiment_AAPL", "GET", "/sentiment/news/AAPL", timeout=30,
     extract={"sentiment": ["sentiment"], "articles": ["articles"]})

# 9. Ask AI non-streaming NVDA
print("\n=== 9. Ask AI NVDA ===")
test("askai_nvda", "POST", "/query/v2", timeout=60,
     payload={"query": "What is the outlook for NVDA?", "ticker": "NVDA"},
     extract={"has_response": ["response"], "has_data": ["data"], "verdict": ["data", "verdict"], "score": ["data", "score"]})

# 10. Ask AI portfolio INR
print("\n=== 10. Ask AI Portfolio INR ===")
test("askai_portfolio_inr", "POST", "/query/v2", timeout=60,
     payload={"query": "I have 10 lakh rupees, build my portfolio"},
     extract={"is_portfolio": ["is_portfolio_response"], "has_response": ["response"]})

# 11. Ask AI portfolio USD
print("\n=== 11. Ask AI Portfolio USD ===")
test("askai_portfolio_usd", "POST", "/query/v2", timeout=60,
     payload={"query": "I have 50000 dollars, build my portfolio"},
     extract={"is_portfolio": ["is_portfolio_response"], "has_response": ["response"]})

# 12. PARA-DEBATE
print("\n=== 12. PARA-DEBATE ===")
test("paradebate_nvda", "POST", "/analyst", timeout=120,
     payload={"ticker": "NVDA", "streaming": False},
     extract={"has_debate": ["debate"], "has_verdict": ["verdict"], "bull_count": ["bull_count"], "bear_count": ["bear_count"]})

# 13. Backtest
print("\n=== 13. Backtest ===")
test("backtest_aapl", "POST", "/backtest", timeout=45,
     payload={"ticker": "AAPL"},
     extract={"ticker": ["ticker"], "sharpe": ["sharpe_ratio"], "cagr": ["cagr"], "max_dd": ["max_drawdown"], "trades": ["trade_count"]})

# 14. News
print("\n=== 14. News ===")
test("news", "GET", "/news", timeout=30,
     extract={"articles": ["articles"], "first_headline": ["articles", 0, "headline"]})

# Summary
print("\n" + "="*60)
print("SUMMARY")
print("="*60)
passed = 0
failed = 0
for r in results:
    ok = r["status"] == 200 and r["error"] is None
    if ok:
        passed += 1
    else:
        failed += 1
    print(f"{'[PASS]' if ok else '[FAIL]'} {r['name']}: HTTP {r['status']} | {r['elapsed']}s | {r['error'] or 'OK'}")

print(f"\nTotal: {len(results)} | Passed: {passed} | Failed: {failed}")

# Data accuracy checks
print("\n" + "="*60)
print("DATA ACCURACY SPOT CHECKS")
print("="*60)
for r in results:
    name = r["name"]
    ex = r.get("extracted", {})
    if name == "score_AAPL":
        pe = ex.get("pe")
        beta = ex.get("beta")
        print(f"AAPL: price={ex.get('price')} P/E={pe} beta={beta} score={ex.get('score')} verdict={ex.get('verdict')}")
        # Known rough values: AAPL P/E ~32-36, beta ~1.2
        if pe and (pe < 20 or pe > 50):
            print("  WARNING: AAPL P/E looks off")
        if beta and (beta < 0.5 or beta > 2.0):
            print("  WARNING: AAPL beta looks off")
    elif name == "score_NVDA":
        pe = ex.get("pe")
        beta = ex.get("beta")
        print(f"NVDA: price={ex.get('price')} P/E={pe} beta={beta} score={ex.get('score')} verdict={ex.get('verdict')}")
        # Known: NVDA P/E ~40-50, beta ~2.0+
        if pe and (pe < 30 or pe > 80):
            print("  WARNING: NVDA P/E looks off")
        if beta and (beta < 1.5 or beta > 3.0):
            print("  WARNING: NVDA beta looks off")
    elif name == "score_TCS_IN":
        print(f"TCS: price={ex.get('price')} P/E={ex.get('pe')} beta={ex.get('beta')} score={ex.get('score')} verdict={ex.get('verdict')}")
    elif name == "meta_AAPL":
        print(f"AAPL meta: sector={ex.get('sector')} industry={ex.get('industry')} mcap={ex.get('market_cap')}")
    elif name == "market_overview":
        print(f"Market: SPY change={ex.get('spy_change')} VIX={ex.get('vix')} trend={ex.get('trend')}")
    elif name == "sectors":
        print(f"Sectors: count={ex.get('count')} first={ex.get('first_name')} ({ex.get('first_change')})")
    elif name == "movers":
        print(f"Movers: gainers={ex.get('gainers_count')} losers={ex.get('losers_count')} top={ex.get('first_gainer')} ({ex.get('first_gainer_change')})")
    elif name == "askai_portfolio_inr":
        print(f"Portfolio INR: is_portfolio={ex.get('is_portfolio')}")
    elif name == "askai_portfolio_usd":
        print(f"Portfolio USD: is_portfolio={ex.get('is_portfolio')}")
    elif name == "paradebate_nvda":
        print(f"PARA-DEBATE NVDA: has_debate={ex.get('has_debate') is not None} verdict={ex.get('has_verdict') is not None} bull={ex.get('bull_count')} bear={ex.get('bear_count')}")
    elif name == "backtest_aapl":
        print(f"Backtest AAPL: sharpe={ex.get('sharpe')} CAGR={ex.get('cagr')} maxDD={ex.get('max_dd')} trades={ex.get('trades')}")
        if ex.get("max_dd") and ex.get("max_dd") > 1.0:
            print("  WARNING: max_drawdown > 100% — likely decimal format bug")
    elif name == "screener_value":
        print(f"Screener: count={ex.get('count')} first={ex.get('first_symbol')} score={ex.get('first_score')}")
    elif name == "sentiment_AAPL":
        print(f"Sentiment AAPL: sentiment={ex.get('sentiment')} articles={ex.get('articles')}")

# Save full results
with open("deep_test_results.json", "w") as f:
    json.dump(results, f, indent=2, default=str)
print("\nFull results saved to deep_test_results.json")

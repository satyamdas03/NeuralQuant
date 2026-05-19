import requests, json, time

API = "https://neuralquant.onrender.com"
SITE = "https://www.neuralquant.co"

results = []

def test(name, method, path, base=API, expected_status=200, timeout=30, payload=None, headers=None, extract=None):
    url = f"{base}{path}"
    start = time.time()
    status = None
    error = None
    data = None
    text = ""
    try:
        if method == "GET":
            r = requests.get(url, timeout=timeout, headers=headers)
        else:
            r = requests.post(url, json=payload, timeout=timeout, headers=headers)
        status = r.status_code
        text = r.text
        try:
            data = r.json()
        except Exception:
            data = None
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
                        val = val[p] if p < len(val) else None
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
        "text_preview": text[:500] if not data else ""
    })
    status_str = f"HTTP {status}"
    print(f"[{name}] {status_str} | {elapsed:.2f}s | {error or 'OK'}")
    if extracted:
        print(f"  Extracted: {json.dumps(extracted, default=str)[:300]}")
    return status, data, extracted

print("\n===== 1. HEALTH =====")
test("health", "GET", "/health", timeout=10,
     extract={"status": ["status"], "version": ["version"]})

print("\n===== 2. STOCK SCORES =====")
test("score_AAPL", "GET", "/stocks/AAPL", timeout=30,
     extract={"composite_score": ["composite_score"], "score_1_10": ["score_1_10"],
              "regime": ["regime_label"], "confidence": ["confidence"], "ticker": ["ticker"]})
test("score_TCS_IN", "GET", "/stocks/TCS?market=IN", timeout=30,
     extract={"composite_score": ["composite_score"], "score_1_10": ["score_1_10"],
              "regime": ["regime_label"], "confidence": ["confidence"], "ticker": ["ticker"]})
test("score_NVDA", "GET", "/stocks/NVDA", timeout=30,
     extract={"composite_score": ["composite_score"], "score_1_10": ["score_1_10"],
              "regime": ["regime_label"], "confidence": ["confidence"], "ticker": ["ticker"]})

print("\n===== 3. STOCK META =====")
test("meta_AAPL", "GET", "/stocks/AAPL/meta", timeout=30,
     extract={"name": ["name"], "sector": ["sector"], "pe_ttm": ["pe_ttm"],
              "beta": ["beta"], "price": ["current_price"], "mcap": ["market_cap_fmt"],
              "dividend_yield": ["dividend_yield"]})
test("meta_TCS_IN", "GET", "/stocks/TCS/meta?market=IN", timeout=30,
     extract={"name": ["name"], "sector": ["sector"], "pe_ttm": ["pe_ttm"],
              "beta": ["beta"], "price": ["current_price"], "mcap": ["market_cap_fmt"],
              "dividend_yield": ["dividend_yield"]})

print("\n===== 4. MARKET OVERVIEW =====")
test("market_overview", "GET", "/market/overview", timeout=30,
     extract={"spy_price": ["indices", 0, "price"], "spy_change": ["indices", 0, "change_pct"],
              "nasdaq_price": ["indices", 1, "price"], "nasdaq_change": ["indices", 1, "change_pct"]})

print("\n===== 5. SECTORS =====")
test("sectors", "GET", "/market/sectors", timeout=30,
     extract={"count": ["sectors"], "first_name": ["sectors", 0, "name"],
              "first_change": ["sectors", 0, "change_pct"]})

print("\n===== 6. MOVERS =====")
test("movers", "GET", "/market/movers", timeout=30,
     extract={"top_gainer": ["gainers", 0, "ticker"], "top_gainer_change": ["gainers", 0, "change_pct"],
              "top_loser": ["losers", 0, "ticker"], "top_loser_change": ["losers", 0, "change_pct"]})

print("\n===== 7. SCREENER =====")
test("screener_value", "GET", "/screener/preview?preset=value_play", timeout=30,
     extract={"total": ["total"], "first_symbol": ["results", 0, "ticker"],
              "first_score": ["results", 0, "composite_score"], "first_score_1_10": ["results", 0, "score_1_10"]})

print("\n===== 8. SENTIMENT =====")
test("sentiment_AAPL", "GET", "/sentiment/news/AAPL", timeout=30,
     extract={"aggregate_score": ["aggregate_score"], "label": ["label"],
              "n_headlines": ["n_headlines"]})

print("\n===== 9. ASK AI NVDA (corrected field) =====")
test("askai_nvda", "POST", "/query/v2", timeout=60,
     payload={"question": "What is the outlook for NVDA?", "ticker": "NVDA"},
     extract={"has_response": ["response"], "has_data": ["data"],
              "verdict": ["data", "verdict"], "score": ["data", "score"]})

print("\n===== 10. ASK AI PORTFOLIO INR =====")
test("askai_portfolio_inr", "POST", "/query/v2", timeout=60,
     payload={"question": "I have 10 lakh rupees, build my portfolio"},
     extract={"is_portfolio": ["is_portfolio_response"], "has_response": ["response"]})

print("\n===== 11. ASK AI PORTFOLIO USD =====")
test("askai_portfolio_usd", "POST", "/query/v2", timeout=60,
     payload={"question": "I have 50000 dollars, build my portfolio"},
     extract={"is_portfolio": ["is_portfolio_response"], "has_response": ["response"]})

print("\n===== 12. PARA-DEBATE =====")
test("paradebate_nvda", "POST", "/analyst", timeout=150,
     payload={"ticker": "NVDA", "streaming": False},
     extract={"verdict": ["head_analyst_verdict"], "consensus": ["consensus_score"],
              "bull_present": ["bull_case"], "bear_present": ["bear_case"]})

print("\n===== 13. BACKTEST =====")
test("backtest_aapl", "POST", "/backtest", timeout=45,
     payload={"ticker": "AAPL"},
     extract={"ticker": ["ticker"], "sharpe": ["sharpe"],
              "cagr": ["total_return_pct"], "max_dd": ["max_drawdown_pct"],
              "trades": ["n_trades"], "n_days": ["n_days"],
              "buy_hold": ["buy_hold_return_pct"]})

print("\n===== 14. NEWS =====")
test("news", "GET", "/news", timeout=30,
     extract={"sentiment": ["sentiment"],
              "first_headline": ["headlines", 0, "title"]})

print("\n===== 15. SITE HOMEPAGE =====")
test("site_homepage", "GET", "/", base=SITE, timeout=15,
     extract={})

# ===== SUMMARY =====
print("\n" + "="*70)
print("SUMMARY")
print("="*70)
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

# ===== DATA ACCURACY CHECKS =====
print("\n" + "="*70)
print("DATA ACCURACY SPOT CHECKS")
print("="*70)

for r in results:
    name = r["name"]
    ex = r.get("extracted", {})

    if name == "meta_AAPL":
        pe = ex.get("pe_ttm")
        beta = ex.get("beta")
        price = ex.get("price")
        print(f"\nAAPL META: price=${price} | P/E={pe} | beta={beta} | mcap={ex.get('mcap')} | sector={ex.get('sector')}")
        if price and abs(price - 287) > 50:
            print("  WARNING: AAPL price looks off")
        if pe and (pe < 25 or pe > 45):
            print(f"  WARNING: AAPL P/E looks off")
        if beta and abs(beta - 1.2) > 0.4:
            print(f"  WARNING: AAPL beta looks off")

    elif name == "meta_TCS_IN":
        pe = ex.get("pe_ttm")
        beta = ex.get("beta")
        price = ex.get("price")
        print(f"\nTCS META: price={price} | P/E={pe} | beta={beta} | mcap={ex.get('mcap')} | sector={ex.get('sector')}")
        if price == 0.0 or price is None:
            print("  ISSUE: TCS current_price is 0/null")
        if beta is None:
            print("  ISSUE: TCS beta is null")
        if pe and (pe < 10 or pe > 30):
            print(f"  WARNING: TCS P/E looks off")

    elif name == "score_AAPL":
        cs = ex.get("composite_score")
        s10 = ex.get("score_1_10")
        print(f"\nAAPL SCORE: composite={cs} | 1-10={s10} | regime={ex.get('regime')} | confidence={ex.get('confidence')}")
        if cs is None or s10 is None:
            print("  ISSUE: Score fields missing")

    elif name == "score_NVDA":
        cs = ex.get("composite_score")
        s10 = ex.get("score_1_10")
        print(f"\nNVDA SCORE: composite={cs} | 1-10={s10} | regime={ex.get('regime')} | confidence={ex.get('confidence')}")

    elif name == "score_TCS_IN":
        cs = ex.get("composite_score")
        s10 = ex.get("score_1_10")
        print(f"\nTCS SCORE: composite={cs} | 1-10={s10} | regime={ex.get('regime')} | confidence={ex.get('confidence')}")

    elif name == "market_overview":
        spy = ex.get("spy_price")
        spy_chg = ex.get("spy_change")
        print(f"\nMARKET: SPY={spy} ({spy_chg}%) | NASDAQ={ex.get('nasdaq_price')} ({ex.get('nasdaq_change')}%)")
        if spy and (spy < 5000 or spy > 8000):
            print(f"  WARNING: SPY price looks off")

    elif name == "sectors":
        cnt = len(ex.get("count", [])) if isinstance(ex.get("count"), list) else ex.get("count")
        print(f"\nSECTORS: count={cnt} | first={ex.get('first_name')} ({ex.get('first_change')}%)")

    elif name == "movers":
        print(f"\nMOVERS: top_gainer={ex.get('top_gainer')} ({ex.get('top_gainer_change')}%) | top_loser={ex.get('top_loser')} ({ex.get('top_loser_change')}%)")

    elif name == "screener_value":
        print(f"\nSCREENER: total={ex.get('total')} | first={ex.get('first_symbol')} score={ex.get('first_score')} (1-10={ex.get('first_score_1_10')})")

    elif name == "sentiment_AAPL":
        print(f"\nSENTIMENT AAPL: score={ex.get('aggregate_score')} | label={ex.get('label')} | headlines={ex.get('n_headlines')}")

    elif name == "askai_nvda":
        print(f"\nASK AI NVDA: has_response={ex.get('has_response') is not None} | has_data={ex.get('has_data') is not None} | verdict={ex.get('verdict')} | score={ex.get('score')}")

    elif name == "askai_portfolio_inr":
        print(f"\nASK AI PORTFOLIO INR: is_portfolio={ex.get('is_portfolio')} | has_response={ex.get('has_response') is not None}")

    elif name == "askai_portfolio_usd":
        print(f"\nASK AI PORTFOLIO USD: is_portfolio={ex.get('is_portfolio')} | has_response={ex.get('has_response') is not None}")

    elif name == "paradebate_nvda":
        print(f"\nPARA-DEBATE NVDA: verdict={ex.get('verdict')} | consensus={ex.get('consensus')} | bull_present={ex.get('bull_present') is not None} | bear_present={ex.get('bear_present') is not None}")
        consensus = ex.get("consensus")
        if consensus is not None and abs(consensus) > 1.0:
            print(f"  WARNING: consensus_score magnitude > 1 ({consensus})")

    elif name == "backtest_aapl":
        dd = ex.get("max_dd")
        print(f"\nBACKTEST AAPL: sharpe={ex.get('sharpe')} | return={ex.get('cagr')}% | maxDD={dd}% | trades={ex.get('trades')} | days={ex.get('n_days')} | buy&hold={ex.get('buy_hold')}%")
        if dd is not None and dd < -100:
            print(f"  CRITICAL: max_drawdown < -100%")
        if dd is not None and dd > 0:
            print(f"  WARNING: max_drawdown is positive ({dd})")

    elif name == "news":
        print(f"\nNEWS: sentiment={ex.get('sentiment')} | first='{ex.get('first_headline', '')[:70]}...'")

    elif name == "site_homepage":
        print(f"\nSITE HOMEPAGE: HTTP {r['status']} | {r['elapsed']}s | length={len(r.get('text_preview', ''))}")

with open("deep_test_results_v3.json", "w") as f:
    json.dump(results, f, indent=2, default=str)
print("\n\nFull results saved to deep_test_results_v3.json")

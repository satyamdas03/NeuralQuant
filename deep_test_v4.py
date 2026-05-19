#!/usr/bin/env python3
"""Deep test v4 — comprehensive production endpoint test after curl_cffi fix."""
import json
import time
import urllib.request
import urllib.error

BASE = "https://neuralquant.onrender.com"
TIMEOUT = 30

def get(path, timeout=TIMEOUT):
    try:
        req = urllib.request.Request(f"{BASE}{path}", headers={"User-Agent": "DeepTest/4.0"})
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read())
    except Exception as e:
        return {"ERROR": str(e)}

def test(name, result, check_fn):
    try:
        ok, detail = check_fn(result)
        status = "PASS" if ok else "FAIL"
        print(f"  {status} | {name} | {detail}")
        return ok
    except Exception as e:
        print(f"  FAIL | {name} | exception: {e}")
        return False

def main():
    results = []
    print("=" * 70)
    print("NEURALQUANT DEEP TEST v4 — Post curl_cffi Fix")
    print("=" * 70)

    # 1. Health
    print("\n--- Health ---")
    r = get("/health")
    results.append(test("Health", r, lambda d: (d.get("status") == "ok", f'version={d.get("version")}')))

    # 2. Market Overview (US) — CRITICAL: must not be 0.0
    print("\n--- Market Overview US ---")
    r = get("/market/overview?market=US", timeout=60)
    def check_overview_us(d):
        if "ERROR" in d:
            return False, f'error: {d["ERROR"]}'
        indices = d.get("indices", [])
        if not indices:
            return False, "no indices returned"
        sp500 = next((i for i in indices if i["symbol"] == "^GSPC"), {})
        price = sp500.get("price", 0)
        if price == 0.0:
            return False, f'S&P 500 price is 0.0 — curl_cffi likely still missing'
        return True, f'S&P 500: {price} ({sp500.get("change_pct", "N/A")}%)'
    results.append(test("Market Overview US", r, check_overview_us))

    # 3. Market Overview (India)
    print("\n--- Market Overview IN ---")
    r = get("/market/overview?market=IN", timeout=60)
    def check_overview_in(d):
        if "ERROR" in d:
            return False, f'error: {d["ERROR"]}'
        indices = d.get("indices", [])
        nifty = next((i for i in indices if i["symbol"] == "^NSEI"), {})
        price = nifty.get("price", 0)
        if price == 0.0:
            return False, f'Nifty 50 price is 0.0'
        return True, f'Nifty 50: {price} ({nifty.get("change_pct", "N/A")}%)'
    results.append(test("Market Overview IN", r, check_overview_in))

    # 4. Sectors — must not all be 0.00%
    print("\n--- Sectors ---")
    r = get("/market/sectors", timeout=60)
    def check_sectors(d):
        if "ERROR" in d:
            return False, f'error: {d["ERROR"]}'
        sectors = d.get("sectors", [])
        if not sectors:
            return False, "no sectors returned"
        zero_count = sum(1 for s in sectors if s.get("change_pct", -1) == 0.0)
        if zero_count > 8:
            return False, f'{zero_count}/11 sectors have 0.00% change'
        xlk = next((s for s in sectors if s["symbol"] == "XLK"), {})
        return True, f'XLK: {xlk.get("change_pct", "N/A")}%, {zero_count}/11 at 0.00%'
    results.append(test("Sectors", r, check_sectors))

    # 5. Movers
    print("\n--- Movers ---")
    r = get("/market/movers", timeout=60)
    def check_movers(d):
        if "ERROR" in d:
            return False, f'error: {d["ERROR"]}'
        gainers = d.get("gainers", [])
        losers = d.get("losers", [])
        active = d.get("active", [])
        if not gainers and not losers:
            return False, "no gainers/losers returned"
        top = gainers[0] if gainers else {}
        return True, f'{len(gainers)} gainers, {len(losers)} losers, {len(active)} active | top: {top.get("ticker","?")} {top.get("change_pct","?")}%'
    results.append(test("Movers", r, check_movers))

    # 6. News
    print("\n--- News ---")
    r = get("/market/news?n=3", timeout=30)
    def check_news(d):
        if "ERROR" in d:
            return False, f'error: {d["ERROR"]}'
        news = d.get("news", [])
        if not news:
            return False, "no news returned"
        return True, f'{len(news)} articles | top: {news[0].get("title","?")[:60]}'
    results.append(test("News", r, check_news))

    # 7. Stock Score AAPL (US)
    print("\n--- Stock Score AAPL ---")
    r = get("/stocks/AAPL", timeout=45)
    def check_stock_score(d):
        if "ERROR" in d:
            return False, f'error: {d["ERROR"]}'
        score = d.get("composite_score", 0)
        name = d.get("ticker", "?")
        if score == 0:
            return False, f'{name} composite_score is 0'
        return True, f'{name}: score={score:.4f}, 1-10={d.get("score_1_10","?")}'
    results.append(test("Stock Score AAPL", r, check_stock_score))

    # 8. Stock Meta AAPL (US)
    print("\n--- Stock Meta AAPL ---")
    r = get("/stocks/AAPL/meta", timeout=45)
    def check_meta(d):
        if "ERROR" in d:
            return False, f'error: {d["ERROR"]}'
        pe = d.get("pe_ttm", 0)
        price = d.get("current_price", 0)
        if pe == 0 or price == 0:
            return False, f'pe_ttm={pe}, current_price={price}'
        return True, f'AAPL: P/E={pe}, price=${price}, sector={d.get("sector","?")}'
    results.append(test("Stock Meta AAPL", r, check_meta))

    # 9. Indian Stock TCS
    print("\n--- Stock Meta TCS (India) ---")
    r = get("/stocks/TCS/meta?market=IN", timeout=45)
    def check_india(d):
        if "ERROR" in d:
            return False, f'error: {d["ERROR"]}'
        pe = d.get("pe_ttm", 0)
        price = d.get("current_price", 0)
        if pe == 0:
            return False, f'TCS pe_ttm=0 (blank Indian data)'
        return True, f'TCS: P/E={pe}, price=₹{price}, sector={d.get("sector","?")}'
    results.append(test("Indian Stock TCS", r, check_india))

    # 10. Data Quality
    print("\n--- Data Quality ---")
    r = get("/market/data-quality", timeout=30)
    def check_quality(d):
        real = d.get("tickers_with_real_data", 0)
        synthetic = d.get("tickers_with_synthetic_fallback", 0)
        macro_ok = d.get("macro_is_real", False)
        if real == 0:
            return False, f'0 real tickers (all synthetic), macro={macro_ok}'
        return True, f'{real} real, {synthetic} synthetic, macro={macro_ok}'
    results.append(test("Data Quality", r, check_quality))

    # 11. Sentiment
    print("\n--- Sentiment ---")
    r = get("/sentiment/news/AAPL", timeout=30)
    def check_sentiment(d):
        if "ERROR" in d:
            return False, f'error: {d["ERROR"]}'
        articles = d.get("articles", [])
        if not articles:
            return False, "no sentiment articles"
        return True, f'{len(articles)} articles'
    results.append(test("Sentiment AAPL", r, check_sentiment))

    # Summary
    passed = sum(1 for r in results if r)
    total = len(results)
    print(f"\n{'='*70}")
    print(f"RESULTS: {passed}/{total} passed")
    if passed < total:
        print(f"FAILURES: {total - passed} tests failed")
    print(f"{'='*70}")
    return passed == total

if __name__ == "__main__":
    success = main()
    exit(0 if success else 1)
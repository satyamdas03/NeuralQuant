"""
Deep test v2 — inspects actual response shapes first.
"""
import requests, json, time

API = "https://neuralquant.onrender.com"

results = []

def test(name, method, path, expected_status=200, timeout=30, payload=None, headers=None):
    url = f"{API}{path}"
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
        text = r.text[:2000]
        try:
            data = r.json()
        except Exception:
            data = None
    except Exception as e:
        error = str(e)
    elapsed = time.time() - start

    results.append({
        "name": name,
        "status": status,
        "elapsed": round(elapsed, 2),
        "error": error,
        "text": text,
        "data": data
    })
    return status, data, text, elapsed

# --- 1. Health ---
print("\n=== 1. HEALTH ===")
s, d, t, e = test("health", "GET", "/health", timeout=10)
print(f"Status: {s}, Time: {e:.2f}s")
if d: print(f"Keys: {list(d.keys())} | Data: {json.dumps(d, indent=2)[:500]}")

# --- 2. Stock Scores --- inspect shape
print("\n=== 2. STOCK SCORES (AAPL) ===")
s, d, t, e = test("score_AAPL", "GET", "/stocks/AAPL", timeout=30)
print(f"Status: {s}, Time: {e:.2f}s")
if d:
    print(f"Top keys: {list(d.keys())}")
    # Print first level values (truncated)
    for k, v in d.items():
        preview = json.dumps(v)[:200] if not isinstance(v, str) else v[:200]
        print(f"  {k}: {preview}")

print("\n=== 2b. STOCK SCORES (NVDA) ===")
s, d, t, e = test("score_NVDA", "GET", "/stocks/NVDA", timeout=30)
print(f"Status: {s}, Time: {e:.2f}s")
if d:
    for k, v in d.items():
        preview = json.dumps(v)[:200] if not isinstance(v, str) else v[:200]
        print(f"  {k}: {preview}")

print("\n=== 2c. STOCK SCORES (TCS?market=IN) ===")
s, d, t, e = test("score_TCS_IN", "GET", "/stocks/TCS?market=IN", timeout=30)
print(f"Status: {s}, Time: {e:.2f}s")
if d:
    for k, v in d.items():
        preview = json.dumps(v)[:200] if not isinstance(v, str) else v[:200]
        print(f"  {k}: {preview}")

# --- 3. Meta ---
print("\n=== 3. META AAPL ===")
s, d, t, e = test("meta_AAPL", "GET", "/stocks/AAPL/meta", timeout=30)
print(f"Status: {s}, Time: {e:.2f}s")
if d: print(json.dumps(d, indent=2, default=str)[:1000])

print("\n=== 3b. META TCS IN ===")
s, d, t, e = test("meta_TCS_IN", "GET", "/stocks/TCS/meta?market=IN", timeout=30)
print(f"Status: {s}, Time: {e:.2f}s")
if d: print(json.dumps(d, indent=2, default=str)[:1000])

# --- 4. Market overview ---
print("\n=== 4. MARKET OVERVIEW ===")
s, d, t, e = test("market_overview", "GET", "/market/overview", timeout=30)
print(f"Status: {s}, Time: {e:.2f}s")
if d:
    print(f"Top keys: {list(d.keys())}")
    for k, v in d.items():
        preview = json.dumps(v)[:300] if not isinstance(v, str) else v[:300]
        print(f"  {k}: {preview}")

# --- 5. Sectors ---
print("\n=== 5. SECTORS ===")
s, d, t, e = test("sectors", "GET", "/market/sectors", timeout=30)
print(f"Status: {s}, Time: {e:.2f}s")
if d:
    print(f"Top keys: {list(d.keys())}")
    for k, v in d.items():
        preview = json.dumps(v)[:300] if not isinstance(v, str) else v[:300]
        print(f"  {k}: {preview}")

# --- 6. Movers ---
print("\n=== 6. MOVERS ===")
s, d, t, e = test("movers", "GET", "/market/movers", timeout=30)
print(f"Status: {s}, Time: {e:.2f}s")
if d:
    print(f"Top keys: {list(d.keys())}")
    for k, v in d.items():
        preview = json.dumps(v)[:400] if not isinstance(v, str) else v[:400]
        print(f"  {k}: {preview}")

# --- 7. Screener ---
print("\n=== 7. SCREENER ===")
s, d, t, e = test("screener", "GET", "/screener/preview?preset=value_play", timeout=30)
print(f"Status: {s}, Time: {e:.2f}s")
if d:
    print(f"Top keys: {list(d.keys())}")
    for k, v in d.items():
        preview = json.dumps(v)[:400] if not isinstance(v, str) else v[:400]
        print(f"  {k}: {preview}")

# --- 8. Sentiment ---
print("\n=== 8. SENTIMENT AAPL ===")
s, d, t, e = test("sentiment_AAPL", "GET", "/sentiment/news/AAPL", timeout=30)
print(f"Status: {s}, Time: {e:.2f}s")
if d:
    print(f"Top keys: {list(d.keys())}")
    for k, v in d.items():
        preview = json.dumps(v)[:400] if not isinstance(v, str) else v[:400]
        print(f"  {k}: {preview}")

# --- 9. Ask AI — inspect 422 reason ---
print("\n=== 9. ASK AI NVDA ===")
s, d, t, e = test("askai_nvda", "POST", "/query/v2", timeout=60, payload={"query": "What is the outlook for NVDA?", "ticker": "NVDA"})
print(f"Status: {s}, Time: {e:.2f}s")
print(f"Response text: {t}")
if d:
    print(f"Top keys: {list(d.keys())}")
    for k, v in d.items():
        preview = json.dumps(v)[:400] if not isinstance(v, str) else v[:400]
        print(f"  {k}: {preview}")

# Try different payload shape
print("\n=== 9b. ASK AI NVDA (alt payload) ===")
s, d, t, e = test("askai_nvda_alt", "POST", "/query/v2", timeout=60, payload={"message": "What is the outlook for NVDA?", "ticker": "NVDA"})
print(f"Status: {s}, Time: {e:.2f}s")
print(f"Response text: {t}")

# --- 10. Ask AI Portfolio INR ---
print("\n=== 10. ASK AI PORTFOLIO INR ===")
s, d, t, e = test("askai_portfolio_inr", "POST", "/query/v2", timeout=60, payload={"query": "I have 10 lakh rupees, build my portfolio"})
print(f"Status: {s}, Time: {e:.2f}s")
print(f"Response text: {t}")

# --- 11. Ask AI Portfolio USD ---
print("\n=== 11. ASK AI PORTFOLIO USD ===")
s, d, t, e = test("askai_portfolio_usd", "POST", "/query/v2", timeout=60, payload={"query": "I have 50000 dollars, build my portfolio"})
print(f"Status: {s}, Time: {e:.2f}s")
print(f"Response text: {t}")

# --- 12. PARA-DEBATE ---
print("\n=== 12. PARA-DEBATE NVDA ===")
s, d, t, e = test("paradebate_nvda", "POST", "/analyst", timeout=120, payload={"ticker": "NVDA", "streaming": False})
print(f"Status: {s}, Time: {e:.2f}s")
if d:
    print(f"Top keys: {list(d.keys())}")
    for k, v in d.items():
        preview = json.dumps(v)[:500] if not isinstance(v, str) else v[:500]
        print(f"  {k}: {preview}")

# --- 13. Backtest ---
print("\n=== 13. BACKTEST AAPL ===")
s, d, t, e = test("backtest_aapl", "POST", "/backtest", timeout=45, payload={"ticker": "AAPL"})
print(f"Status: {s}, Time: {e:.2f}s")
if d:
    print(f"Top keys: {list(d.keys())}")
    for k, v in d.items():
        preview = json.dumps(v)[:400] if not isinstance(v, str) else v[:400]
        print(f"  {k}: {preview}")

# --- 14. News ---
print("\n=== 14. NEWS ===")
s, d, t, e = test("news", "GET", "/news", timeout=30)
print(f"Status: {s}, Time: {e:.2f}s")
if d:
    print(f"Top keys: {list(d.keys())}")
    for k, v in d.items():
        preview = json.dumps(v)[:400] if not isinstance(v, str) else v[:400]
        print(f"  {k}: {preview}")

# Save
with open("deep_test_results_v2.json", "w") as f:
    json.dump(results, f, indent=2, default=str)
print("\n\nSaved to deep_test_results_v2.json")

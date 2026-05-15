"""End-to-end data pipeline test with real API keys."""
import os
import sys

# Verify env
print("=== ENV CHECK ===")
for k in ["FMP_API_KEY", "FINNHUB_API_KEY", "ANTHROPIC_API_KEY"]:
    print(f"  {k}: {'present' if os.getenv(k) else 'MISSING'}")

print("\n=== US STOCK: AAPL ===")
from nq_api.data_builder import _fetch_one
aapl = _fetch_one("AAPL", "US", fast_pe=False)
for k in ["current_price", "pe_ttm", "beta", "market_cap", "sector", "_is_real", "_is_synthetic", "long_name"]:
    print(f"  {k}={aapl.get(k)}")

print("\n=== IN STOCK: TCS.NS ===")
tcs = _fetch_one("TCS.NS", "IN", fast_pe=False)
for k in ["current_price", "pe_ttm", "beta", "market_cap", "sector", "_is_real", "_is_synthetic", "long_name"]:
    print(f"  {k}={tcs.get(k)}")

# Validation
assert aapl.get("_is_real"), "AAPL should be real"
assert aapl.get("current_price", 0) > 0, "AAPL should have price"
assert abs(aapl.get("current_price", 0) - 298.21) / 298.21 < 0.10, f"AAPL price {aapl.get('current_price')} too far from expected ~$298"

assert tcs.get("_is_real"), "TCS should be real"
assert tcs.get("current_price", 0) > 0, "TCS should have price"

print("\n=== VALIDATION MODULE ===")
from nq_api.validation import extract_verified_values, validate_metrics, validate_summary_prices, validate_response

ctx = "AAPL: CURRENT_PRICE=$196.50 [VERIFIED] | P/E_TTM=34.6 [VERIFIED] | BETA=1.5 [VERIFIED]"
v = extract_verified_values(ctx)
print(f"  extracted: {v}")
assert v["CURRENT_PRICE"] == 196.50
assert v["P_E_TTM"] == 34.6
assert v["BETA"] == 1.5

class FakeMetric:
    def __init__(self, name, value):
        self.name = name
        self.value = value

metrics = [FakeMetric("P/E (TTM)", "28.9x"), FakeMetric("Current Price", "$180.00")]
v3 = {"CURRENT_PRICE": 196.50, "P_E_TTM": 34.6}
corrections = []
validate_metrics(metrics, v3, corrections)
print(f"  metric corrections: {corrections}")
assert len(corrections) == 2

summary = "Trading at $185, this stock is undervalued."
s, c = validate_summary_prices(summary, v3)
print(f"  summary corrections: {c}")
assert "$196.50" in s

print("\n=== ALL TESTS PASSED ===")

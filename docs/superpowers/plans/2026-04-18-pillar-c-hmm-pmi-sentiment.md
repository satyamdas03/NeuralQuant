# Pillar C Implementation Plan — Fitted HMM + ISM PMI + Reddit/StockTwits Sentiment

> superpowers:executing-plans

**Goal:** Upgrade macro regime classification from heuristic to fitted 3-state HMM on 20-year FRED history; add ISM PMI as a macro feature; ingest Reddit + StockTwits retail sentiment as a new per-ticker factor.

**Architecture:** `hmmlearn` trained offline, pickled to `apps/api/data/hmm_regime.pkl`, loaded at boot. ISM PMI via FRED series `NAPM`. Sentiment daily pull script → Supabase `sentiment_daily` → joined into factor snapshot.

---

## File Map

| File | Change |
|---|---|
| `apps/api/pyproject.toml` | add `hmmlearn>=0.3`, `praw>=7.8`, `vaderSentiment>=3.3`, `stocktwits` (custom minimal client) |
| `scripts/train_hmm.py` | NEW — fit hmmlearn on 20yr FRED data, pickle |
| `apps/api/data/hmm_regime.pkl` | NEW — output of training (committed once) |
| `apps/api/src/nq_api/macro/hmm_regime.py` | NEW — load model, predict regime + probs |
| `apps/api/src/nq_api/data_builder.py` | inject `ism_pmi` via FRED `NAPM`, call hmm_regime for `macro_regime` |
| `apps/api/src/nq_signals/score_engine.py` | consume `macro_regime` + `ism_pmi`, plumb sentiment factor |
| `apps/api/src/nq_api/sentiment/reddit.py` | NEW — PRAW client, top subs r/stocks r/investing r/wallstreetbets, VADER score per ticker mention |
| `apps/api/src/nq_api/sentiment/stocktwits.py` | NEW — StockTwits public JSON API, bullish/bearish ratio |
| `scripts/daily_sentiment.py` | NEW — union Reddit + StockTwits, upsert `sentiment_daily` |
| `.github/workflows/daily-sentiment.yml` | NEW — cron hourly during market hours |
| `sql/004_sentiment_daily.sql` | NEW |

---

## Task 1: Train HMM

- [ ] `sql/004_sentiment_daily.sql`:
```sql
CREATE TABLE IF NOT EXISTS public.sentiment_daily (
  ticker TEXT NOT NULL,
  day DATE NOT NULL,
  reddit_mentions INT DEFAULT 0,
  reddit_vader NUMERIC,
  stocktwits_bullish_pct NUMERIC,
  stocktwits_messages INT DEFAULT 0,
  composite_sentiment NUMERIC,
  PRIMARY KEY (ticker, day)
);
CREATE INDEX idx_sentiment_day ON public.sentiment_daily(day DESC);
ALTER TABLE public.sentiment_daily ENABLE ROW LEVEL SECURITY;
CREATE POLICY sentiment_public_read ON public.sentiment_daily FOR SELECT USING (true);
```

- [ ] `scripts/train_hmm.py`:
  - Pull FRED: `VIXCLS`, `BAMLH0A0HYM2` (HY spread), `T10Y2Y`, `UNRATE`, `INDPRO`, monthly from 2005.
  - Compute z-scores per feature, drop NaN, fit `GaussianHMM(n_components=3, covariance_type="diag", n_iter=100)`.
  - Map states to labels by mean VIX: lowest = `RISK_ON`, highest = `RISK_OFF`, middle = `NEUTRAL`.
  - Pickle `{"model": gmm, "scaler": standardizer, "state_to_label": {0:"RISK_ON",...}}`.
  - Print transition matrix + mean-by-state for sanity.

## Task 2: Runtime HMM predictor

- [ ] `apps/api/src/nq_api/macro/hmm_regime.py`:
```python
class HMMRegime:
    def __init__(self, path="apps/api/data/hmm_regime.pkl"): ...
    def predict(self, macro_snapshot: dict) -> tuple[str, dict[str, float]]:
        # z-score input, model.predict_proba on last row, return label + {RISK_ON:.., NEUTRAL:.., RISK_OFF:..}
```
- [ ] Swap heuristic regime in `data_builder.fetch_real_macro` for the fitted call. Expose `regime_probs` on MacroSnapshot.

## Task 3: Add ISM PMI

- [ ] `data_builder.fetch_real_macro`: pull FRED `NAPM` (monthly), set `macro.ism_pmi = latest`. Cache 24h.
- [ ] `score_engine.compute`: if `ism_pmi < 50`, downweight momentum factor by 0.15 (contraction regime).

## Task 4: Reddit ingest

- [ ] `sentiment/reddit.py`:
  - PRAW client with env creds.
  - For each subreddit in `["stocks","investing","wallstreetbets","IndianStockMarket"]`, fetch top 200 `new` posts + comments.
  - Extract tickers via regex `\$?[A-Z]{1,5}\b` filtered against universe.
  - Score post body with VADER; aggregate per ticker → mean `vader_compound`, mention count.
  - Emit list of `{ticker, reddit_mentions, reddit_vader}`.

## Task 5: StockTwits ingest

- [ ] `sentiment/stocktwits.py`:
  - Public endpoint `https://api.stocktwits.com/api/2/streams/symbol/{TICKER}.json` (30 msgs, no auth, 200 req/hr).
  - Parse `entities.sentiment.basic` → count `Bullish` / `Bearish`.
  - Emit `{ticker, stocktwits_bullish_pct, stocktwits_messages}`.
  - Rate-limit: 60 tickers/hour ceiling → iterate 500-stock universe in 9 hourly batches (fits inside GHA schedule).

## Task 6: Daily job

- [ ] `scripts/daily_sentiment.py`:
  - Run Reddit (single pass, cheap).
  - Batch StockTwits (50 tickers/run, rotating cursor stored in Supabase key-value or row timestamp).
  - Composite: `composite_sentiment = 0.5 * reddit_vader + 0.5 * (stocktwits_bullish_pct - 0.5) * 2` (normalized to [-1,1]).
  - Upsert `sentiment_daily` keyed on `(ticker, day)`.

## Task 7: Sentiment as factor

- [ ] `data_builder.build_real_snapshot`: join latest `sentiment_daily` row per ticker → add `sentiment_score` column.
- [ ] `score_engine.compute`: add `sentiment_percentile` factor with weight 0.10 (existing factors scaled down proportionally). Surface in `AIScore.features`.

## Task 8: Workflow

- [ ] `.github/workflows/daily-sentiment.yml`:
```yaml
name: daily-sentiment
on:
  schedule: [{cron: "0 */2 * * 1-5"}]    # every 2 hours, Mon-Fri
  workflow_dispatch: {}
jobs:
  run:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with: {python-version: "3.12"}
      - run: pip install uv && uv sync --all-packages
      - run: uv run python scripts/daily_sentiment.py
        env:
          SUPABASE_URL: ${{ secrets.SUPABASE_URL }}
          SUPABASE_SERVICE_ROLE_KEY: ${{ secrets.SUPABASE_SERVICE_ROLE_KEY }}
          REDDIT_CLIENT_ID: ${{ secrets.REDDIT_CLIENT_ID }}
          REDDIT_CLIENT_SECRET: ${{ secrets.REDDIT_CLIENT_SECRET }}
          REDDIT_USER_AGENT: NeuralQuant/0.1
```

## Task 9: Test

- [ ] `test_hmm_predict.py` — load pickled model, assert regime is one of 3 labels, probs sum to 1.
- [ ] `test_sentiment_join.py` — mock Supabase, assert snapshot gets sentiment column joined.
- [ ] Live smoke: hit `/stocks/NVDA` → verify `features.sentiment_percentile` present.

## Risks

- **Reddit rate-limit** — PRAW at 60 QPM. Safe for 4 subs × 200 posts.
- **StockTwits bans scraping** — use their official JSON API (200 req/hr), respect with batching.
- **HMM state instability** — retrain quarterly; if state means drift, relabel.
- **Sentiment data latency** — cache can be ≤ 2h old; OK because sentiment is slow-moving signal.

## Success metrics

- HMM regime matches NBER recession flag ≥ 85% on held-out 2020-2024 test set
- ISM PMI field populated in every `/market/overview` payload
- sentiment_daily covers ≥ 90% of full universe within 24h of cron start
- sentiment factor weight 0.10 doesn't degrade Sharpe in backtest (see Pillar D)

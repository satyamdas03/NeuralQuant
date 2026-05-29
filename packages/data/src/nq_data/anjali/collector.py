"""Anjali Value Screener — data collector.

Ports the anjali-value-stocks collector into the NeuralQuant data pipeline.
Returns DataFrames instead of writing CSVs. Uses JSON checkpointing for resume.

Usage:
    df = collect_stocks(universe="SP500", market="US")
    df = collect_stocks(universe="NIFTY200", market="IN")
"""
from __future__ import annotations

import logging
import math
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal

import numpy as np
import pandas as pd
import yfinance as yf

logger = structlog.get_logger() if __import__("os").environ.get("STRUCTLOG") else logging.getLogger(__name__)

# Checkpoint file path (JSON-based, simpler than DuckDB for checkpoint data)
_CHECKPOINT_DIR = Path(__file__).resolve().parents[4] / "data" / "anjali_checkpoints"

# ---------------------------------------------------------------------------
# Universe definitions
# ---------------------------------------------------------------------------

SP500_TICKERS: list[str] = []  # Populated dynamically from Wikipedia or fallback
SP400_TICKERS: list[str] = []  # S&P MidCap 400 — populated dynamically
SP600_TICKERS: list[str] = []  # S&P SmallCap 600 — populated dynamically

NIFTY200_TICKERS: list[str] = [
    "RELIANCE", "TCS", "HDFCBANK", "INFY", "HINDUNILVR", "ICICIBANK",
    "SBIN", "BHARTIARTL", "KOTAKBANK", "LT", "HCLTECH", "WIPRO",
    "ASIANPAINT", "MARUTI", "SUNPHARMA", "ULTRACEMCO", "BAJFINANCE",
    "TITAN", "NESTLEIND", "POWERGRID", "NTPC", "ONGC", "COALINDIA",
    "TATASTEEL", "JSWSTEEL", "HINDALCO", "ADANIPORTS", "ADANIENT",
    "DMART", "PIDILITIND", "EICHERMOT", "BAJAJ-AUTO", "HEROMOTOCO",
    "M&M", "DRREDDY", "CIPLA", "DIVISLAB", "APOLLOHOSP",
    "TECHM", "GRASIM", "TATAMOTORS", "TATACONSUM", "BAJAJFINSV",
    "BRITANNIA", "DABUR", "GODREJCP", "COLPAL", "MPHASIS",
    "OFSS", "WIPRO", "HDFC LIFE", "SBILIFE", "ICICIGI",
    "TATAELXSI", "LTI", "MINDTREE", "MPHASIS", "PERSISTENT",
    "CLEAN", "ATGL", "IEX", "DELHIVERY", "POLICYBZR",
    "NYKAA", "PAYTM", "ZOMATO", "BLUEDART", "CONCOR",
    "TVSMOTOR", "MOTHERSON", "BOSCHLTD", "MRF", "PAGEIND",
    "HINDPETRO", "BPCL", "IOC", "GAIL", "NLCINDIA",
    "NHPC", "SJVN", "POWERGRID", "REC", "PFC",
    "PNBHOUSING", "CANBK", "UNIONBANK", "BANKBARODA", "IDFCFIRSTB",
    "INDUSINDBK", "FEDERALBNK", "BANDHANBNK", "RBLBANK", "YESBANK",
    "LICHSGFIN", "MANAPPURAM", "MUTHOOTFIN", "CHOLAFIN", "SHRIRAMFIN",
    "ESCORTS", "ASHOKLEY", "CONCOR", "IRCTC", "Avenue Supermart",
]

# Fallback S&P 500 (top 100 by market cap)
SP500_FALLBACK = [
    "AAPL", "MSFT", "AMZN", "NVDA", "GOOGL", "GOOG", "META", "BRK-B", "LLY", "AVGO",
    "TSLA", "JPM", "V", "UNH", "WMT", "XOM", "MA", "PG", "JNJ", "HD",
    "COST", "ABBV", "MRK", "ORCL", "BAC", "AMD", "CRM", "NFLX", "ADBE", "CVX",
    "KO", "SHW", "INTU", "TMO", "COP", "VZ", "QCOM", "ABT", "PEP", "PGR",
    "MS", "AXP", "CAT", "LIN", "NOW", "SPGI", "ISRG", "PLTR", "DELL", "UBER",
    "CMCSA", "SYK", "T", "INTC", "LOW", "IBM", "DIS", "GS", "AMAT", "VRTX",
    "RTX", "BLK", "ETN", "REGN", "BSX", "BKNG", "MU", "C", "CB", "CI",
    "GE", "NKE", "BDX", "CHTR", "MMC", "HON", "TGT", "UPS", "FDX",
    "AMGN", "CME", "MDLZ", "ADI", "CSX", "LRCX", "PYPL", "NEE", "SLB", "SRE",
]

# Revenue/Income row name variants for yfinance financial statements
REVENUE_ROWS = ["TotalRevenue", "Total Revenue", "Net Revenue"]
INCOME_ROWS = [
    "NetIncome", "Net Income", "Net Income Common Stockholders",
    "Net Income Continuous Operations",
]

# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------

def _safe_round(val, decimals: int = 2):
    """Round a value, returning None if NaN."""
    if val is None or (isinstance(val, float) and (math.isnan(val) or math.isinf(val))):
        return None
    try:
        return round(float(val), decimals)
    except (TypeError, ValueError):
        return None


def _try_financials_row(fin, row_names: list[str], col_name: str):
    """Try multiple row name variants to extract a value from yfinance financials."""
    row = next((r for r in row_names if r in fin.index), None)
    if row:
        val = fin.loc[row, col_name]
        if pd.notna(val):
            return float(val)
    return None


def _fetch_sp500_tickers() -> list[str]:
    """Fetch current S&P 500 constituents from Wikipedia."""
    import requests
    from io import StringIO
    logger.info("Fetching S&P 500 tickers from Wikipedia")
    try:
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
        resp = requests.get(
            "https://en.wikipedia.org/wiki/List_of_S%26P_500_companies",
            headers=headers, timeout=15,
        )
        resp.raise_for_status()
        tables = pd.read_html(StringIO(resp.text))
        df = tables[0]
        tickers = df["Symbol"].str.replace(".", "-", regex=False).tolist()
        logger.info(f"Fetched {len(tickers)} S&P 500 tickers from Wikipedia")
        return tickers
    except Exception as e:
        logger.warning(f"Wikipedia fetch failed: {e}, using fallback")
        return SP500_FALLBACK


def _fetch_sp400_tickers() -> list[str]:
    """Fetch current S&P MidCap 400 constituents from Wikipedia."""
    import requests
    from io import StringIO
    logger.info("Fetching S&P 400 tickers from Wikipedia")
    try:
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
        resp = requests.get(
            "https://en.wikipedia.org/wiki/List_of_S%26P_400_companies",
            headers=headers, timeout=15,
        )
        resp.raise_for_status()
        tables = pd.read_html(StringIO(resp.text))
        df = tables[0]
        # Column may be "Symbol" or "Ticker" depending on page structure
        col = "Symbol" if "Symbol" in df.columns else "Ticker"
        tickers = df[col].str.replace(".", "-", regex=False).tolist()
        logger.info(f"Fetched {len(tickers)} S&P 400 tickers from Wikipedia")
        return tickers
    except Exception as e:
        logger.warning(f"SP400 Wikipedia fetch failed: {e}, using SP500 fallback")
        return SP500_FALLBACK


def _fetch_sp600_tickers() -> list[str]:
    """Fetch current S&P SmallCap 600 constituents from Wikipedia."""
    import requests
    from io import StringIO
    logger.info("Fetching S&P 600 tickers from Wikipedia")
    try:
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
        resp = requests.get(
            "https://en.wikipedia.org/wiki/List_of_S%26P_600_companies",
            headers=headers, timeout=15,
        )
        resp.raise_for_status()
        tables = pd.read_html(StringIO(resp.text))
        df = tables[0]
        col = "Symbol" if "Symbol" in df.columns else "Ticker"
        tickers = df[col].str.replace(".", "-", regex=False).tolist()
        logger.info(f"Fetched {len(tickers)} S&P 600 tickers from Wikipedia")
        return tickers
    except Exception as e:
        logger.warning(f"SP600 Wikipedia fetch failed: {e}, using SP500 fallback")
        return SP500_FALLBACK


def _fetch_benchmark(benchmark_ticker: str, period: str) -> pd.Series:
    """Fetch benchmark returns for beta calculation."""
    bench = yf.Ticker(benchmark_ticker)
    hist = bench.history(period=period)
    if hist.empty:
        return pd.Series(dtype=float)
    return hist["Close"].pct_change().dropna()


# ---------------------------------------------------------------------------
# Core collection function
# ---------------------------------------------------------------------------

def collect_stocks(
    universe: Literal["SP500", "SP400", "SP600", "NIFTY200"] = "SP500",
    market: Literal["US", "IN"] = "US",
    tickers: list[str] | None = None,
    checkpoint_every: int = 50,
    delay: float = 0.3,
) -> pd.DataFrame:
    """Collect fundamental + risk data for a universe of stocks.

    Args:
        universe: Which universe to score.
        market: US or IN market.
        tickers: Override universe with explicit ticker list.
        checkpoint_every: Save progress every N tickers (DuckDB checkpoint).
        delay: Seconds to sleep between yfinance calls (rate limiting).

    Returns:
        DataFrame with all Anjali columns (33 columns + loss flags).
    """
    # Resolve tickers
    if tickers is None:
        if universe == "SP500":
            tickers_list = _fetch_sp500_tickers()
        elif universe == "SP400":
            tickers_list = _fetch_sp400_tickers()
        elif universe == "SP600":
            tickers_list = _fetch_sp600_tickers()
        elif universe == "NIFTY200":
            tickers_list = NIFTY200_TICKERS
        else:
            tickers_list = SP500_FALLBACK
            logger.warning(f"Unknown universe {universe}, using SP500 fallback")
    else:
        tickers_list = tickers

    # Suffix for yfinance
    yf_suffix = ".NS" if market == "IN" else ""

    # Benchmark for beta
    benchmark_ticker = "^NSEI" if market == "IN" else "^GSPC"
    benchmark_3mo = _fetch_benchmark(benchmark_ticker, "3mo")
    benchmark_1y = _fetch_benchmark(benchmark_ticker, "1y")

    # Load checkpoint from JSON file if available
    checkpoint_file = _CHECKPOINT_DIR / f"{universe}_{market}.json"
    done_tickers: set[str] = set()
    if checkpoint_file.exists():
        try:
            import json
            existing = json.loads(checkpoint_file.read_text(encoding="utf-8"))
            done_tickers = {r["ticker"] for r in existing if "ticker" in r}
            logger.info(f"Checkpoint: {len(done_tickers)} tickers already collected, resuming")
        except Exception as e:
            logger.warning(f"Failed to load checkpoint: {e}")
            done_tickers = set()

    start_idx = 0
    results: list[dict] = []

    logger.info(f"Starting Anjali collection: {universe} ({market}), {len(tickers_list)} tickers")

    for i, ticker in enumerate(tickers_list):
        yf_sym = ticker + yf_suffix if yf_suffix and "." not in ticker else ticker

        if ticker in done_tickers:
            continue

        row = _collect_one(ticker, yf_sym, market, benchmark_3mo, benchmark_1y)
        if row:
            results.append(row)

        if (i + 1) % checkpoint_every == 0:
            logger.info(f"Checkpoint: {i + 1}/{len(tickers_list)} tickers processed, {len(results)} successful")
            # Save checkpoint to JSON
            if results:
                _save_checkpoint(results, universe, market)

        time.sleep(delay)

    # Final save
    if results:
        _save_checkpoint(results, universe, market)

    df = pd.DataFrame(results)
    logger.info(f"Collection complete: {len(df)} stocks collected for {universe} ({market})")
    return df


def _collect_one(
    ticker: str,
    yf_sym: str,
    market: str,
    benchmark_3mo: pd.Series,
    benchmark_1y: pd.Series,
) -> dict | None:
    """Collect data for a single stock. Returns dict or None on failure."""
    row: dict = {
        "ticker": ticker,
        "market": market,
    }

    try:
        stock = yf.Ticker(yf_sym)
        info = stock.info or {}

        if not info:
            logger.debug(f"Skipping {ticker}: no info returned")
            return None

        row["sector"] = info.get("sector", "")
        row["sub_sector"] = info.get("industry", "")

        # --- Growth ---
        row["sales_yoy_growth"] = _safe_round(info.get("revenueGrowth"), 4)  # already decimal
        if row["sales_yoy_growth"] is not None:
            row["sales_yoy_growth"] *= 100  # convert to percentage

        row["net_profit_yoy_growth"] = _safe_round(info.get("earningsGrowth"), 4)
        if row["net_profit_yoy_growth"] is not None:
            row["net_profit_yoy_growth"] *= 100

        # TTM growth from financials
        try:
            fin = stock.financials
            if fin is not None and not fin.empty:
                cols = list(fin.columns)
                if len(cols) >= 2:
                    latest = cols[0]
                    prior = cols[1]
                    rev_latest = _try_financials_row(fin, REVENUE_ROWS, latest)
                    rev_prior = _try_financials_row(fin, REVENUE_ROWS, prior)
                    ni_latest = _try_financials_row(fin, INCOME_ROWS, latest)
                    ni_prior = _try_financials_row(fin, INCOME_ROWS, prior)

                    if rev_latest and rev_prior and rev_prior != 0:
                        row["sales_ttm_growth"] = _safe_round((rev_latest / rev_prior - 1) * 100)
                    if ni_latest and ni_prior and ni_prior != 0:
                        row["net_profit_ttm_growth"] = _safe_round((ni_latest / ni_prior - 1) * 100)
        except Exception as e:
            logger.debug(f"Financials error for {ticker}: {e}")

        # QoQ from quarterly financials
        try:
            qfin = stock.quarterly_financials
            if qfin is not None and not qfin.empty:
                qcols = list(qfin.columns)
                if len(qcols) >= 2:
                    qrev_latest = _try_financials_row(qfin, REVENUE_ROWS, qcols[0])
                    qrev_prior = _try_financials_row(qfin, REVENUE_ROWS, qcols[1])
                    qni_latest = _try_financials_row(qfin, INCOME_ROWS, qcols[0])
                    qni_prior = _try_financials_row(qfin, INCOME_ROWS, qcols[1])

                    if qrev_latest and qrev_prior and qrev_prior != 0:
                        raw = (qrev_latest / qrev_prior - 1) * 100
                        row["qoq_sales_growth"] = _safe_round(max(-500, min(500, raw)))
                    if qni_latest and qni_prior and qni_prior != 0:
                        raw = (qni_latest / qni_prior - 1) * 100
                        row["qoq_profit_growth"] = _safe_round(max(-500, min(500, raw)))
        except Exception as e:
            logger.debug(f"Quarterly financials error for {ticker}: {e}")

        # Loss flags
        row["loss_profit_yoy"] = row.get("net_profit_yoy_growth") is not None and row["net_profit_yoy_growth"] < 0
        row["loss_profit_ttm"] = row.get("net_profit_ttm_growth") is not None and row["net_profit_ttm_growth"] < 0
        row["loss_profit_qoq"] = row.get("qoq_profit_growth") is not None and row["qoq_profit_growth"] < 0

        # --- Returns ---
        hist_3mo = stock.history(period="3mo")
        hist_6mo = stock.history(period="6mo")
        hist_1y = stock.history(period="1y")
        hist_2y = stock.history(period="2y")

        if len(hist_1y) > 1:
            price_now = hist_1y["Close"].iloc[-1]
            price_3m = hist_3mo["Close"].iloc[0] if len(hist_3mo) > 0 else None
            price_6m = hist_6mo["Close"].iloc[0] if len(hist_6mo) > 0 else None
            price_1y = hist_1y["Close"].iloc[0]
            price_2y = hist_2y["Close"].iloc[0] if len(hist_2y) > 0 else None

            row["return_3m"] = _safe_round(((price_now / price_3m) - 1) * 100) if price_3m else None
            row["return_6m"] = _safe_round(((price_now / price_6m) - 1) * 100) if price_6m else None
            row["return_1yr"] = _safe_round(((price_now / price_1y) - 1) * 100) if price_1y else None
            row["return_2yr"] = _safe_round(((price_now / price_2y) - 1) * 100) if price_2y else None

            # --- Risk ---
            daily_returns = hist_1y["Close"].pct_change().dropna()
            qtr_daily = daily_returns.tail(63)
            row["qtr_std"] = _safe_round(qtr_daily.std() * np.sqrt(252) * 100)
            row["yr_std"] = _safe_round(daily_returns.std() * np.sqrt(252) * 100)

            # Beta (aligned date intersection — CRITICAL for accuracy)
            if len(hist_3mo) > 10 and len(benchmark_3mo) > 10:
                stock_qtr_ret = hist_3mo["Close"].pct_change().dropna()
                common = stock_qtr_ret.index.intersection(benchmark_3mo.index)
                if len(common) > 10:
                    cov = np.cov(stock_qtr_ret.loc[common], benchmark_3mo.loc[common])[0][1]
                    var = np.var(benchmark_3mo.loc[common])
                    row["qtr_beta"] = _safe_round(cov / var, 4) if var > 0 else None

            if len(hist_1y) > 20 and len(benchmark_1y) > 20:
                stock_yr_ret = hist_1y["Close"].pct_change().dropna()
                common = stock_yr_ret.index.intersection(benchmark_1y.index)
                if len(common) > 20:
                    cov = np.cov(stock_yr_ret.loc[common], benchmark_1y.loc[common])[0][1]
                    var = np.var(benchmark_1y.loc[common])
                    row["yr_beta"] = _safe_round(cov / var, 4) if var > 0 else None

        # --- Valuation ---
        pe_raw = info.get("trailingPE")
        row["pe_ratio"] = _safe_round(pe_raw)

        # Future PE — CALCULATED, not yfinance forwardPE
        pe = row.get("pe_ratio")
        npg = row.get("net_profit_ttm_growth")
        if pe is not None and npg is not None and npg != 0:
            row["future_pe"] = _safe_round(pe * (1 + npg / 100))
            row["ttm_peg"] = _safe_round(pe / npg) if npg != 0 else None
            row["future_peg"] = _safe_round(row["future_pe"] / npg) if npg != 0 else None
        else:
            row["future_pe"] = None
            row["ttm_peg"] = None
            row["future_peg"] = None

        # PB — negative PB excluded (ABBV -108.95, DELL -68.76)
        pb_raw = info.get("priceToBook")
        row["pb_ratio"] = None if (pb_raw is None or pb_raw <= 0) else _safe_round(pb_raw)

        row["ev_sales"] = _safe_round(info.get("enterpriseToRevenue"))
        row["ev_ebitda"] = _safe_round(info.get("enterpriseToEbitda"))

        # --- Size (uncolored) ---
        mc = info.get("marketCap")
        row["market_cap_bn"] = _safe_round(mc / 1e9) if mc else None
        rev = info.get("totalRevenue")
        row["revenue_bn"] = _safe_round(rev / 1e9) if rev else None
        row["ttm_revenue_bn"] = row["revenue_bn"]  # approximate — same source

        # --- India-specific (NULL for now) ---
        row["dii_quarter"] = None
        row["dii_1yr"] = None
        row["fii_quarter"] = None
        row["fii_1yr"] = None

        # Metadata
        row["data_collected_at"] = datetime.now(timezone.utc).isoformat()
        row["index_group"] = None  # set by caller

        return row

    except Exception as e:
        logger.warning(f"Failed to collect {ticker}: {e}")
        return None


def _save_checkpoint(results: list[dict], universe: str, market: str) -> None:
    """Save collection progress to JSON checkpoint file."""
    import json
    try:
        _CHECKPOINT_DIR.mkdir(parents=True, exist_ok=True)
        checkpoint_file = _CHECKPOINT_DIR / f"{universe}_{market}.json"
        # Merge with existing checkpoint
        existing: list[dict] = []
        if checkpoint_file.exists():
            try:
                existing = json.loads(checkpoint_file.read_text(encoding="utf-8"))
            except Exception:
                existing = []
        # Merge: replace existing tickers with new data
        existing_tickers = {r["ticker"]: i for i, r in enumerate(existing) if "ticker" in r}
        for row in results:
            ticker = row.get("ticker")
            if ticker in existing_tickers:
                existing[existing_tickers[ticker]] = row
            else:
                existing.append(row)
        checkpoint_file.write_text(json.dumps(existing, default=str), encoding="utf-8")
        logger.debug(f"Checkpoint saved: {len(results)} rows, total {len(existing)}")
    except Exception as e:
        logger.warning(f"Checkpoint save failed: {e}")
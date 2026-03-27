from typing import Literal

import yfinance as yf
from fastapi import APIRouter, Depends, HTTPException, Query

from nq_api.deps import get_signal_engine
from nq_api.schemas import AIScore
from nq_api.score_builder import row_to_ai_score, rank_scores_in_universe
from nq_api.universe import UNIVERSE_BY_MARKET
from nq_api.data_builder import build_real_snapshot, _fund_cache
from nq_signals.engine import SignalEngine

router = APIRouter()

_PERIOD_MAP = {
    "1d":  ("1d",  "5m"),
    "5d":  ("5d",  "30m"),
    "1mo": ("1mo", "1d"),
    "3mo": ("3mo", "1d"),
    "1y":  ("1y",  "1d"),
    "5y":  ("5y",  "1wk"),
}


def _yf_sym(ticker: str, market: str) -> str:
    if market == "IN" and "." not in ticker:
        return ticker + ".NS"
    return ticker


def _fmt_mcap(mc: float) -> str:
    if mc >= 1e12: return f"${mc/1e12:.2f}T"
    if mc >= 1e9:  return f"${mc/1e9:.1f}B"
    if mc >= 1e6:  return f"${mc/1e6:.0f}M"
    return f"${mc:,.0f}"


@router.get("/{ticker}", response_model=AIScore)
def get_stock_score(
    ticker: str,
    market: Literal["US", "IN", "GLOBAL"] = Query("US"),
    engine: SignalEngine = Depends(get_signal_engine),
) -> AIScore:
    ticker_upper = ticker.upper()
    known_universe = list(UNIVERSE_BY_MARKET.get(market, UNIVERSE_BY_MARKET["US"]))

    # Always compute within full reference universe for meaningful percentile ranks
    universe = known_universe.copy()
    if ticker_upper not in universe:
        universe = [ticker_upper] + universe[:19]

    snapshot = build_real_snapshot(universe, market)
    result_df = engine.compute(snapshot)

    # BUG-001 fix: reject tickers that yfinance couldn't find (synthetic fallback + not in known universe)
    fund_data = _fund_cache.get(f"{ticker_upper}:{market}", {})
    if not fund_data.get("_is_real") and ticker_upper not in known_universe:
        raise HTTPException(
            status_code=404,
            detail=f"Ticker '{ticker_upper}' not found in {market} market. "
                   "Check the ticker symbol and market parameter."
        )

    matching = result_df[result_df["ticker"] == ticker_upper]
    if matching.empty:
        raise HTTPException(status_code=404, detail=f"No data for {ticker}")

    # Use rank-based 1-10 within the reference universe for consistent spread
    ranked_scores = rank_scores_in_universe(result_df)
    ticker_idx = matching.index[0]
    score_override = int(ranked_scores.iloc[ticker_idx]) if ticker_idx < len(ranked_scores) else None

    return row_to_ai_score(matching.iloc[0], market, score_1_10_override=score_override)


@router.get("/{ticker}/chart")
def get_stock_chart(
    ticker: str,
    period: str = Query("1mo"),
    market: str = Query("US"),
):
    yf_period, interval = _PERIOD_MAP.get(period, ("1mo", "1d"))
    sym = _yf_sym(ticker.upper(), market)
    try:
        hist = yf.Ticker(sym).history(period=yf_period, interval=interval, auto_adjust=True)
    except Exception as exc:
        raise HTTPException(500, str(exc))
    if hist.empty:
        raise HTTPException(404, f"No chart data for {ticker}")

    data = []
    for idx, row in hist.iterrows():
        # Intraday: keep HH:MM; daily: keep YYYY-MM-DD
        if period in ("1d", "5d"):
            date_str = idx.strftime("%m/%d %H:%M")
        else:
            date_str = idx.strftime("%b %d")
        try:
            data.append({
                "date": date_str,
                "close": round(float(row["Close"]), 2),
                "open":  round(float(row["Open"]),  2),
                "high":  round(float(row["High"]),  2),
                "low":   round(float(row["Low"]),   2),
                "volume": int(row.get("Volume") or 0),
            })
        except Exception:
            pass

    period_change = 0.0
    if len(data) >= 2:
        first = data[0]["close"]
        last  = data[-1]["close"]
        period_change = round((last - first) / first * 100, 2) if first else 0.0

    return {"ticker": ticker.upper(), "period": period, "data": data, "period_change_pct": period_change}


@router.get("/{ticker}/meta")
def get_stock_meta(ticker: str, market: str = Query("US")):
    sym = _yf_sym(ticker.upper(), market)
    try:
        t = yf.Ticker(sym)
        info = t.info or {}

        # Earnings date
        earnings_date = None
        try:
            cal = t.calendar
            if isinstance(cal, dict):
                ed = cal.get("Earnings Date")
                if ed and len(ed) > 0:
                    earnings_date = str(ed[0].date())
        except Exception:
            pass

        mc = info.get("marketCap")
        return {
            "ticker":                  ticker.upper(),
            "name":                    info.get("longName") or info.get("shortName") or ticker,
            "market_cap":              mc,
            "market_cap_fmt":          _fmt_mcap(float(mc)) if mc else None,
            "pe_ttm":                  round(float(info["trailingPE"]), 1)  if info.get("trailingPE")    else None,
            "pb_ratio":                round(float(info["priceToBook"]), 2) if info.get("priceToBook")   else None,
            "beta":                    round(float(info["beta"]), 2)        if info.get("beta")          else None,
            "week_52_high":            info.get("fiftyTwoWeekHigh"),
            "week_52_low":             info.get("fiftyTwoWeekLow"),
            "earnings_date":           earnings_date,
            "analyst_target":          info.get("targetMeanPrice"),
            "analyst_recommendation":  info.get("recommendationKey"),
            "sector":                  info.get("sector"),
            "industry":                info.get("industry"),
            "dividend_yield":          round(float(info["dividendYield"]) * 100, 2) if info.get("dividendYield") else None,
            "current_price":           info.get("currentPrice") or info.get("regularMarketPrice"),
        }
    except Exception as exc:
        raise HTTPException(500, str(exc))

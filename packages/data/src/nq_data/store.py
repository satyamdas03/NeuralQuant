import duckdb
from datetime import date
from pathlib import Path
from typing import Optional
from .models import OHLCVBar, FundamentalSnapshot, MacroSnapshot

_SCHEMA = """
CREATE TABLE IF NOT EXISTS ohlcv (
    ticker VARCHAR NOT NULL,
    market VARCHAR NOT NULL,
    date DATE NOT NULL,
    open DOUBLE,
    high DOUBLE,
    low DOUBLE,
    close DOUBLE,
    volume DOUBLE,
    adjusted_close DOUBLE,
    delivery_pct DOUBLE,
    PRIMARY KEY (ticker, market, date)
);
CREATE TABLE IF NOT EXISTS fundamentals (
    ticker VARCHAR NOT NULL,
    market VARCHAR NOT NULL,
    as_of_date DATE NOT NULL,
    pe_ttm DOUBLE, pb DOUBLE, ps DOUBLE,
    roe DOUBLE, gross_margin DOUBLE, net_margin DOUBLE,
    revenue_growth_yoy DOUBLE, fcf_yield DOUBLE, debt_equity DOUBLE,
    piotroski_score INTEGER, accruals_ratio DOUBLE, beneish_m_score DOUBLE,
    PRIMARY KEY (ticker, market, as_of_date)
);
CREATE TABLE IF NOT EXISTS macro (
    as_of_date DATE PRIMARY KEY,
    vix DOUBLE, yield_10y DOUBLE, yield_2y DOUBLE,
    yield_spread_2y10y DOUBLE, hy_spread_oas DOUBLE,
    ism_pmi DOUBLE, cpi_yoy DOUBLE, fed_funds_rate DOUBLE,
    spx_vs_200ma DOUBLE
);
"""

class DataStore:
    def __init__(self, db_path: str = "neuralquant.duckdb"):
        self.db_path = db_path
        self._conn = duckdb.connect(db_path)
        self._conn.execute(_SCHEMA)

    def upsert_ohlcv(self, bars: list[OHLCVBar]) -> None:
        if not bars:
            return
        rows = [(b.ticker, b.market, b.date, b.open, b.high, b.low,
                 b.close, b.volume, b.adjusted_close, b.delivery_pct) for b in bars]
        self._conn.executemany(
            "INSERT OR REPLACE INTO ohlcv VALUES (?,?,?,?,?,?,?,?,?,?)", rows
        )

    def get_ohlcv(self, ticker: str, market: str,
                  start: date, end: date) -> list[OHLCVBar]:
        rows = self._conn.execute(
            "SELECT * FROM ohlcv WHERE ticker=? AND market=? AND date BETWEEN ? AND ? ORDER BY date",
            [ticker, market, start, end]
        ).fetchall()
        cols = ["ticker","market","date","open","high","low","close","volume","adjusted_close","delivery_pct"]
        return [OHLCVBar(**dict(zip(cols, r))) for r in rows]

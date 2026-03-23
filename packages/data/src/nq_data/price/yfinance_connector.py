import yfinance as yf
import pandas as pd
from datetime import date, timedelta
from ..models import OHLCVBar
from ..broker import broker

SUFFIX = {"IN": ".NS", "IN_BSE": ".BO"}

class YFinanceConnector:
    def fetch(self, ticker: str, market: str,
              start: date, end: date) -> list[OHLCVBar]:
        """Fetch daily OHLCV bars. Market: 'US' | 'IN' | 'IN_BSE'"""
        yf_ticker = ticker + SUFFIX.get(market, "")
        with broker.acquire("yfinance"):
            df = yf.download(
                yf_ticker,
                start=start.isoformat(),
                end=(end + timedelta(days=1)).isoformat(),
                progress=False,
                auto_adjust=False,
            )
        if df.empty:
            return []
        # Flatten MultiIndex columns if present (newer yfinance versions)
        if isinstance(df.columns, pd.MultiIndex):
            # Find which level has the price fields (Open, High, Low, Close, Volume)
            price_fields = {"Open", "High", "Low", "Close", "Volume", "Adj Close"}
            if any(c in price_fields for c in df.columns.get_level_values(0)):
                df.columns = df.columns.get_level_values(0)  # level 0 = price fields
            else:
                df.columns = df.columns.get_level_values(1)  # level 1 = price fields
        df = df.reset_index()
        # Normalize Date column name
        if "Datetime" in df.columns:
            df = df.rename(columns={"Datetime": "Date"})
        bars = []
        store_market = "IN" if market == "IN_BSE" else market
        for _, row in df.iterrows():
            bars.append(OHLCVBar(
                ticker=ticker,
                market=store_market,
                date=row["Date"].date() if hasattr(row["Date"], "date") else row["Date"],
                open=float(row["Open"]),
                high=float(row["High"]),
                low=float(row["Low"]),
                close=float(row["Close"]),
                volume=float(row["Volume"]),
                adjusted_close=float(row.get("Adj Close", row["Close"])),
            ))
        return bars

    def fetch_batch(self, tickers: list[str], market: str,
                    start: date, end: date) -> list[OHLCVBar]:
        """Batch fetch for efficiency — yfinance supports multi-ticker download."""
        suffixed = [t + SUFFIX.get(market, "") for t in tickers]
        with broker.acquire("yfinance"):
            df = yf.download(
                " ".join(suffixed),
                start=start.isoformat(),
                end=(end + timedelta(days=1)).isoformat(),
                progress=False,
                auto_adjust=False,
                group_by="ticker",
            )
        if df.empty:
            return []

        # Handle MultiIndex columns from newer yfinance
        if isinstance(df.columns, pd.MultiIndex):
            # group_by="ticker" puts ticker as level 0, field as level 1
            # or field as level 0, ticker as level 1 depending on version
            # Try to detect and normalize so level 0 = tickers
            levels = df.columns.get_level_values(0).unique().tolist()
            if any(t in levels for t in suffixed):
                # level 0 = tickers (expected format)
                pass
            else:
                # swap levels so tickers are at level 0
                df.columns = df.columns.swaplevel()

        store_market = "IN" if market == "IN_BSE" else market
        bars = []
        for orig_ticker, suffixed_ticker in zip(tickers, suffixed):
            try:
                sub = df[suffixed_ticker].dropna(subset=["Close"])
            except KeyError:
                continue
            for ts, row in sub.iterrows():
                bars.append(OHLCVBar(
                    ticker=orig_ticker, market=store_market,
                    date=ts.date(),
                    open=float(row["Open"]), high=float(row["High"]),
                    low=float(row["Low"]), close=float(row["Close"]),
                    volume=float(row["Volume"]),
                    adjusted_close=float(row.get("Adj Close", row["Close"])),
                ))
        return bars

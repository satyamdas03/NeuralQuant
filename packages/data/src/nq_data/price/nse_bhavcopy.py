"""
NSE Bhavcopy downloader. Completely free, no API key.
Bhavcopy URL pattern: https://nsearchives.nseindia.com/content/historical/EQUITIES/<YYYY>/<MMM>/cm<DD><MMM><YYYY>bhav.csv.zip
"""
import io
import zipfile
import requests
import pandas as pd
from datetime import date
from ..models import OHLCVBar
from ..broker import broker

NSE_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Referer": "https://www.nseindia.com",
    "Accept-Encoding": "gzip, deflate, br",
    "Accept-Language": "en-US,en;q=0.9",
}

class NSEBhavCopyConnector:
    BASE_URL = "https://nsearchives.nseindia.com/content/historical/EQUITIES/{year}/{month}/cm{day}{month}{year}bhav.csv.zip"

    def download_bhavcopy(self, for_date: date) -> list[OHLCVBar]:
        """Download and parse Bhavcopy for a given date."""
        url = self.BASE_URL.format(
            year=for_date.strftime("%Y"),
            month=for_date.strftime("%b").upper(),
            day=for_date.strftime("%d"),
        )
        with broker.acquire("nse"):
            resp = requests.get(url, headers=NSE_HEADERS, timeout=30)
        if resp.status_code != 200:
            return []  # Non-trading day or data not yet available
        with zipfile.ZipFile(io.BytesIO(resp.content)) as zf:
            csv_name = zf.namelist()[0]
            with zf.open(csv_name) as f:
                content = f.read().decode("utf-8")
        return self.parse_bhavcopy(io.StringIO(content), for_date)

    def parse_bhavcopy(self, source, for_date: date) -> list[OHLCVBar]:
        """Parse Bhavcopy CSV. source can be file path str or StringIO."""
        df = pd.read_csv(source)
        # Normalize column names (Bhavcopy format varies slightly by year)
        df.columns = [c.strip() for c in df.columns]
        series_col = df.get("SERIES", df.get("Series", pd.Series(dtype=str)))
        eq = df[series_col.str.strip() == "EQ"]
        bars = []
        for _, row in eq.iterrows():
            ticker = str(row.get("SYMBOL", row.get("Symbol", ""))).strip()
            tottrd = float(row.get("TOTTRDQTY", row.get("TOTTRDQTY", 0)) or 0)
            deliv = float(row.get("DELIV_QTY", row.get("DELVQTY", 0)) or 0)
            delivery_pct = (deliv / tottrd * 100) if tottrd > 0 else None
            bars.append(OHLCVBar(
                ticker=ticker, market="IN",
                date=for_date,
                open=float(row.get("OPEN", row.get("Open", 0)) or 0),
                high=float(row.get("HIGH", row.get("High", 0)) or 0),
                low=float(row.get("LOW", row.get("Low", 0)) or 0),
                close=float(row.get("CLOSE", row.get("Close", 0)) or 0),
                volume=tottrd,
                delivery_pct=delivery_pct,
            ))
        return bars

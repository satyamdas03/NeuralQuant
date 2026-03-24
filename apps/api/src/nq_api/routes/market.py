"""GET /market — live market data via yfinance."""
from fastapi import APIRouter
import yfinance as yf

router = APIRouter()

_INDICES = {
    "^GSPC": "S&P 500",
    "^IXIC": "NASDAQ",
    "^DJI": "Dow Jones",
    "^VIX": "VIX",
}

_SECTORS = {
    "XLK": "Technology",
    "XLE": "Energy",
    "XLF": "Financial Services",
    "XLV": "Healthcare",
    "XLY": "Consumer Cyclical",
    "XLP": "Consumer Defensive",
    "XLI": "Industrials",
    "XLB": "Basic Materials",
    "XLRE": "Real Estate",
    "XLU": "Utilities",
    "XLC": "Communication Services",
}


def _pct_change(sym: str) -> dict:
    try:
        t = yf.Ticker(sym)
        hist = t.history(period="2d", auto_adjust=True)
        if len(hist) >= 2:
            price = float(hist["Close"].iloc[-1])
            prev = float(hist["Close"].iloc[-2])
        elif len(hist) == 1:
            price = float(hist["Close"].iloc[-1])
            prev = price
        else:
            return {"price": 0.0, "change_pct": 0.0, "change_abs": 0.0}
        change_abs = price - prev
        change_pct = (change_abs / prev * 100) if prev else 0.0
        return {
            "price": round(price, 2),
            "change_pct": round(change_pct, 2),
            "change_abs": round(change_abs, 2),
        }
    except Exception:
        return {"price": 0.0, "change_pct": 0.0, "change_abs": 0.0}


@router.get("/overview")
def market_overview():
    indices = []
    for sym, name in _INDICES.items():
        d = _pct_change(sym)
        indices.append({"symbol": sym, "name": name, **d})
    return {"indices": indices}


@router.get("/news")
def market_news(n: int = 8):
    try:
        items = yf.Ticker("^GSPC").news or []
        result = []
        for item in items[:n]:
            # yfinance v0.2.x uses nested "content" dict; fallback to flat dict
            content = item.get("content") or {}
            title = content.get("title") or item.get("title", "")
            publisher = (
                (content.get("provider") or {}).get("displayName")
                or item.get("publisher", "")
            )
            url = (
                (content.get("canonicalUrl") or {}).get("url")
                or item.get("link", "")
            )
            pub_date = content.get("pubDate") or str(item.get("providerPublishTime", ""))
            if title:
                result.append(
                    {"title": title, "publisher": publisher, "url": url, "time": pub_date}
                )
        return {"news": result}
    except Exception as exc:
        return {"news": [], "error": str(exc)}


@router.get("/sectors")
def market_sectors():
    sectors = []
    for sym, name in _SECTORS.items():
        d = _pct_change(sym)
        sectors.append({"symbol": sym, "name": name, "change_pct": d["change_pct"]})
    return {"sectors": sectors}

"""
SEC EDGAR Form 4 insider trading signals.

Two-step flow:
  1. `_fetch_raw(ticker, start, end)` — hits EDGAR full-text search and
     returns a list of filing metadata, including `primary_doc_url` (a
     deep link to the Form 4 XML document inside the submission).
  2. `_parse_filing_xml(url)` — fetches the XML and extracts the
     fields needed for signal generation: officer title, transaction
     code (A=acquire/purchase, D=dispose/sale), shares, price.

`get_insider_events` glues them together and returns one dict per
filing with `is_purchase`, `shares`, `price`, `officer_title`.
`compute_insider_cluster_score` converts a list of events into a
normalized 0–1 score.

Free API (no key): https://efts.sec.gov/LATEST/search-index
Rate limit: 10 req/sec — enforced by DataBroker. Fair-use requires a
descriptive User-Agent with a contact email (set below).
"""
from __future__ import annotations
import logging
import re
import warnings
import xml.etree.ElementTree as ET
from datetime import date
from typing import Optional

import requests

from ..broker import broker

log = logging.getLogger(__name__)

EDGAR_HEADERS = {
    "User-Agent": "NeuralQuant research@neuralquant.ai",
    "Accept-Encoding": "gzip, deflate",
}
EDGAR_SEARCH = "https://efts.sec.gov/LATEST/search-index"
EDGAR_ARCHIVES = "https://www.sec.gov/Archives"

# Shape of the filing-id we receive from EDGAR's hit list. Example:
#   "0001127602-25-022123:0001127602-25-022123-index.htm"
# We need to turn this into the filing's primary document URL inside
# /Archives/edgar/data/{cik}/{accession_no}/{primary_doc}.
_HIT_ID_RX = re.compile(r"^(?P<accession>\d{10}-\d{2}-\d{6}):(?P<primary>.+)$")


class Form4Connector:
    """Connector for SEC EDGAR Form 4 filings.

    Override `_fetch_raw` and/or `_parse_filing_xml` in tests to avoid
    making live network calls.
    """

    def _fetch_raw(self, ticker: str, start: date, end: date) -> list[dict]:
        """Return filing metadata for Form 4 filings matching `ticker`
        between `start` and `end` (inclusive)."""
        params = {
            "q": f'"{ticker}"',
            "forms": "4",
            "dateRange": "custom",
            "startdt": start.isoformat(),
            "enddt": end.isoformat(),
        }
        try:
            with broker.acquire("edgar"):
                resp = requests.get(
                    EDGAR_SEARCH, params=params, headers=EDGAR_HEADERS, timeout=15
                )
        except Exception as exc:
            log.warning("EDGAR search failed for %s: %s", ticker, exc)
            return []

        if resp.status_code != 200:
            return []

        hits = resp.json().get("hits", {}).get("hits", [])
        results: list[dict] = []
        for hit in hits:
            src = hit.get("_source", {})
            hit_id = hit.get("_id", "")
            match = _HIT_ID_RX.match(hit_id)
            ciks = src.get("ciks") or []
            primary_doc_url: Optional[str] = None
            if match and ciks:
                accession = match.group("accession").replace("-", "")
                primary = match.group("primary")
                # Swap the index .htm for the transaction primary .xml if present
                primary_xml = primary.rsplit(".", 1)[0] + ".xml"
                primary_doc_url = (
                    f"{EDGAR_ARCHIVES}/edgar/data/{int(ciks[0])}/{accession}/{primary_xml}"
                )
            results.append(
                {
                    "ticker": ticker,
                    "file_date": src.get("file_date"),
                    "period": src.get("period_of_report"),
                    "form_type": src.get("form_type"),
                    "primary_doc_url": primary_doc_url,
                }
            )
        return results

    def _parse_filing_xml(self, url: str) -> Optional[dict]:
        """Fetch and parse a single Form 4 XML submission.

        Returns a dict with transaction-level fields, or None if the
        filing could not be fetched/parsed. Aggregates across all
        nonDerivative transactions in the filing:
          - is_purchase: True if net-acquired shares > 0
          - shares: total acquired minus disposed
          - price: share-weighted average transaction price
          - officer_title: officer title (or 'director' fallback)
        """
        try:
            with broker.acquire("edgar"):
                resp = requests.get(url, headers=EDGAR_HEADERS, timeout=15)
        except Exception as exc:
            log.debug("EDGAR filing fetch failed %s: %s", url, exc)
            return None
        if resp.status_code != 200 or not resp.content:
            return None

        try:
            root = ET.fromstring(resp.content)
        except ET.ParseError:
            return None

        # Officer title + role flags
        officer_title = ""
        rel = root.find(".//reportingOwner/reportingOwnerRelationship")
        if rel is not None:
            ot = rel.findtext("officerTitle") or ""
            officer_title = ot.strip()
            if not officer_title:
                if (rel.findtext("isDirector") or "").strip() in ("1", "true"):
                    officer_title = "DIRECTOR"

        # Insider name
        insider_name = ""
        owner_id = root.find(".//reportingOwner/reportingOwnerId")
        if owner_id is not None:
            insider_name = (owner_id.findtext("rptOwnerName") or "").strip()

        acquired = 0.0
        disposed = 0.0
        price_sum = 0.0
        price_shares = 0.0
        for tx in root.findall(".//nonDerivativeTransaction"):
            code = (
                tx.findtext("./transactionCoding/transactionCode") or ""
            ).strip().upper()
            acq_disp = (
                tx.findtext("./transactionAmounts/transactionAcquiredDisposedCode/value")
                or ""
            ).strip().upper()
            try:
                shares = float(
                    tx.findtext("./transactionAmounts/transactionShares/value") or 0.0
                )
            except ValueError:
                shares = 0.0
            try:
                price = float(
                    tx.findtext("./transactionAmounts/transactionPricePerShare/value")
                    or 0.0
                )
            except ValueError:
                price = 0.0

            # Treat only open-market purchase (code P) / sale (code S) as a
            # strong signal. Award/grant transactions (A, M, F, etc.) are
            # ignored to avoid noise from scheduled compensation.
            if code not in ("P", "S"):
                continue
            if acq_disp == "A":
                acquired += shares
            elif acq_disp == "D":
                disposed += shares
            if shares > 0 and price > 0:
                price_sum += shares * price
                price_shares += shares

        net = acquired - disposed
        if acquired == 0 and disposed == 0:
            return None

        return {
            "is_purchase": net > 0,
            "shares": abs(net),
            "price": (price_sum / price_shares) if price_shares else 0.0,
            "officer_title": officer_title,
            "insider_name": insider_name,
        }

    def get_insider_events(self, ticker: str, start: date, end: date) -> list[dict]:
        """Return parsed insider transaction events."""
        events = self._fetch_raw(ticker, start, end)
        parsed: list[dict] = []
        any_url = any(e.get("primary_doc_url") for e in events)
        for e in events:
            url = e.get("primary_doc_url")
            if not url:
                continue
            detail = self._parse_filing_xml(url)
            if detail is None:
                continue
            parsed.append({**e, **detail})

        if events and not any_url:
            # Fallback for test doubles that return metadata only without URLs
            warnings.warn(
                "Form4Connector._fetch_raw returned filings without primary_doc_url — "
                "insider-cluster score will only use any pre-parsed is_purchase fields.",
                UserWarning,
                stacklevel=2,
            )
            parsed = [e for e in events if "is_purchase" in e]

        return parsed


def compute_insider_cluster_score(events: list[dict], lookback_days: int = 90) -> float:
    """Score from 0.0 (heavy insider selling) through 0.5 (neutral / no
    activity) to 1.0 (heavy insider buying by senior officers).

    Algorithm:
      - Weight each event by officer seniority
        (CEO/President=3, CFO/COO/CTO=2, others=1)
      - Sum net weighted purchases (sells contribute half to avoid
        over-penalising routine diversification grants)
      - Map the signed score into [0, 1] around a 0.5 midpoint so
        "no insider activity" remains neutral — previously a cohort
        with zero events scored 0.0, same as heavy selling, which
        biased the composite downward.
    """
    WEIGHTS = {"CEO": 3, "PRESIDENT": 3, "CFO": 2, "COO": 2, "CTO": 2}

    if not events:
        return 0.5

    net_weighted = 0.0
    for e in events:
        title = (e.get("officer_title") or "").upper()
        weight = next((v for k, v in WEIGHTS.items() if k in title), 1)
        if e.get("is_purchase"):
            net_weighted += weight
        else:
            net_weighted -= weight * 0.5

    # Scale: ±5 weighted units saturates the signal.
    scaled = max(-5.0, min(5.0, net_weighted)) / 5.0  # -1.0 .. 1.0
    return 0.5 + 0.5 * scaled

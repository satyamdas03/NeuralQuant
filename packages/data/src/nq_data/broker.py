import copy
import time
import threading
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Generator

@dataclass
class SourceConfig:
    name: str
    requests_per_minute: int
    _lock: threading.Lock = field(default_factory=threading.Lock, init=False, repr=False)
    _request_times: list = field(default_factory=list, init=False, repr=False)

    def __deepcopy__(self, memo: dict) -> "SourceConfig":
        # Create a fresh instance; do not copy lock or request history
        return SourceConfig(name=self.name, requests_per_minute=self.requests_per_minute)

    def wait_if_needed(self) -> None:
        with self._lock:
            now = time.monotonic()
            # Remove timestamps older than 60s
            self._request_times = [t for t in self._request_times if now - t < 60]
            if len(self._request_times) >= self.requests_per_minute:
                # Wait until oldest request is >60s ago
                wait = 60 - (now - self._request_times[0]) + 0.05
                if wait > 0:
                    time.sleep(wait)
            self._request_times.append(time.monotonic())

class DataBroker:
    """Central rate-limit manager. All data connectors must go through this."""

    DEFAULTS = {
        "yfinance":      SourceConfig("yfinance",      120),
        "twelve_data":   SourceConfig("twelve_data",    8),   # 800 credits/day ≈ 8/min
        "fred":          SourceConfig("fred",           120),
        "fmp":           SourceConfig("fmp",            5),    # 250/day ≈ conservative
        "edgar":         SourceConfig("edgar",          10),   # 10 req/sec limit
        "finra":         SourceConfig("finra",          10),
        "nse":           SourceConfig("nse",            20),   # Be gentle with NSE
        "gdelt":         SourceConfig("gdelt",          30),
        "newsapi":       SourceConfig("newsapi",        5),
        "stocktwits":    SourceConfig("stocktwits",     3),    # 200/hr = 3/min
        "reddit":        SourceConfig("reddit",         60),
        "world_bank":    SourceConfig("world_bank",     30),
        "screener_in":   SourceConfig("screener_in",    6),    # Scraper — be very gentle
    }

    def __init__(self, extra_configs: list[SourceConfig] | None = None):
        self._sources: dict[str, SourceConfig] = {
            name: copy.deepcopy(cfg) for name, cfg in self.DEFAULTS.items()
        }
        for cfg in (extra_configs or []):
            self._sources[cfg.name] = cfg

    @contextmanager
    def acquire(self, source_name: str) -> Generator[None, None, None]:
        if source_name not in self._sources:
            raise KeyError(f"Unknown source: '{source_name}'. Register it in DataBroker.DEFAULTS.")
        self._sources[source_name].wait_if_needed()
        yield

# Global singleton — import and use anywhere
broker = DataBroker()

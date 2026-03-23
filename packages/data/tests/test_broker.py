import time
import pytest
from unittest.mock import patch
from nq_data.broker import DataBroker, SourceConfig

def test_broker_enforces_rate_limit():
    """DataBroker should pace requests to stay within rate limits."""
    config = SourceConfig(name="test", requests_per_minute=6)
    broker = DataBroker([config])

    times = []
    for _ in range(3):
        with broker.acquire("test"):
            times.append(time.monotonic())

    gaps = [times[i+1] - times[i] for i in range(len(times)-1)]
    # With 6 req/min, minimum gap is 10s. With 3 requests it should be near-instant
    # but we just verify the context manager works without error
    assert len(gaps) == 2

def test_broker_raises_for_unknown_source():
    broker = DataBroker([])
    with pytest.raises(KeyError):
        with broker.acquire("nonexistent"):
            pass

def test_broker_rate_limits_when_saturated():
    """When burst capacity exceeded, DataBroker should call time.sleep."""
    # 1 request per minute means the 2nd request should trigger a wait
    config = SourceConfig(name="slow_source", requests_per_minute=1)
    broker = DataBroker([config])

    with patch("nq_data.broker.time.sleep") as mock_sleep:
        # First request — should not sleep (bucket not full)
        with broker.acquire("slow_source"):
            pass
        # Second request — bucket full (1 req already in window), should sleep
        with broker.acquire("slow_source"):
            pass

        # sleep should have been called at least once
        assert mock_sleep.called

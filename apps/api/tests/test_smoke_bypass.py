from nq_api.auth import deps


def test_bypass_inactive_when_unset(monkeypatch):
    monkeypatch.delenv("SMOKE_TEST_SECRET", raising=False)
    assert deps._smoke_bypass_ok("anything") is False


def test_bypass_inactive_when_secret_too_short(monkeypatch):
    monkeypatch.setenv("SMOKE_TEST_SECRET", "short")
    assert deps._smoke_bypass_ok("short") is False


def test_bypass_active_when_strong_and_matches(monkeypatch):
    secret = "x" * 24
    monkeypatch.setenv("SMOKE_TEST_SECRET", secret)
    assert deps._smoke_bypass_ok(secret) is True
    assert deps._smoke_bypass_ok("wrong") is False

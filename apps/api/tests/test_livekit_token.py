"""Tests for /livekit/token — veronica mode, auth gate, usage cap,
and QuantAstra regression."""
from unittest.mock import patch

from fastapi.testclient import TestClient

from nq_api.main import app
from nq_api.auth.deps import get_current_user_optional
from nq_api.auth.models import User
from nq_api.routes import livekit_token as lt


client = TestClient(app)

FAKE_USER = User(id="user-42", email="v@test.com", tier="pro")


def _as_user():
    app.dependency_overrides[get_current_user_optional] = lambda: FAKE_USER


def _as_guest():
    app.dependency_overrides[get_current_user_optional] = lambda: None


def teardown_function():
    app.dependency_overrides.pop(get_current_user_optional, None)


class TestVeronicaMode:
    def test_guest_gets_401(self):
        _as_guest()
        with patch.multiple(
            lt, LIVEKIT_KEY="key",
            LIVEKIT_SECRET="secretsecretsecretsecret",
        ):
            res = client.post("/livekit/token", json={"agent": "veronica"})
        assert res.status_code == 401

    def test_authed_user_gets_veronica_room(self):
        _as_user()
        with patch.multiple(
            lt, LIVEKIT_KEY="key",
            LIVEKIT_SECRET="secretsecretsecretsecret",
            LIVEKIT_URL="wss://x.livekit.cloud",
            LIVEKIT_API_URL="https://x.livekit.cloud",
        ), patch.object(lt, "_veronica_seconds_today", return_value=0), \
           patch.object(lt, "_dispatch_agent", return_value=None), \
           patch.object(lt, "_log_session_start", return_value=None):
            res = client.post("/livekit/token", json={"agent": "veronica"})
        assert res.status_code == 200
        body = res.json()
        assert body["room"] == "veronica-user-42"
        assert body["token"]

    def test_cap_exceeded_gets_429(self):
        _as_user()
        with patch.multiple(
            lt, LIVEKIT_KEY="key",
            LIVEKIT_SECRET="secretsecretsecretsecret",
        ), patch.object(lt, "_veronica_seconds_today", return_value=1800):
            res = client.post("/livekit/token", json={"agent": "veronica"})
        assert res.status_code == 429
        assert "tomorrow" in res.json()["detail"].lower()


class TestQuantAstraRegression:
    def test_guest_still_allowed_no_body(self):
        _as_guest()
        with patch.multiple(
            lt, LIVEKIT_KEY="key",
            LIVEKIT_SECRET="secretsecretsecretsecret",
            LIVEKIT_URL="wss://x.livekit.cloud",
            LIVEKIT_API_URL="https://x.livekit.cloud",
        ), patch.object(lt, "_dispatch_agent", return_value=None), \
           patch.object(lt, "_log_session_start", return_value=None):
            res = client.post("/livekit/token")
        assert res.status_code == 200
        assert res.json()["room"].startswith("quantastra-anonymous-")


class TestSecondsToday:
    def test_sums_ends_and_orphan_starts(self):
        rows = [
            {"label": "session_start", "payload": {}},
            {"label": "session_end", "payload": {"duration_s": 120}},
            {"label": "session_start", "payload": {}},  # orphan -> 600s
        ]
        with patch.object(lt, "_fetch_today_veronica_events", return_value=rows):
            assert lt._veronica_seconds_today("user-42") == 720

    def test_supabase_failure_fails_open(self):
        with patch.object(
            lt, "_fetch_today_veronica_events", side_effect=RuntimeError
        ):
            assert lt._veronica_seconds_today("user-42") == 0

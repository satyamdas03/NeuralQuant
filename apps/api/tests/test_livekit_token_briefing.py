from nq_api.routes import livekit_token as lt


def test_first_session_of_day_true(monkeypatch):
    monkeypatch.setattr(lt, "_fetch_today_veronica_events", lambda uid: [])
    assert lt._is_first_veronica_today("u1") is True


def test_second_session_of_day_false(monkeypatch):
    monkeypatch.setattr(
        lt, "_fetch_today_veronica_events",
        lambda uid: [{"label": "session_start", "payload": {}}],
    )
    assert lt._is_first_veronica_today("u1") is False


def test_first_check_fails_open_false(monkeypatch):
    def _boom(uid):
        raise RuntimeError("supabase down")
    monkeypatch.setattr(lt, "_fetch_today_veronica_events", _boom)
    assert lt._is_first_veronica_today("u1") is False  # fail closed: no briefing on error

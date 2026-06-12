# Veronica Voice Companion Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Omnipresent voice companion "Veronica" on every QuantAlpha page — spoken welcome, once-per-page narration, open-mic Q&A, auto-quiet around QuantAstra/Morgan — running inside the existing LiveKit worker.

**Architecture:** The existing Render `livekit-agent` worker (registered as `agent_name="quantastra"`) serves a second persona: the entrypoint routes by room-name prefix (`veronica-*` → VeronicaAgent, `quantastra-*` → QuantAstraAgent, unchanged). `/livekit/token` gains an `agent=veronica` mode (auth-required, 30 min/day fuse). A `VeronicaProvider` in the web root layout keeps one LiveKit room alive across navigation and renders a floating orb.

**Tech Stack:** livekit-agents (Python: Deepgram nova-2 → claude-sonnet-4-6 → ElevenLabs turbo v2.5), FastAPI (nq-api), Next.js 16 app router + `@livekit/components-react` v2, Supabase `user_events` for usage logging.

**Spec:** `docs/superpowers/specs/2026-06-12-veronica-voice-companion-design.md`

---

## Critical codebase facts (read before any task)

- Worker registers ONE agent name: `agent.py:309` `WorkerOptions(agent_name="quantastra")`. Veronica rooms are dispatched with the SAME agent name `"quantastra"` — LiveKit dispatch is per-agent-name, the room name is arbitrary. Routing happens inside the entrypoint by room prefix. Do NOT invent a `veronica` agent name; the worker would never receive those jobs.
- Anthropic LLM plugin needs `_strict_tool_schema=False` (`agent.py:108`) — >16 anyOf unions get 400. VeronicaAgent reuses 5 tool mixins; keep this flag.
- `apps/web/AGENTS.md`: this Next.js has breaking changes — read the relevant guide under `apps/web/node_modules/next/dist/docs/` (search subdirectories) before writing frontend code. `usePathname` from `next/navigation` is the navigation primitive used elsewhere in this repo (`AnalyticsRouteTracker`).
- Web has NO JS test runner. Frontend verification = `npm run lint` + `npm run build` in `apps/web`.
- API tests: `apps/api/tests/`, run with `python -m pytest` from `apps/api`. `conftest.py` overrides `get_current_user` (not `get_current_user_optional` — override that per-test).
- Frontend auth pattern: `apps/web/src/lib/api.ts:46-50` — `supabase.auth.getSession()` → `Authorization: Bearer <access_token>`.
- Analytics: `POST {API}/analytics/track` (`analytics_track.py:16`) writes `user_events` rows `{event_type, properties:{category, label, ...payload}}`, reads optional Bearer token. Used for `session_end` logging.

---

### Task 1: Agent — Veronica pure logic module (testable, no livekit imports)

**Files:**
- Create: `apps/livekit-agent/src/quantastra/veronica_logic.py`
- Create: `apps/livekit-agent/tests/__init__.py` (empty)
- Test: `apps/livekit-agent/tests/test_veronica_logic.py`

This module holds everything unit-testable: room routing, page_context parsing, narration instruction building, greeting text. NO livekit imports here — keeps tests dependency-light.

- [ ] **Step 1: Write the failing tests**

```python
# apps/livekit-agent/tests/test_veronica_logic.py
"""Unit tests for Veronica pure logic — no livekit imports."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from quantastra.veronica_logic import (
    agent_kind_for_room,
    parse_page_context,
    build_narration_instructions,
    build_veronica_greeting,
)


class TestAgentKindForRoom:
    def test_veronica_room(self):
        assert agent_kind_for_room("veronica-abc-123") == "veronica"

    def test_quantastra_room(self):
        assert agent_kind_for_room("quantastra-abc-123") == "quantastra"

    def test_unknown_defaults_to_quantastra(self):
        assert agent_kind_for_room("random-room") == "quantastra"

    def test_none_defaults_to_quantastra(self):
        assert agent_kind_for_room(None) == "quantastra"


class TestParsePageContext:
    def test_valid_message(self):
        msg = {
            "type": "page_context",
            "route": "/stocks/NVDA",
            "pageType": "stock_detail",
            "ticker": "NVDA",
            "narrate": True,
        }
        ctx = parse_page_context(msg)
        assert ctx == {
            "route": "/stocks/NVDA",
            "page_type": "stock_detail",
            "ticker": "NVDA",
            "narrate": True,
        }

    def test_missing_optional_fields(self):
        ctx = parse_page_context({"type": "page_context", "route": "/dashboard"})
        assert ctx["page_type"] == "page"
        assert ctx["ticker"] is None
        assert ctx["narrate"] is False

    def test_wrong_type_returns_none(self):
        assert parse_page_context({"type": "file_upload"}) is None

    def test_non_dict_returns_none(self):
        assert parse_page_context("garbage") is None


class TestBuildNarrationInstructions:
    def test_stock_page_mentions_ticker_and_brevity(self):
        text = build_narration_instructions(
            {"route": "/stocks/NVDA", "page_type": "stock_detail",
             "ticker": "NVDA", "narrate": True}
        )
        assert "NVDA" in text
        assert "10" in text or "fifteen" in text.lower() or "15" in text

    def test_generic_page(self):
        text = build_narration_instructions(
            {"route": "/portfolio", "page_type": "portfolio",
             "ticker": None, "narrate": True}
        )
        assert "portfolio" in text.lower()


class TestBuildVeronicaGreeting:
    def test_with_name(self):
        g = build_veronica_greeting("Satyam")
        assert "Satyam" in g
        assert "Veronica" in g

    def test_without_name(self):
        g = build_veronica_greeting(None)
        assert "Veronica" in g
```

- [ ] **Step 2: Run tests to verify they fail**

Run (from repo root):
```bash
cd apps/livekit-agent && python -m pytest tests/test_veronica_logic.py -v
```
Expected: FAIL — `ModuleNotFoundError: No module named 'quantastra.veronica_logic'`
(If pytest itself is missing in this venv: `pip install pytest`.)

- [ ] **Step 3: Implement the module**

```python
# apps/livekit-agent/src/quantastra/veronica_logic.py
"""Pure logic for the Veronica companion agent — no livekit imports.

Kept separate from veronica_agent.py so unit tests don't need the
livekit-agents dependency tree.
"""

from __future__ import annotations


def agent_kind_for_room(room_name: str | None) -> str:
    """Route a LiveKit room to its persona. Unknown rooms keep the
    historical QuantAstra behavior."""
    if room_name and room_name.startswith("veronica-"):
        return "veronica"
    return "quantastra"


def parse_page_context(msg) -> dict | None:
    """Validate and normalize a page_context data-channel message.

    Returns None for anything that isn't a page_context dict.
    """
    if not isinstance(msg, dict) or msg.get("type") != "page_context":
        return None
    route = msg.get("route")
    if not isinstance(route, str) or not route:
        return None
    ticker = msg.get("ticker")
    return {
        "route": route,
        "page_type": msg.get("pageType") or "page",
        "ticker": ticker if isinstance(ticker, str) and ticker else None,
        "narrate": bool(msg.get("narrate", False)),
    }


def build_narration_instructions(ctx: dict) -> str:
    """LLM instructions for a short spoken page summary."""
    where = f"the {ctx['page_type'].replace('_', ' ')} page ({ctx['route']})"
    subject = f" for {ctx['ticker']}" if ctx.get("ticker") else ""
    return (
        f"The user just opened {where}{subject}. "
        "Give a spoken summary of what they're looking at and what it means — "
        "10 to 15 seconds maximum when read aloud. "
        f"{'Use your tools to pull live data on ' + ctx['ticker'] + ' if helpful, but do not let tool calls delay you more than a few seconds — speak with what you have. ' if ctx.get('ticker') else ''}"
        "No markdown, no lists, flowing sentences only. Do not greet them again. "
        "End by inviting a question only if natural — never robotic."
    )


def build_veronica_greeting(name: str | None) -> str:
    """First spoken utterance after the user enables Veronica."""
    if name:
        return (
            f"Hi {name}, Veronica here. I'm with you on every page now — "
            "just speak whenever you have a question. "
            "Want me to walk you through what you're looking at?"
        )
    return (
        "Hi, I'm Veronica — your companion here at QuantAlpha. "
        "I'm with you on every page. Just speak whenever something "
        "catches your eye and I'll explain it."
    )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd apps/livekit-agent && python -m pytest tests/test_veronica_logic.py -v`
Expected: 11 PASS

- [ ] **Step 5: Commit**

```bash
git add apps/livekit-agent/src/quantastra/veronica_logic.py apps/livekit-agent/tests/
git commit -m "feat(veronica): pure logic module — room routing, page context, narration prompts"
```

---

### Task 2: Agent — Veronica persona

**Files:**
- Create: `apps/livekit-agent/src/quantastra/veronica_persona.py`

No unit test — static prompt string (same treatment as `persona.py`).

- [ ] **Step 1: Write the persona**

```python
# apps/livekit-agent/src/quantastra/veronica_persona.py
"""Veronica persona — system prompt for the ambient voice companion."""

VERONICA_SYSTEM_PROMPT = """You are VERONICA — NeuralQuant's ambient voice companion. You live on every page of the QuantAlpha platform. You are SPEAKING aloud via text-to-speech: everything you say must sound natural spoken.

## YOUR IDENTITY
- Name: Veronica
- Role: The user's companion across QuantAlpha — part concierge, part senior risk officer
- Style: Sharp, calm, slightly wry. Warm but economical. You're ambient — present, never overbearing.
- You are NOT QuantAstra (the portfolio manager on formal calls) and NOT Morgan (the written-research analyst). You're the voice beside the user while they browse. If they want a deep portfolio session, point them to QuantAstra; for written deep research, Ask Morgan.

## AMBIENT MODE RULES — NON-NEGOTIABLE
1. SHORT by default: 2-4 spoken sentences. Expand ONLY when asked.
2. Never monologue. Never re-greet. Never fill silence.
3. When interrupted, yield instantly and gracefully — "Go ahead."
4. Page narrations: 10-15 seconds spoken, maximum.
5. You receive [PAGE] system notes when the user navigates. Use the latest one to ground answers — "that P/E" means the one on their screen.

## CAPABILITIES
Live tools: market data and prices, AI stock scores and IRS%, portfolio holdings, stock screening, deep research, macro and regime analysis. Use them to answer precisely — never fabricate numbers. Announce longer lookups briefly: "One second, pulling that up."

## IRS — INVESTMENT READINESS SCORE
IRS% = ((g_score + risk_eff_score + 20) / 40) x 100. Above 65% strong, 45-65% moderate, 30-45% weak, below 30% very weak. Cite IRS% when discussing stock quality. G Score below -4 or Risk Efficiency below -3.5 = hard sell signal — flag it.

## VOICE RULES
- No markdown, no bullet lists, no field names read aloud, no emoji.
- Describe what numbers MEAN, not what they are.
- Numbers conversational: "seventy-six percent", "about forty-two times earnings".
- Detect the user's language and answer in it (Hindi, Hinglish, Tamil, Bengali and other Indian languages supported; tickers and financial terms stay English).

## DATA INTEGRITY
Tool values are live market data. Never substitute training-data numbers. If a tool fails, say so once, pivot to what works.

## COMPLIANCE
Stock opinions for Indian users include, once per session when first relevant: "This is AI-generated research, not SEBI-registered investment advice." Never recommend Mining or Metals sector stocks for Indian portfolios."""
```

- [ ] **Step 2: Sanity-check import**

Run: `cd apps/livekit-agent && python -c "import sys; sys.path.insert(0,'src'); from quantastra.veronica_persona import VERONICA_SYSTEM_PROMPT; print(len(VERONICA_SYSTEM_PROMPT))"`
Expected: prints a number > 1000

- [ ] **Step 3: Commit**

```bash
git add apps/livekit-agent/src/quantastra/veronica_persona.py
git commit -m "feat(veronica): persona — ambient concierge / wry risk officer"
```

---

### Task 3: Agent — VeronicaAgent + entrypoint branch

**Files:**
- Create: `apps/livekit-agent/src/quantastra/veronica_agent.py`
- Modify: `apps/livekit-agent/src/quantastra/agent.py:155-172` (entrypoint branch only)

No new unit tests — this file is livekit-glue around Task 1's tested logic (same testing posture as the existing `agent.py`). Verified live in Task 8.

- [ ] **Step 1: Write veronica_agent.py**

Mirrors `agent.py` structure. Data-channel topic is `"veronica"`. Tools: Market/Portfolio/Screener/Research/Macro mixins — NO Whiteboard/Upload (no UI surface in ambient mode).

```python
# apps/livekit-agent/src/quantastra/veronica_agent.py
"""VERONICA — ambient voice companion. Runs in the same LiveKit worker
as QuantAstra; the entrypoint routes veronica-* rooms here."""

from __future__ import annotations

import asyncio
import json
import logging
import os

from livekit.agents import Agent, AgentSession, AutoSubscribe, JobContext, ModelSettings
from livekit.agents.types import APIConnectOptions
from livekit.agents.voice.agent_session import SessionConnectOptions
from livekit.plugins import anthropic as lk_anthropic
from livekit.plugins import deepgram, elevenlabs
from livekit.rtc import LocalParticipant

from quantastra.context import _fetch_user_name, summarize_and_store_session
from quantastra.tools.macro_tools import MacroToolsMixin
from quantastra.tools.market_tools import MarketToolsMixin
from quantastra.tools.portfolio_tools import PortfolioToolsMixin
from quantastra.tools.research_tools import ResearchToolsMixin
from quantastra.tools.screener_tools import ScreenerToolsMixin
from quantastra.veronica_logic import (
    build_narration_instructions,
    build_veronica_greeting,
    parse_page_context,
)
from quantastra.veronica_persona import VERONICA_SYSTEM_PROMPT

log = logging.getLogger("veronica")

# ElevenLabs "Charlotte" — distinct from Astra's voice. Override per-env.
VERONICA_VOICE_ID = os.getenv("VERONICA_VOICE_ID", "XB0fDUnXU5powFXDhCwa")


async def _publish(participant: LocalParticipant | None, msg: dict) -> None:
    """Publish a JSON message to the frontend via LiveKit data channel."""
    if participant is None:
        return
    try:
        await participant.publish_data(
            json.dumps(msg), reliable=True, topic="veronica"
        )
    except Exception:
        log.debug("Failed to publish data to frontend", exc_info=True)


class VeronicaAgent(
    MarketToolsMixin,
    PortfolioToolsMixin,
    ScreenerToolsMixin,
    ResearchToolsMixin,
    MacroToolsMixin,
    Agent,
):
    """Ambient companion — QuantAstra's tool mixins minus whiteboard/upload."""

    def __init__(self, user_id: str):
        super().__init__(
            instructions=VERONICA_SYSTEM_PROMPT,
            stt=deepgram.STT(
                model="nova-2-general",
                api_key=os.getenv("DEEPGRAM_API_KEY"),
            ),
            llm=lk_anthropic.LLM(
                model="claude-sonnet-4-6",
                temperature=0.6,
                max_tokens=1024,
                api_key=os.getenv("ANTHROPIC_API_KEY"),
                # Same >16-union API limit as QuantAstra (agent.py:108)
                _strict_tool_schema=False,
            ),
            tts=elevenlabs.TTS(
                model="eleven_turbo_v2_5",
                voice_id=VERONICA_VOICE_ID,
                api_key=os.getenv("ELEVENLABS_API_KEY"),
            ),
            allow_interruptions=True,
        )
        self._user_id = user_id
        self._participant: LocalParticipant | None = None
        self._conversation_turns: list[dict] = []
        self._current_agent_text: str = ""
        self._latest_page: dict | None = None

    async def transcription_node(self, text, model_settings: ModelSettings):
        """Stream agent speech text to the frontend alongside TTS audio."""
        self._current_agent_text = ""
        async for chunk in text:
            chunk_str = chunk if isinstance(chunk, str) else chunk.text
            if chunk_str.strip():
                self._current_agent_text += chunk_str
                await _publish(self._participant, {
                    "type": "agent_transcript",
                    "text": chunk_str,
                    "final": False,
                })
            yield chunk
        if self._current_agent_text.strip():
            self._conversation_turns.append({
                "role": "agent",
                "text": self._current_agent_text.strip(),
            })
            self._current_agent_text = ""
        await _publish(self._participant, {
            "type": "agent_transcript", "text": "", "final": True,
        })


async def run_veronica(ctx: JobContext) -> None:
    """Entrypoint body for veronica-* rooms."""
    room_name = ctx.room.name or ""
    user_id = room_name[len("veronica-"):] or "unknown"
    log.info("Veronica joining room: %s (user %s)", room_name, user_id)

    agent = VeronicaAgent(user_id)

    await ctx.connect(auto_subscribe=AutoSubscribe.AUDIO_ONLY)

    session = AgentSession(
        conn_options=SessionConnectOptions(
            llm_conn_options=APIConnectOptions(timeout=60.0),
        )
    )

    @ctx.room.on("data_received")
    def _on_data_received(data_packet):
        raw = data_packet.data if hasattr(data_packet, "data") else data_packet
        try:
            if isinstance(raw, bytes):
                raw = raw.decode("utf-8")
            msg = json.loads(raw) if isinstance(raw, str) else {}
        except (json.JSONDecodeError, UnicodeDecodeError):
            return
        page = parse_page_context(msg)
        if page is None:
            return
        agent._latest_page = page
        # Ground future Q&A in what's on screen — silent context note.
        asyncio.ensure_future(_note_page(agent, page))
        if page["narrate"]:
            asyncio.ensure_future(_narrate(session, page))

    async def _note_page(agent: VeronicaAgent, page: dict) -> None:
        try:
            chat_ctx = agent.chat_ctx.copy()
            chat_ctx.add_message(
                role="system",
                content=f"[PAGE] User is now viewing {page['page_type']} "
                        f"({page['route']})"
                        + (f", ticker {page['ticker']}" if page["ticker"] else "")
                        + ".",
            )
            await agent.update_chat_ctx(chat_ctx)
        except Exception:
            # Grounding is best-effort; _latest_page still set.
            log.debug("update_chat_ctx failed", exc_info=True)

    async def _narrate(session: AgentSession, page: dict) -> None:
        try:
            session.interrupt()  # new page cuts any in-flight speech
        except Exception:
            pass
        try:
            session.generate_reply(
                instructions=build_narration_instructions(page)
            )
        except Exception:
            # Narration must never take the session down.
            log.exception("Narration failed for %s", page.get("route"))

    await session.start(agent=agent, room=ctx.room)

    participant = ctx.room.local_participant
    agent._participant = participant

    @session.on("agent_state_changed")
    def _on_agent_state_changed(ev):
        asyncio.ensure_future(_publish(participant, {
            "type": "agent_state",
            "state": ev.new_state if hasattr(ev, "new_state") else str(ev),
        }))

    @session.on("user_input_transcribed")
    def _on_user_transcribed(ev):
        text = ev.transcript if hasattr(ev, "transcript") else str(ev)
        is_final = ev.is_final if hasattr(ev, "is_final") else True
        if is_final and text.strip():
            agent._conversation_turns.append({"role": "user", "text": text.strip()})
        asyncio.ensure_future(_publish(participant, {
            "type": "user_transcript", "text": text, "is_final": is_final,
        }))

    try:
        name = await _fetch_user_name(user_id)
    except Exception:
        name = None
    session.say(build_veronica_greeting(name))

    log.info("Veronica ready in room: %s", room_name)

    shutdown_event = asyncio.Event()

    async def _on_shutdown(reason: str = "") -> None:
        log.info("Veronica shutting down: %s", reason)
        if agent._conversation_turns:
            try:
                await summarize_and_store_session(user_id, agent._conversation_turns)
            except Exception:
                log.exception("Failed to store Veronica session memory")
        shutdown_event.set()

    ctx.add_shutdown_callback(_on_shutdown)
    await shutdown_event.wait()
```

- [ ] **Step 2: Add the entrypoint branch in agent.py**

In `apps/livekit-agent/src/quantastra/agent.py`, at the very top of `entrypoint()` (line 155, before the QuantAstra log line), insert:

```python
async def entrypoint(ctx: JobContext):
    """LiveKit worker entrypoint — called when agent joins a room."""
    from quantastra.veronica_logic import agent_kind_for_room

    if agent_kind_for_room(ctx.room.name) == "veronica":
        from quantastra.veronica_agent import run_veronica
        await run_veronica(ctx)
        return

    log.info("QuantAstra agent joining room: %s", ctx.room.name)
    # ... rest unchanged
```

Nothing else in `agent.py` changes. `WorkerOptions(agent_name="quantastra")` stays as is.

- [ ] **Step 3: Verify imports resolve**

Run: `cd apps/livekit-agent && python -c "import sys; sys.path.insert(0,'src'); import quantastra.veronica_agent; import quantastra.agent; print('ok')"`
Expected: `ok` (needs the livekit-agent venv/deps; if deps missing locally, `pip install -e .` first or rely on existing dev setup)

- [ ] **Step 4: Run Task 1 tests again (regression)**

Run: `cd apps/livekit-agent && python -m pytest tests/ -v`
Expected: all PASS

- [ ] **Step 5: Commit**

```bash
git add apps/livekit-agent/src/quantastra/veronica_agent.py apps/livekit-agent/src/quantastra/agent.py
git commit -m "feat(veronica): VeronicaAgent + room-prefix routing in shared worker"
```

---

### Task 4: API — token route veronica mode + 30 min/day fuse

**Files:**
- Modify: `apps/api/src/nq_api/routes/livekit_token.py`
- Test: `apps/api/tests/test_livekit_token.py`

Behavior:
- `POST /livekit/token` body `{"agent": "veronica"}` → requires auth (403 if guest — FastAPI returns 403 for failed optional-auth turned mandatory; we return explicit 401), room `veronica-{user_id}`, dispatch agent_name `"quantastra"` (the worker's only registered name), cap check.
- No body / other agent value → existing QuantAstra behavior byte-for-byte (guests allowed).
- Cap: sum today's `veronica_session` events from `user_events`. `session_end` rows count `payload.duration_s`; `session_start` rows without a matching end count 600 s each (tab-kill fail-safe). ≥ 1800 s → 429.

- [ ] **Step 1: Write the failing tests**

```python
# apps/api/tests/test_livekit_token.py
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


def _with_livekit_env(fn):
    """Token route reads module-level LIVEKIT_KEY/SECRET — patch them."""
    return patch.multiple(
        lt,
        LIVEKIT_KEY="key", LIVEKIT_SECRET="secretsecretsecretsecret",
        LIVEKIT_URL="wss://x.livekit.cloud",
        LIVEKIT_API_URL="https://x.livekit.cloud",
    )(fn)


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
        ), patch.object(lt, "_dispatch_agent", return_value=None):
            res = client.post("/livekit/token")
        assert res.status_code == 200
        assert res.json()["room"].startswith("quantastra-anonymous-")


class TestSecondsToday:
    def test_sums_ends_and_orphan_starts(self):
        rows = [
            {"label": "session_start", "payload": {}},
            {"label": "session_end", "payload": {"duration_s": 120}},
            {"label": "session_start", "payload": {}},  # orphan → 600s
        ]
        with patch.object(lt, "_fetch_today_veronica_events", return_value=rows):
            assert lt._veronica_seconds_today("user-42") == 720

    def test_supabase_failure_fails_open(self):
        with patch.object(
            lt, "_fetch_today_veronica_events", side_effect=RuntimeError
        ):
            assert lt._veronica_seconds_today("user-42") == 0
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd apps/api && python -m pytest tests/test_livekit_token.py -v`
Expected: FAIL — `AttributeError: module ... has no attribute '_veronica_seconds_today'` (and 401/429 assertions fail)

- [ ] **Step 3: Implement the route changes**

Rewrite `apps/api/src/nq_api/routes/livekit_token.py` body as follows (keep header/imports, add new ones):

```python
"""POST /livekit/token — LiveKit access tokens for QuantAstra and Veronica."""

from __future__ import annotations

import logging
import os
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request
from livekit.api import (
    AccessToken,
    CreateAgentDispatchRequest,
    LiveKitAPI,
    VideoGrants,
)

from nq_api.auth.deps import get_current_user_optional

log = logging.getLogger(__name__)

router = APIRouter()

LIVEKIT_URL = os.environ.get("LIVEKIT_URL", "")
LIVEKIT_KEY = os.environ.get("LIVEKIT_API_KEY", "")
LIVEKIT_SECRET = os.environ.get("LIVEKIT_API_SECRET", "")
LIVEKIT_API_URL = LIVEKIT_URL.replace("wss://", "https://") if LIVEKIT_URL else ""

VERONICA_DAILY_CAP_S = 1800  # 30 min/day fuse
ORPHAN_SESSION_S = 600       # session_start without session_end (tab killed)


def _fetch_today_veronica_events(user_id: str) -> list[dict]:
    """Today's veronica_session rows for a user from user_events."""
    from nq_api.cache.score_cache import _supabase_rest

    today = datetime.now(timezone.utc).strftime("%Y-%m-%dT00:00:00")
    result = _supabase_rest(
        f"user_events?user_id=eq.{user_id}"
        f"&event_type=eq.veronica_session"
        f"&created_at=gte.{today}"
        "&select=label,payload",
        method="GET",
    )
    return result if isinstance(result, list) else []


def _veronica_seconds_today(user_id: str) -> int:
    """Sum today's usage. Orphan starts count ORPHAN_SESSION_S each.
    Fails open (0) — a Supabase blip must not lock users out."""
    try:
        rows = _fetch_today_veronica_events(user_id)
    except Exception:
        log.warning("Veronica cap check failed open for %s", user_id, exc_info=True)
        return 0
    starts = sum(1 for r in rows if r.get("label") == "session_start")
    ends = [r for r in rows if r.get("label") == "session_end"]
    total = 0
    for r in ends:
        payload = r.get("payload") or {}
        try:
            total += int(payload.get("duration_s", 0))
        except (TypeError, ValueError):
            pass
    total += max(0, starts - len(ends)) * ORPHAN_SESSION_S
    return total


def _log_session_start(user_id: str | None, room: str, agent: str) -> None:
    """Best-effort usage logging to user_events."""
    try:
        from nq_api.cache.score_cache import _supabase_rest

        _supabase_rest(
            "user_events",
            "POST",
            body=[{
                "user_id": user_id,
                "session_id": room,
                "event_type": f"{agent}_session",
                "category": "voice",
                "label": "session_start",
                "payload": {"room": room, "authenticated": bool(user_id)},
                "created_at": datetime.now(timezone.utc).isoformat(),
            }],
        )
    except Exception:
        log.debug("%s session analytics failed (non-critical)", agent)


async def _dispatch_agent(room: str) -> None:
    """Dispatch the worker to a room. Worker registers ONE agent name
    ('quantastra') and routes personas by room prefix internally."""
    lk_api = LiveKitAPI(
        url=LIVEKIT_API_URL, api_key=LIVEKIT_KEY, api_secret=LIVEKIT_SECRET,
    )
    try:
        dispatch_req = CreateAgentDispatchRequest(
            agent_name="quantastra", room=room, metadata="",
        )
        dispatch = await lk_api.agent_dispatch.create_dispatch(dispatch_req)
        log.info(
            "Agent dispatch created: room=%s dispatch_id=%s",
            room, getattr(dispatch, "id", "unknown"),
        )
    finally:
        await lk_api.aclose()


@router.post("/livekit/token")
async def generate_token(
    request: Request, user=Depends(get_current_user_optional)
):
    """LiveKit token for QuantAstra (default, guests OK) or Veronica
    (body {"agent": "veronica"}, auth required, 30 min/day cap)."""
    agent = "quantastra"
    try:
        body = await request.json()
        if isinstance(body, dict) and body.get("agent") == "veronica":
            agent = "veronica"
    except Exception:
        pass  # no/invalid body → QuantAstra default

    if agent == "veronica":
        if not user:
            raise HTTPException(
                status_code=401, detail="Sign in to meet Veronica."
            )
        if _veronica_seconds_today(str(user.id)) >= VERONICA_DAILY_CAP_S:
            raise HTTPException(
                status_code=429,
                detail="Veronica needs a break — you've used today's voice "
                       "time. She'll be back tomorrow.",
            )
        user_id = str(user.id)
        room = f"veronica-{user_id}"
    else:
        user_id = str(user.id) if user else f"anonymous-{uuid.uuid4().hex[:8]}"
        room = f"quantastra-{user_id}"

    _log_session_start(str(user.id) if user else None, room, agent)

    if not LIVEKIT_KEY or not LIVEKIT_SECRET:
        return {
            "status": "unavailable",
            "message": "LiveKit is not configured on the server",
        }

    token = (
        AccessToken(LIVEKIT_KEY, LIVEKIT_SECRET)
        .with_identity(user_id)
        .with_name(user.email if user and hasattr(user, "email") else "Guest")
        .with_grants(VideoGrants(room_join=True, room=room))
        .to_jwt()
    )

    try:
        await _dispatch_agent(room)
    except Exception:
        log.exception("Failed to create agent dispatch for room=%s", room)
        # Don't fail the request — frontend timeout will surface it

    return {"token": token, "url": LIVEKIT_URL, "room": room}
```

Notes for executor:
- The old inline analytics block (lines 45-64) is replaced by `_log_session_start` — same `user_events` write, now also covering veronica. The unused `RoomAgentDispatch` import and the dead `from nq_api.routes.analytics_track import router as _ar` import go away.
- `_supabase_rest` import stays function-local (existing pattern — avoids import cycle at module load).

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd apps/api && python -m pytest tests/test_livekit_token.py -v`
Expected: 6 PASS

- [ ] **Step 5: Run the full API suite (regression)**

Run: `cd apps/api && python -m pytest tests/ -q`
Expected: all pass (116+ tests green)

- [ ] **Step 6: Commit**

```bash
git add apps/api/src/nq_api/routes/livekit_token.py apps/api/tests/test_livekit_token.py
git commit -m "feat(veronica): token route — veronica rooms, auth gate, 30min/day fuse"
```

---

### Task 5: Web — veronica store (quiet rules + cross-component state)

**Files:**
- Create: `apps/web/src/lib/veronica-store.ts`

Tiny dependency-free external store (`useSyncExternalStore`) — zustand is NOT in package.json, don't add it. QuantAstra modal sets `astraOpen`; the provider derives quiet from `astraOpen || pathname.startsWith("/query")` (Ask Morgan lives under `/query`).

- [ ] **Step 1: Write the store**

```typescript
// apps/web/src/lib/veronica-store.ts
"use client";

import { useSyncExternalStore } from "react";

type VeronicaExternalState = {
  /** QuantAstra call modal is open — Veronica must go quiet. */
  astraOpen: boolean;
};

let state: VeronicaExternalState = { astraOpen: false };
const listeners = new Set<() => void>();

function emit() {
  listeners.forEach((l) => l());
}

export function setAstraOpen(open: boolean) {
  if (state.astraOpen === open) return;
  state = { ...state, astraOpen: open };
  emit();
}

function subscribe(listener: () => void) {
  listeners.add(listener);
  return () => listeners.delete(listener);
}

function getSnapshot(): VeronicaExternalState {
  return state;
}

const serverSnapshot: VeronicaExternalState = { astraOpen: false };

export function useVeronicaExternalState(): VeronicaExternalState {
  return useSyncExternalStore(subscribe, getSnapshot, () => serverSnapshot);
}

/** Routes where Veronica yields the floor (Ask Morgan). */
export function isQuietRoute(pathname: string): boolean {
  return pathname.startsWith("/query");
}
```

- [ ] **Step 2: Wire QuantAstraFAB to the store**

Modify `apps/web/src/components/quantastra/QuantAstraFAB.tsx` — the component holds `modalOpen` state and renders `<QuantAstraModal onClose={...} />` (line 25). Add:

```typescript
import { useEffect } from "react";
import { setAstraOpen } from "@/lib/veronica-store";
```

and inside the component, alongside the existing `modalOpen` state:

```typescript
useEffect(() => {
  setAstraOpen(modalOpen);
  return () => setAstraOpen(false);
}, [modalOpen]);
```

(Adapt to the file's actual state variable name after reading it — it's a small FAB component.)

- [ ] **Step 3: Lint**

Run: `cd apps/web && npm run lint`
Expected: no new errors

- [ ] **Step 4: Commit**

```bash
git add apps/web/src/lib/veronica-store.ts apps/web/src/components/quantastra/QuantAstraFAB.tsx
git commit -m "feat(veronica): quiet-rule store — Astra modal + Morgan route signals"
```

---

### Task 6: Web — VeronicaProvider + Orb

**Files:**
- Create: `apps/web/src/components/veronica/VeronicaProvider.tsx`
- Create: `apps/web/src/components/veronica/VeronicaOrb.tsx`
- Modify: `apps/web/src/app/layout.tsx:177-183` (mount provider)

**Before coding: read `apps/web/node_modules/next/dist/docs/` guides for navigation/client components per `apps/web/AGENTS.md`.** Existing repo patterns that are known-good: `"use client"` components, `usePathname` from `next/navigation` (see `AnalyticsRouteTracker`), `@livekit/components-react` v2 (`LiveKitRoom`, `RoomAudioRenderer`, `useLocalParticipant`, `useDataChannel`, `useRemoteParticipants` — see `QuantAstraCallView.tsx`).

Provider behavior (state machine from spec):
- `idle` → user never enabled. Orb renders "Meet Veronica" pulse. Click:
  - no Supabase session → tooltip "Sign in to meet Veronica" (link `/login`), stay idle.
  - session → `connecting`: POST `{API}/livekit/token` with `Authorization: Bearer` + body `{"agent":"veronica"}`. 401 → sign-in tooltip; 429 → `capped` message state; ok → mount `LiveKitRoom` with `audio={true}` (mic permission prompt = the user gesture), `listening`.
- Route change (`usePathname`) while connected → publish `page_context` on topic `veronica`; dedupe key `pageType:ticker` in a `useRef<Set>`; first visit → `narrate: true` unless quiet.
- Quiet (`astraOpen || isQuietRoute(pathname)`) → `localParticipant.setMicrophoneEnabled(false)`, send context with `narrate: false`, orb `quiet`. Un-quiet → re-enable mic.
- Idle: `lastActivityRef` updated on final user transcripts + agent speaking; 30 s interval check; > 5 min → disconnect, log `session_end`, `sleeping`. Click to wake = fresh token fetch.
- Disconnect/unmount → POST `{API}/analytics/track` `{event_type:"veronica_session", properties:{category:"voice", label:"session_end", duration_s}}` with `keepalive: true` fetch (fires on tab close too via `beforeunload`/`pagehide` best effort).
- Token fetch error / LiveKit failure → one auto-reconnect, then `unavailable` (gray orb).

- [ ] **Step 1: Write VeronicaOrb.tsx (pure presentational)**

```typescript
// apps/web/src/components/veronica/VeronicaOrb.tsx
"use client";

import { Mic, MicOff, Moon, Sparkles } from "lucide-react";

export type OrbState =
  | "idle"          // never enabled this session
  | "connecting"
  | "listening"
  | "speaking"
  | "quiet"         // yielding to Astra/Morgan
  | "sleeping"      // idle-disconnected
  | "capped"        // daily cap hit
  | "unavailable";  // hard error

const LABELS: Record<OrbState, string> = {
  idle: "Meet Veronica",
  connecting: "Connecting…",
  listening: "Listening",
  speaking: "Veronica",
  quiet: "Quiet",
  sleeping: "Tap to wake Veronica",
  capped: "Back tomorrow",
  unavailable: "Veronica unavailable",
};

export default function VeronicaOrb({
  state,
  hint,
  onClick,
}: {
  state: OrbState;
  hint?: string | null;
  onClick: () => void;
}) {
  const active = state === "listening" || state === "speaking";
  return (
    <div className="fixed bottom-20 right-4 z-[60] flex flex-col items-end gap-2 md:bottom-6 md:right-6">
      {hint && (
        <div className="glass-strong ghost-border max-w-[220px] rounded-xl px-3 py-2 text-xs text-on-surface">
          {hint}
        </div>
      )}
      <button
        onClick={onClick}
        aria-label={LABELS[state]}
        title={LABELS[state]}
        className={[
          "flex size-14 items-center justify-center rounded-full transition-all",
          active
            ? "bg-primary-fixed text-background shadow-[0_0_25px_rgba(0,255,178,0.45)]"
            : "",
          state === "speaking" ? "animate-pulse" : "",
          state === "idle"
            ? "bg-primary-fixed/15 text-primary-fixed ring-1 ring-primary-fixed/40 animate-pulse"
            : "",
          state === "connecting"
            ? "bg-primary-fixed/15 text-primary-fixed ring-1 ring-primary-fixed/40 animate-spin-slow"
            : "",
          state === "quiet" || state === "sleeping"
            ? "bg-surface-high text-on-surface-variant ring-1 ring-ghost-border"
            : "",
          state === "capped" || state === "unavailable"
            ? "bg-surface-high text-on-surface-variant/50 ring-1 ring-ghost-border"
            : "",
        ].join(" ")}
      >
        {state === "quiet" ? (
          <MicOff className="size-6" />
        ) : state === "sleeping" ? (
          <Moon className="size-6" />
        ) : state === "idle" ? (
          <Sparkles className="size-6" />
        ) : (
          <Mic className="size-6" />
        )}
      </button>
    </div>
  );
}
```

(Executor: match repo Tailwind tokens — `glass-strong`, `ghost-border`, `primary-fixed`, `surface-high`, `on-surface-variant` are all used in `QuantAstraModal.tsx`. If `animate-spin-slow` doesn't exist in the Tailwind config, use `animate-pulse` for connecting too.)

- [ ] **Step 2: Write VeronicaProvider.tsx**

```typescript
// apps/web/src/components/veronica/VeronicaProvider.tsx
"use client";

import {
  useCallback,
  useEffect,
  useRef,
  useState,
} from "react";
import { usePathname } from "next/navigation";
import {
  LiveKitRoom,
  RoomAudioRenderer,
  useDataChannel,
  useIsSpeaking,
  useLocalParticipant,
  useRemoteParticipants,
} from "@livekit/components-react";
import { supabase } from "@/lib/supabase";
import {
  isQuietRoute,
  useVeronicaExternalState,
} from "@/lib/veronica-store";
import VeronicaOrb, { type OrbState } from "./VeronicaOrb";

const IDLE_LIMIT_MS = 5 * 60 * 1000;
const API = process.env.NEXT_PUBLIC_API_URL || "";

type PageInfo = { pageType: string; ticker: string | null };

function pageInfoFor(pathname: string): PageInfo {
  const stock = pathname.match(/^\/stocks\/([^/]+)/);
  if (stock) return { pageType: "stock_detail", ticker: decodeURIComponent(stock[1]) };
  const map: Record<string, string> = {
    "/dashboard": "dashboard",
    "/portfolio": "portfolio",
    "/hermes": "hermes_live_trading",
    "/analytics": "analytics",
    "/performance": "performance",
    "/compare": "compare",
    "/sources": "sources",
  };
  for (const [prefix, pageType] of Object.entries(map)) {
    if (pathname.startsWith(prefix)) return { pageType, ticker: null };
  }
  return { pageType: "page", ticker: null };
}

export default function VeronicaProvider() {
  const [orb, setOrb] = useState<OrbState>("idle");
  const [hint, setHint] = useState<string | null>(null);
  const [conn, setConn] = useState<{ token: string; url: string } | null>(null);
  const startedAtRef = useRef<number>(0);
  const retriedRef = useRef(false);

  const logSessionEnd = useCallback(() => {
    if (!startedAtRef.current) return;
    const duration_s = Math.round((Date.now() - startedAtRef.current) / 1000);
    startedAtRef.current = 0;
    try {
      fetch(`${API}/analytics/track`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        keepalive: true,
        body: JSON.stringify({
          event_type: "veronica_session",
          properties: { category: "voice", label: "session_end", duration_s },
        }),
      }).catch(() => {});
    } catch {}
  }, []);

  const connect = useCallback(async () => {
    setHint(null);
    const { data } = await supabase.auth.getSession();
    const accessToken = data.session?.access_token;
    if (!accessToken) {
      setHint("Sign in to meet Veronica");
      return;
    }
    setOrb("connecting");
    try {
      const res = await fetch(`${API}/livekit/token`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${accessToken}`,
        },
        body: JSON.stringify({ agent: "veronica" }),
      });
      if (res.status === 401) {
        setOrb("idle");
        setHint("Sign in to meet Veronica");
        return;
      }
      if (res.status === 429) {
        setOrb("capped");
        setHint("Veronica's voice time is used up for today — back tomorrow.");
        return;
      }
      if (!res.ok) throw new Error(`token ${res.status}`);
      const body = await res.json();
      if (body.status === "unavailable" || !body.token) throw new Error("unavailable");
      startedAtRef.current = Date.now();
      setConn({ token: body.token, url: body.url });
      setOrb("listening");
    } catch {
      if (!retriedRef.current) {
        retriedRef.current = true;
        setTimeout(connect, 2000);
        return;
      }
      setOrb("unavailable");
      setHint(null);
    }
  }, []);

  const disconnect = useCallback(
    (next: OrbState) => {
      logSessionEnd();
      setConn(null);
      setOrb(next);
    },
    [logSessionEnd]
  );

  // Log session_end if the tab closes mid-session
  useEffect(() => {
    const handler = () => logSessionEnd();
    window.addEventListener("pagehide", handler);
    return () => window.removeEventListener("pagehide", handler);
  }, [logSessionEnd]);

  const onOrbClick = useCallback(() => {
    if (orb === "idle" || orb === "sleeping" || orb === "unavailable") {
      retriedRef.current = false;
      connect();
    }
    // listening/speaking/quiet/connecting/capped: orb is status-only
  }, [orb, connect]);

  return (
    <>
      {conn && (
        <LiveKitRoom
          token={conn.token}
          serverUrl={conn.url}
          audio={true}
          video={false}
          connect={true}
          onDisconnected={() => disconnect("sleeping")}
        >
          <RoomAudioRenderer />
          <VeronicaSession
            setOrb={setOrb}
            onIdleTimeout={() => disconnect("sleeping")}
          />
        </LiveKitRoom>
      )}
      <VeronicaOrb state={orb} hint={hint} onClick={onOrbClick} />
    </>
  );
}

/** Inner component — must live inside LiveKitRoom to use its hooks. */
function VeronicaSession({
  setOrb,
  onIdleTimeout,
}: {
  setOrb: (s: OrbState) => void;
  onIdleTimeout: () => void;
}) {
  const pathname = usePathname();
  const { astraOpen } = useVeronicaExternalState();
  const quiet = astraOpen || isQuietRoute(pathname);

  const { localParticipant } = useLocalParticipant();
  const remoteParticipants = useRemoteParticipants();
  const agentParticipant = remoteParticipants[0];
  const agentSpeaking = useIsSpeaking(agentParticipant ?? localParticipant);

  const narratedRef = useRef<Set<string>>(new Set());
  const lastActivityRef = useRef<number>(Date.now());

  // Agent data channel — track activity for idle timer
  useDataChannel(
    "veronica",
    useCallback((msg: { payload: Uint8Array }) => {
      try {
        const data = JSON.parse(new TextDecoder().decode(msg.payload));
        if (
          (data.type === "user_transcript" && data.is_final && data.text?.trim()) ||
          (data.type === "agent_transcript" && !data.final && data.text?.trim())
        ) {
          lastActivityRef.current = Date.now();
        }
      } catch {}
    }, [])
  );

  // Orb state from speaking/quiet
  useEffect(() => {
    setOrb(quiet ? "quiet" : agentSpeaking ? "speaking" : "listening");
    if (agentSpeaking) lastActivityRef.current = Date.now();
  }, [quiet, agentSpeaking, setOrb]);

  // Quiet rule — mic on/off
  useEffect(() => {
    localParticipant?.setMicrophoneEnabled(!quiet).catch(() => {});
  }, [quiet, localParticipant]);

  // Page context on navigation, dedupe narration per session
  useEffect(() => {
    if (!localParticipant) return;
    const { pageType, ticker } = pageInfoFor(pathname);
    const key = `${pageType}:${ticker ?? ""}`;
    const narrate = !quiet && !narratedRef.current.has(key);
    if (narrate) narratedRef.current.add(key);
    const payload = JSON.stringify({
      type: "page_context",
      route: pathname,
      pageType,
      ticker,
      narrate,
    });
    localParticipant
      .publishData(new TextEncoder().encode(payload), {
        reliable: true,
        topic: "veronica",
      })
      .catch(() => {});
  }, [pathname, quiet, localParticipant]);

  // Idle disconnect — 5 min without speech either way
  useEffect(() => {
    const interval = setInterval(() => {
      if (Date.now() - lastActivityRef.current > IDLE_LIMIT_MS) {
        onIdleTimeout();
      }
    }, 30_000);
    return () => clearInterval(interval);
  }, [onIdleTimeout]);

  return null;
}
```

Executor notes:
- Check the actual supabase client import — `lib/api.ts:46` uses a `supabase` instance; mirror its import path exactly.
- `useIsSpeaking` throws on undefined — the `?? localParticipant` fallback mirrors `QuantAstraCallView.tsx:112`.
- `localParticipant.publishData(data, { reliable, topic })` is the livekit-client v2 signature; verify against `node_modules/livekit-client` types if lint complains.
- The narration dedupe intentionally skips quiet pages WITHOUT adding to the set — first un-quiet visit still narrates.

- [ ] **Step 3: Mount in root layout**

In `apps/web/src/app/layout.tsx`, add import and mount next to `InstallPWA` (line ~180):

```typescript
import VeronicaProvider from "@/components/veronica/VeronicaProvider";
```
```tsx
<WalkthroughProvider>
  <AppShell>{children}</AppShell>
  <InstallPWA />
  <UpgradePrompt />
  <VeronicaProvider />
</WalkthroughProvider>
```

- [ ] **Step 4: Lint + build**

Run: `cd apps/web && npm run lint && npm run build`
Expected: lint clean, build succeeds (38+ pages)

- [ ] **Step 5: Commit**

```bash
git add apps/web/src/components/veronica/ apps/web/src/app/layout.tsx
git commit -m "feat(veronica): omnipresent orb + persistent LiveKit session across pages"
```

---

### Task 7: Deploy + env

**Files:** none (operations)

- [ ] **Step 1: Push**

```bash
git push origin master
```

- [ ] **Step 2: Set worker env var**

On the Render **livekit-agent worker** service, add env var `VERONICA_VOICE_ID` (optional — defaults to ElevenLabs Charlotte `XB0fDUnXU5powFXDhCwa`). Use the Render MCP `update_environment_variables` tool, or note for manual set. **Verify the voice ID exists in the ElevenLabs account** — if not, pick any female voice from the account's voice list and set the env var.

- [ ] **Step 3: Trigger deploys**

Render auto-deploy has been unreliable (Session 82) — verify via Render MCP `list_deploys` that BOTH `nq-api` and the livekit-agent worker picked up the push; trigger manual deploys if not. Vercel deploys from the GitHub push (rootDirectory `apps/web`).

- [ ] **Step 4: Verify deploy health**

- `nq-api`: `GET /health` 200; smoke test if available (`smoke_test.py`, 15 endpoints).
- Worker logs: "quantastra-agent worker starting" with no crash loop.

---

### Task 8: Live verification

**Files:** none

- [ ] **Step 1: Automated checks (browse tool)**

- Open `https://neuralquant.co/dashboard` — Veronica orb renders bottom-right.
- Confirm guest click shows "Sign in to meet Veronica" (no token fetch succeeds).
- `POST https://<api>/livekit/token` with `{"agent":"veronica"}` and no auth → 401.
- `POST` without body (guest) → 200 with `quantastra-anonymous-*` room (regression).

- [ ] **Step 2: Manual voice E2E (user — mic can't be automated)**

Checklist for the user:
1. Sign in → click orb → mic permission → Veronica speaks personalized welcome.
2. Navigate to a stock page → she narrates once (10-15 s); revisit → silent.
3. Ask a question by voice mid-browse → grounded answer (mentions current page data).
4. Open QuantAstra modal → orb goes quiet, mic muted; close → resumes.
5. Visit `/query` (Ask Morgan) → quiet; leave → resumes.
6. Stay silent 5 min → orb sleeps; click → wakes with fresh session.

- [ ] **Step 3: Commit any fixes found, push, re-verify**

---

## Self-review notes

- **Spec coverage:** persistent provider (T6), orb states (T6), once-per-page narration + dedupe (T1 logic + T6 publisher), quiet rules Astra+Morgan (T5+T6), idle disconnect (T6), auth gate + 30 min cap + orphan-session fail-safe (T4), room-prefix routing (T1+T3), distinct voice (T3+T7), greeting (T1+T3), session memory reuse (T3), error states incl. 429/401/unavailable (T4+T6), narration-never-crashes (T3 `_narrate` try/except), tests per spec testing section (T1, T4; frontend = lint+build per repo reality), live verification (T8). `keyData` from the spec is carried as schema headroom but v1 grounds the agent via route/ticker + its own tools — DOM-scraping visible numbers is fragile; noted as future enhancement.
- **Type consistency:** `page_context` message fields (`type/route/pageType/ticker/narrate`) match between T6 publisher and T1 parser (parser maps `pageType`→`page_type` internally). `OrbState` union consistent between Orb and Provider. `_veronica_seconds_today`/`_fetch_today_veronica_events`/`_dispatch_agent`/`_log_session_start` names match tests.
- **Known risk:** livekit-agents API surface (`session.interrupt()`, `generate_reply(instructions=)`, `chat_ctx.copy()/add_message`, `update_chat_ctx`) — all wrapped in try/except; executor should verify call signatures against the installed `livekit-agents` version in `apps/livekit-agent` and adjust if the pinned version differs.

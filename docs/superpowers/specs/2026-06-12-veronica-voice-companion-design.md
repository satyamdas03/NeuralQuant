# VERONICA — Omnipresent Voice Companion — Design

Date: 2026-06-12 · Status: approved · Supersedes the "v1 watchdog-first" ordering in
`2026-06-11-hermes-live-trading-veronica-design.md` (watchdog moves to next session;
persona and long-term role ladder from that spec still stand).

## Goal

Veronica lives on every page of QuantAlpha as a voice companion: she welcomes the
user, narrates what they're looking at when they open a page, and answers spoken
questions at any time — while staying out of the way of QuantAstra and Ask Morgan.
Built on the existing LiveKit stack. Ships today.

## Decisions (locked in brainstorm)

| Decision | Choice |
|---|---|
| Today's scope | Voice companion only — watchdog (cron/events/push) ships next session |
| Listening model | Open mic after one-time enable, auto-disconnect after 5 min silence |
| Page narration | Auto, once per page per session; interruptible; quiet on revisits |
| Access | Logged-in users only; guests see "Sign in to meet Veronica" orb |
| Architecture | Approach A — Veronica runs inside the existing livekit-agent worker |

## Architecture (Approach A)

```
Vercel (web)                          Render (nq-api)            Render (livekit-agent worker)
┌───────────────────────────┐  POST   ┌──────────────────┐       ┌─────────────────────────────┐
│ VeronicaProvider (layout) │────────►│ /livekit/token   │       │ entrypoint(ctx)             │
│  - persistent LiveKit room│  token  │  ?agent=veronica │       │   room veronica-*  → Veronica│
│  - orb widget (all pages) │◄────────│  auth required   │       │   room quantastra-*→ Astra   │
│  - page_context publisher │         │  30 min/day cap  │       │ (same worker, same deploy)  │
│  - quiet-rule watcher     │         │  agent dispatch  │       │ Deepgram → Claude → 11Labs  │
└───────────────────────────┘         └──────────────────┘       └─────────────────────────────┘
            ▲ audio + data channel (topic "veronica") via LiveKit Cloud ▲
```

One worker process serves both agents: the entrypoint inspects `ctx.room.name`
prefix and constructs `VeronicaAgent` for `veronica-*` rooms, `QuantAstraAgent`
for `quantastra-*` rooms. Zero new infra; one deploy.

Trade-off accepted: shared worker capacity. Heavy Veronica adoption competes with
Astra calls — fine at current traffic; split into its own service when usage
justifies it.

## Components

### 1. Frontend — `VeronicaProvider` + orb

- **Provider in root layout**, above page routes, so the LiveKit room connection
  survives client-side navigation. State machine: `idle` (never enabled) →
  `connecting` → `listening` → `speaking` → `quiet` (suppressed) → `sleeping`
  (idle-disconnected) → `unavailable` (error).
- **Orb widget** bottom-right on every page, reflecting state (pulse on listening,
  waveform on speaking, dimmed on quiet/sleeping, gray on unavailable).
- **First-run**: orb pulses "Meet Veronica". Click = user gesture → mic permission
  → token fetch → room connect → spoken personalized welcome. Browsers require
  this gesture for both mic and audio autoplay; Veronica never auto-speaks on
  page load before enablement.
- **Guests**: orb renders but click shows "Sign in to meet Veronica" (signup hook).
  No token issued.
- **Page narration**: on route change the provider publishes a `page_context`
  data message (topic `veronica`): `{ route, ticker?, pageType, keyData }` where
  `keyData` is a small map of visible numbers (score, price, IRS%, etc.).
  Provider keeps a per-session dedupe set of narration keys (`pageType:ticker`);
  only first visit triggers narration — revisits send context silently (so her
  Q&A answers stay grounded in what's on screen) with `narrate: false`.
- **Quiet rules**: provider watches two signals — QuantAstra call view mounted,
  Ask Morgan input focused. Either active → mute local mic track, set
  `narrate: false` on outgoing context, orb shows quiet state. Signal clears →
  auto-resume listening. Implemented as a tiny shared store (e.g. zustand or
  context flag) that QuantAstraCallView and Morgan chat set/unset.
- **Idle disconnect**: 5 min with no user speech (tracked via local mic activity /
  agent transcript events) → provider disconnects the room (billing stops), orb
  sleeps. Click wakes (new token, reconnect). Navigation while sleeping does NOT
  reconnect.

### 2. Agent — `VeronicaAgent` (apps/livekit-agent)

- Same cascaded pipeline as QuantAstra: Deepgram `nova-2-general` STT →
  `claude-sonnet-4-6` (`_strict_tool_schema=False` — same >16-union API limit
  applies) → ElevenLabs `eleven_turbo_v2_5` with a **distinct female voice_id**
  (different from Astra's `EXAVITQu4vr4xnSDxMaL`).
- **Persona** (`veronica_persona.py`): warm concierge layered on the approved
  "sharp, calm, slightly wry senior risk officer". Ambient-mode rules: answers
  short by default (2–4 sentences spoken), expands only when asked; never
  monologues; acknowledges interruptions gracefully.
- **Tools**: reuse existing mixins — Market, Portfolio, Screener, Research,
  Macro. Excluded: Whiteboard and Upload (no UI surface in ambient mode).
- **Narration handler**: data-channel listener for `page_context` messages.
  When `narrate: true`, generates a 10–15 second spoken summary of the page
  (what the user is seeing, what the numbers mean) via the session's reply
  mechanism. Latest context is always folded into conversation state so
  follow-up questions ("is that P/E high?") resolve against the current page.
  A new `page_context` or user speech interrupts any in-flight narration.
- **Greeting**: on connect, Veronica-flavored personalized welcome reusing the
  `build_greeting_context` / `build_personalized_greeting` pattern.
- **Entrypoint branch**: `agent.py` entrypoint routes by room-name prefix.
  QuantAstra path untouched.

### 3. Backend — token + usage fuse (apps/api)

- `/livekit/token` extended with optional `agent` body/query param:
  - `agent=veronica` → **requires authenticated user** (401 otherwise), room
    `veronica-{user_id}`, dispatches the worker to the room.
  - Default/absent → existing QuantAstra behavior, unchanged (guests still OK).
- **Usage fuse**: session start logged to `user_events`
  (`event_type=veronica_session`, `label=session_start`); frontend reports
  disconnect with duration (`label=session_end`, `payload.duration_s`). Token
  endpoint sums today's durations for the user; ≥ 30 min/day → 429 with a
  friendly message the orb renders ("Veronica needs a break until tomorrow").
  Sessions missing a `session_end` (tab killed) count as 10 min each — crude
  but fail-safe.

## Error handling

- LiveKit down / token 5xx → orb gray "Veronica unavailable"; site unaffected.
- Mic permission denied → orb shows one-time hint, no retry nagging.
- Worker crash mid-session → frontend auto-reconnects once; second failure →
  sleeping state.
- Token 429 (cap) → orb message, no reconnect attempts until next day.
- Narration must never block Q&A: if a tool call inside narration fails, she
  skips the detail rather than erroring aloud.

## Testing

- **Unit (agent)**: narration prompt builder; page_context message parsing;
  room-prefix routing in entrypoint.
- **Unit (api)**: token route — guest 401 for veronica, authed 200, cap 429,
  QuantAstra path regression (guest still allowed).
- **Frontend**: dedupe-set logic; quiet-rule store transitions.
- **Live**: browse-driven check — orb renders on dashboard, token endpoint
  auth-gates. Voice E2E verified manually (headless can't grant mic).

## Out of scope (explicitly deferred)

- Watchdog (cron checks, `veronica_events`, push/email fan-out) — next session,
  per the 2026-06-11 spec.
- Wake word ("Hey Veronica"), outbound calls (LiveKit SIP), morning briefing,
  Hermes copilot, TTS voice cloning.
- Per-tier gating beyond logged-in (Pro gating decision deferred).

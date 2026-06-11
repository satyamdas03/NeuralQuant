# Hermes Live Trading Page + VERONICA v1 — Design

Date: 2026-06-11 · Status: approved approach, pre-implementation

## Part 1 — Hermes "Matrix" Live Trading Page

### Goal
Render the 24/7 Hermes paper-trading agent (Railway, BTC/USDT, self-modifying
strategy, currently v27 with 183 trades) live inside QuantAlpha: streaming
logs, trade tape, P&L, and the strategy's self-evolution story.

### Architecture (approved: Live API on Railway)
```
Railway (hermes-trading)                Render (nq-api)            Vercel (web)
┌──────────────────────────┐   proxy    ┌──────────────┐   SSE/RT  ┌──────────┐
│ loop.py (existing)       │◄──────────│ /hermes/* router│◄────────│ /hermes  │
│ + api.py  (NEW FastAPI)  │  X-Hermes- │  - auth        │          │  page    │
│   GET /status            │  Secret    │  - CORS        │          └──────────┘
│   GET /trades?n=200      │            │  - 5s cache    │
│   GET /strategy          │            │  (mirrors the  │
│   GET /reflections       │            │   OpenBB proxy │
│   GET /events  (SSE)     │            │   pattern)     │
└──────────────────────────┘            └──────────────┘
```

- **Hermes side** (`hermes_trading/api.py`): FastAPI app run alongside the loop
  (same process via thread, or second Railway service sharing the /app/state
  volume). Read-only over state files:
  - `/status` → heartbeat.json + strategy.yaml + computed aggregates
    (open position, equity, win rate, total P&L)
  - `/trades` → tail of trades.jsonl
  - `/strategy` → current + `history/` version list (the v01→v27 story)
  - `/reflections` → hypotheses.jsonl tail (what Claude changed and why)
  - `/events` → SSE: tail -f of the loop's log + trade events (the Matrix feed)
  - Shared-secret header auth (`HERMES_API_SECRET`); only nq-api calls it.
- **nq-api** `routes/hermes.py`: thin proxy (same pattern as the OpenBB proxy),
  env `HERMES_API_URL` + `HERMES_API_SECRET`. SSE passthrough for /events.
- **web** `/hermes` page ("Live Trading" nav item, BETA tag):
  - Left pane: Matrix-style auto-scrolling log stream (SSE), green-on-black.
  - Right: live P&L equity curve, open-position card, trade tape,
    win-rate / Sharpe / drawdown stat row.
  - Bottom: strategy evolution timeline (v01→v27, each node = one variable
    change + Claude's reasoning from hypotheses.jsonl).
  - Header: ● LIVE indicator from heartbeat freshness; degraded → "AGENT
    OFFLINE — last heartbeat X min ago" (page still renders cached history).
- **Disclaimers**: paper trading, not investment advice (SEBI text reused).

### Error handling
Hermes down → proxy returns 503 with last-cached status; page shows offline
banner + historical data. SSE reconnects with backoff. No external keys in web.

### Testing
- Unit: api.py file-reader endpoints against fixture state dir.
- Proxy: nq-api tests with mocked upstream.
- E2E: browse-driven check of /hermes rendering with live Railway.

## Part 2 — VERONICA v1: Proactive Watchdog (approved debut role)

One persona, four eventual roles (watchdog → briefing anchor → Hermes copilot
→ life planner). v1 = the watchdog: VERONICA initiates contact.

### v1 scope
- **Watches**: user watchlist + portfolio (score/IRS drops, sell-signal
  triggers, earnings within 48h, price moves >|3|%), Hermes events (SL hit,
  reflection changed strategy, drawdown breach), market regime flips.
- **Initiates**: web push notification + in-app VERONICA inbox card; each
  alert is a spoken-word-style brief (her voice/personality in text first;
  TTS voice in v1.5 reusing the QuantAstra ElevenLabs stack).
- **Personality**: sharp, calm, slightly wry senior risk officer — contrast
  to Morgan (analyst) and Astra (advisor). She only speaks when it matters;
  scarcity is the product.
- **Plumbing**: extends the existing in-process cron scheduler + alert_checker;
  new `veronica_events` table; notification fan-out via existing channels
  (web push + email once Resend domain is verified).
- v2+: outbound voice calls (LiveKit SIP), morning briefing, Hermes copilot.

### Open questions (next brainstorm round)
- Notification channel priority for v1 (push vs email vs WhatsApp).
- Quiet hours / frequency caps.
- Free vs paid gating (watchdog as Pro hook?).

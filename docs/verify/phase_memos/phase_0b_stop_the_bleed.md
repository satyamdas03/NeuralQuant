# Phase 0B — Stop the Bleed

**Original pass:** 2026-10-13 (AEDT), commits `9a8fd6d` (cleanup) and `bda7f15` (memo).
**Updated:** 2026-10-22, against master `5d642dd`, using the public probes from progress review 3 (2026-10-22 01:04–01:10 UTC).
**Status:** IN PROGRESS.

The 2026-10-13 version of this memo carried a September date and said the cleanup was "complete and deployed". On 2026-10-13 it was not deployed: STATUS records that the public API ran a build older than `9a8fd6d` until the manual deploy on 2026-10-18. That memo is withdrawn. This memo replaces it.

---

## Matched by a public curl on 2026-10-22

Only items whose unauthenticated public GET matched on 2026-10-22 are listed here.

| Item | Probe | Result on 2026-10-22 |
|---|---|---|
| Unknown ticker | `GET https://neuralquant.onrender.com/stocks/NOTAREALTICKERXYZ?market=US` | 404 `{"detail":"Unknown ticker NOTAREALTICKERXYZ"}` |
| Public backtest results | `GET /testing/quarterly/public-results` | 200, `available: false`, `summary: null`, empty pools and curve. No `alpha` or `hit_rate` in the JSON. |
| Cron status without a token | `GET /cron/nightly-score/status` (no header) | 401 `{"detail":"missing Bearer token"}` |
| Hermes removed | web `/hermes`; API `/hermes`, `/hermes/health`, `/hermes/status` | 404 on all |
| Accuracy route gated | `GET /backtest/accuracy` | 401 `{"detail":"missing Bearer token"}` |
| Homepage 87% claim | `curl https://www.neuralquant.co/ \| grep -c '87%'` | 0 |

## Not verified live

Everything else in Phase 0-SEC and Phase 0B is tracked in `docs/verify/STATUS.md` with its own status. In particular S1 (auth on `POST /live/classify`, `POST /trade/backtest`) and S4 (Ask AI error handling) are not VERIFIED-LIVE: S1 is CONDITIONAL and was not re-probed (no POSTs are sent), and S4 timeout and error paths still return 200 HOLD.

Open 0B work on 2026-10-22: the methodology "BUY / HOLD / SELL" pipeline step (B5), the `/pricing` disclaimer (B7), and "Beat the market" / "Institutional-grade" still in `apps/web/src/app/layout.tsx` and its JSON-LD (B2).

## Gate decision

Phase 0B is **IN PROGRESS**. If this memo and STATUS disagree, STATUS wins and this memo is wrong.

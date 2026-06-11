# NeuralQuant — Asset Inventory (Sale Contents)

What a buyer receives. Companion docs: [ARCHITECTURE.md](ARCHITECTURE.md),
[BUG_HISTORY.md](BUG_HISTORY.md), [OPERATIONS.md](OPERATIONS.md),
[HANDOVER.md](HANDOVER.md).

## 1. Code

| Asset | Detail |
|---|---|
| NeuralQuant monorepo | FastAPI backend (33 routers), Next.js 16 web (33+ pages), Expo mobile (5-tab), LiveKit voice agent — ~200+ commits, proprietary license |
| anjali-value-stocks (sister repo) | India value-stock Excel pipeline feeding quantfactor_universe |
| PARA-DEBATE engine | 5 specialist + adversarial + head-analyst agents, parallel orchestration, metric validation, hallucination guards, consensus clamping |
| yf_guard + data pipeline | 6-tier fallback chain; every yfinance/NSE/India quirk from 126 documented bugs already solved |
| Demo stack | `docker compose up` with zero API keys — seeded Postgres + PostgREST + bundled PARA-DEBATE sample |
| Test suite | 113 tests, single-command green (`pytest apps/api/tests/ packages/`) |
| AWS Bedrock adapter | `.messages.create()`-compatible client; run on buyer's AWS account day one |

## 2. Methodology IP

- **IRS%** scoring system: G Score (−12..+12) + Risk Efficiency (−8..+8) →
  IRS% = (raw + 20) / 40 × 100, quintile engine over 1,750+ US + IN stocks.
- 5-factor quant engine with HMM regime reweighting (separate US / IN macro).
- Quarterly testing framework (machinery to keep generating proof) +
  **Q1FY27 backtest results: +13.5% avg alpha vs Nifty50, ~89% hit rate**
  across 3 pools, stored in Supabase + CSV export.
- Agent prompts and orchestration logic.
- Public methodology page (neuralquant.co/methodology) documenting derivations,
  walk-forward validation, model governance.

## 3. Brand & web presence

- neuralquant.co domain (Porkbun) + DNS/email (Resend DKIM) setup.
- Brand/design system ("Obsidian Quantum"), logo assets, OG images, PWA icons.
- LinkedIn company page content history (transfer optional).

## 4. Data

- Supabase production database (score_cache, anjali_enrichment,
  quantfactor_universe, quarterly test tables, 25 migrations).
- Bundled demo snapshot (5 tables, 1,669 rows) + real PARA-DEBATE sample JSON.
- DB backup tooling (`scripts/backup_database.*`).

## 5. Documentation

- 5-file due-diligence bundle (`docs/`), 337-line shutdown/resume runbook,
  126-bug history, complete `.env.example`, `render.yaml` blueprint.
- 82 session-by-session build logs (available in diligence data room).

## 6. Optional

- Founder transition/consulting, 3–6 months (separately priced).

## Explicitly NOT included

- Founder's personal accounts (GitHub identity, Anthropic, AWS, Stripe, PayPal).
- FMP Premium subscription (non-transferable — buyer re-subscribes, $49/mo).
- All API keys/secrets (rotated at close — HANDOVER.md §5).
- End-user PII unless contractually scoped in the APA.

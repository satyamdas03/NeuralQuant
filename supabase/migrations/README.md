# Supabase Migrations — canonical directory

This is the **single source of truth** for all SQL migrations. The old
`apps/api/migrations/` directory was consolidated here on 2026-08-16 to remove a
numbering collision (see "Renumbering" below).

Migrations are **not auto-applied** by the API. `nq_api.db_migrate.run_pending()`
only *checks* that a few required tables exist and logs a warning if not. Apply
each `.sql` file manually in the Supabase SQL editor, in numeric order.

## Inventory

| File | Purpose |
|------|---------|
| `004_alerts.sql` | Price-alert subscriptions |
| `006_team_hub.sql` | Team collaboration hub |
| `007_conversations.sql` | Ask-Morgan conversation storage |
| `008_roe_fcf_columns.sql` | ROE / FCF columns on score cache |
| `009_enrichment_cache.sql` | Enrichment cache table |
| `011_user_profiles.sql` | User profiles |
| `012_anjali_enrichment.sql` | Anjali (QuantFactor) enrichment |
| `012a_email_market_wrap.sql` | Market-wrap email opt-in (removed later by 028) |
| `012b_score_cache_history.sql` | Append-only daily score history (walk-forward) |
| `013_signal_log.sql` | Trade signal log |
| `014_news_classifications.sql` | News classification cache |
| `015_session_tracking.sql` | Session tracking |
| `016_session_fix_fk.sql` | Session FK fix |
| `017_shared_analyses.sql` | Shareable analyses |
| `018_user_events.sql` | User event analytics |
| `019_email_schedule.sql` | Email scheduler (removed later by 028) |
| `020_anjali_enrichment_irs_columns.sql` | IRS% columns on anjali_enrichment |
| `021_quarterly_testing.sql` | Quarterly backtest results |
| `022_mobile_push_tokens.sql` | Mobile push tokens |
| `022_score_cache_growth_percentile.sql` | `growth_percentile` column on score_cache |
| `023_user_profiles_risk_v2.sql` | Risk-profile v2 columns |
| `024_stock_snapshot.sql` | `stock_snapshot` table (30-min price refresh) |
| `025_quantfactor_universe.sql` | `quantfactor_universe` table (India + US universe) |
| `026_enable_rls.sql` | Row-Level Security (defense-in-depth net) |
| `027_security_events.sql` | `security_events` audit-log table |
| `028_remove_email_schema.sql` | Drop email schema (email feature removed) |
| `029_drop_legacy_email_columns.sql` | Drop leftover `public.users` email columns (optional cleanup) |

## Renumbering (2026-08-16)

The old `apps/api/migrations/` directory had three files whose numbers collided
with unrelated migrations here. They were moved and renumbered:

| Old path | New path |
|----------|----------|
| `apps/api/migrations/020_enable_rls.sql` | `026_enable_rls.sql` |
| `apps/api/migrations/021_security_events.sql` | `027_security_events.sql` |
| `apps/api/migrations/023_remove_email_schema.sql` | `028_remove_email_schema.sql` |

The old `apps/api/migrations/010_score_cache_history.sql` was **deleted** — it is
an older, superseded duplicate of `012b_score_cache_history.sql` (which has
column defaults and correct RLS policies). Keep `012b` as canonical.

## Apply order

Numeric order is correct for a fresh database. For an existing database, apply
only the files not yet applied — every `CREATE TABLE` uses `IF NOT EXISTS`, and
column adds use `ADD COLUMN IF NOT EXISTS`, so re-running is safe.

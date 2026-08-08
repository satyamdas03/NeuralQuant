-- Migration 022: growth_percentile column on score_cache (+ history)
-- Fixes: growth sub-score hardcoded 0.5 for every ticker (Session 102 known gap).
-- The nightly_score writer already emits growth_percentile in its row payload;
-- upsert_scores() silently drops it because the column does not exist.
-- Growth percentile is derived cross-sectionally from quantfactor growth_score.

ALTER TABLE score_cache
    ADD COLUMN IF NOT EXISTS growth_percentile DOUBLE PRECISION DEFAULT 0.5;

ALTER TABLE score_cache_history
    ADD COLUMN IF NOT EXISTS growth_percentile DOUBLE PRECISION DEFAULT 0.5;

-- Backfill: leave existing rows at 0.5 default — next nightly rebuild (02:00/02:30 UTC)
-- repopulates the full universe with real values.

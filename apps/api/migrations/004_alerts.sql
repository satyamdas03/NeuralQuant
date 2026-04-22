-- Alert subscriptions: users subscribe to score change alerts for tickers
CREATE TABLE IF NOT EXISTS alert_subscriptions (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id     UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    ticker      TEXT NOT NULL,
    market      TEXT NOT NULL DEFAULT 'US' CHECK (market IN ('US', 'IN')),
    alert_type  TEXT NOT NULL DEFAULT 'score_change' CHECK (alert_type IN ('score_change', 'regime_change', 'threshold')),
    -- For threshold alerts: trigger when composite_score crosses this value
    threshold   NUMERIC(5, 2),
    -- Minimum score delta to trigger a score_change alert
    min_delta   NUMERIC(4, 2) DEFAULT 0.10,
    last_triggered_at TIMTIMESTAMP WITH TIME ZONE,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE(user_id, ticker, market, alert_type)
);

-- Alert delivery log: dedup + audit trail
CREATE TABLE IF NOT EXISTS alert_deliveries (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id     UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    subscription_id UUID NOT NULL REFERENCES alert_subscriptions(id) ON DELETE CASCADE,
    ticker      TEXT NOT NULL,
    market      TEXT NOT NULL,
    alert_type  TEXT NOT NULL,
    old_value   NUMERIC(5, 2),
    new_value   NUMERIC(5, 2),
    delivered_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- RLS
ALTER TABLE alert_subscriptions ENABLE ROW LEVEL SECURITY;
ALTER TABLE alert_deliveries ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Users see own alert subs" ON alert_subscriptions
    FOR ALL USING (user_id = auth.uid());

CREATE POLICY "Users see own alert deliveries" ON alert_deliveries
    FOR SELECT USING (user_id = auth.uid());

-- Index for fast per-user lookups
CREATE INDEX idx_alert_subs_user ON alert_subscriptions(user_id);
CREATE INDEX idx_alert_subs_ticker_market ON alert_subscriptions(ticker, market);
CREATE INDEX idx_alert_deliveries_user ON alert_deliveries(user_id);
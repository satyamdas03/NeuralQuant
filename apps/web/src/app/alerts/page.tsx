"use client";
import { useEffect, useState } from "react";
import { authedApi } from "@/lib/api";
import type { AlertSubscription, AlertDelivery, AlertType } from "@/lib/types";
import GhostBorderCard from "@/components/ui/GhostBorderCard";
import GradientButton from "@/components/ui/GradientButton";
import { Bell, Plus, Trash2, Loader2, ArrowUpRight, ArrowDownRight, X } from "lucide-react";

export default function AlertsPage() {
  const [subs, setSubs] = useState<AlertSubscription[]>([]);
  const [deliveries, setDeliveries] = useState<AlertDelivery[]>([]);
  const [loading, setLoading] = useState(true);
  const [showAdd, setShowAdd] = useState(false);

  const fetchAll = async () => {
    try {
      const [s, d] = await Promise.all([
        authedApi.listAlertSubscriptions(),
        authedApi.listAlertDeliveries(30),
      ]);
      setSubs(s.items);
      setDeliveries(d.items);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { fetchAll(); }, []);

  const deleteSub = async (id: string) => {
    await authedApi.deleteAlertSubscription(id);
    setSubs(prev => prev.filter(s => s.id !== id));
  };

  if (loading) return <AlertsSkeleton />;

  return (
    <div className="space-y-6 p-4 lg:p-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="font-headline text-2xl font-bold text-on-surface">Alerts</h1>
          <p className="text-sm text-on-surface-variant mt-1">
            Get email notifications when scores change or cross thresholds.
          </p>
        </div>
        <GradientButton onClick={() => setShowAdd(true)} size="sm">
          <Plus size={14} /> New Alert
        </GradientButton>
      </div>

      {showAdd && (
        <AddAlertCard
          onCreated={(sub) => { setSubs(prev => [sub, ...prev]); setShowAdd(false); }}
          onCancel={() => setShowAdd(false)}
        />
      )}

      {/* Active subscriptions */}
      <section>
        <h2 className="font-semibold text-sm text-on-surface-variant uppercase tracking-wide mb-3">
          Active Alerts ({subs.length})
        </h2>
        {subs.length === 0 ? (
          <GhostBorderCard>
            <div className="text-center py-8">
              <Bell size={24} className="mx-auto text-on-surface-variant mb-2" />
              <p className="text-sm text-on-surface-variant">No alerts set up yet.</p>
              <p className="text-xs text-on-surface-variant mt-1">
                Create one to get notified when a stock score changes.
              </p>
            </div>
          </GhostBorderCard>
        ) : (
          <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-3">
            {subs.map(sub => (
              <AlertSubCard key={sub.id} sub={sub} onDelete={deleteSub} />
            ))}
          </div>
        )}
      </section>

      {/* Recent deliveries */}
      <section>
        <h2 className="font-semibold text-sm text-on-surface-variant uppercase tracking-wide mb-3">
          Recent Notifications
        </h2>
        {deliveries.length === 0 ? (
          <GhostBorderCard>
            <p className="text-sm text-on-surface-variant text-center py-6">
              No notifications triggered yet. Alerts fire when scores change.
            </p>
          </GhostBorderCard>
        ) : (
          <div className="space-y-2">
            {deliveries.map(d => (
              <DeliveryRow key={d.id} delivery={d} />
            ))}
          </div>
        )}
      </section>
    </div>
  );
}

function AlertSubCard({ sub, onDelete }: { sub: AlertSubscription; onDelete: (id: string) => void }) {
  const typeLabel: Record<AlertType, string> = {
    score_change: "Score Change",
    regime_change: "Regime Change",
    threshold: "Threshold",
  };
  return (
    <GhostBorderCard className="flex items-start justify-between gap-3">
      <div>
        <div className="flex items-center gap-2">
          <span className="font-headline font-bold text-on-surface">{sub.ticker}</span>
          <span className="text-xs text-on-surface-variant px-1.5 py-0.5 rounded ghost-border">
            {sub.market}
          </span>
        </div>
        <p className="text-xs text-on-surface-variant mt-1">
          {typeLabel[sub.alert_type]}
          {sub.alert_type === "threshold" && sub.threshold != null && ` → ${sub.threshold.toFixed(2)}`}
          {sub.alert_type === "score_change" && ` (min Δ${sub.min_delta.toFixed(2)})`}
        </p>
        {sub.last_triggered_at && (
          <p className="text-xs text-on-surface-variant mt-1 opacity-60">
            Last: {new Date(sub.last_triggered_at).toLocaleDateString()}
          </p>
        )}
      </div>
      <button
        onClick={() => onDelete(sub.id)}
        className="text-on-surface-variant hover:text-error transition-colors p-1"
      >
        <Trash2 size={14} />
      </button>
    </GhostBorderCard>
  );
}

function DeliveryRow({ delivery }: { delivery: AlertDelivery }) {
  const delta = delivery.new_value != null && delivery.old_value != null
    ? delivery.new_value - delivery.old_value
    : null;
  const up = delta != null && delta > 0;
  return (
    <GhostBorderCard className="flex items-center justify-between text-sm">
      <div className="flex items-center gap-3">
        <span className="font-headline font-bold text-on-surface">{delivery.ticker}</span>
        <span className="text-xs text-on-surface-variant">{delivery.market}</span>
        <span className="text-xs text-on-surface-variant px-1.5 py-0.5 rounded ghost-border capitalize">
          {delivery.alert_type.replace("_", " ")}
        </span>
      </div>
      <div className="flex items-center gap-2 tabular-nums">
        {delta != null && (
          <span className={up ? "text-tertiary" : "text-error"}>
            {up ? <ArrowUpRight size={12} /> : <ArrowDownRight size={12} />}
            {up ? "+" : ""}{delta.toFixed(2)}
          </span>
        )}
        <span className="text-xs text-on-surface-variant">
          {new Date(delivery.delivered_at).toLocaleDateString()}
        </span>
      </div>
    </GhostBorderCard>
  );
}

function AddAlertCard({
  onCreated,
  onCancel,
}: { onCreated: (sub: AlertSubscription) => void; onCancel: () => void }) {
  const [ticker, setTicker] = useState("");
  const [market, setMarket] = useState<"US" | "IN">("US");
  const [alertType, setAlertType] = useState<AlertType>("score_change");
  const [threshold, setThreshold] = useState("0.70");
  const [minDelta, setMinDelta] = useState("0.10");
  const [submitting, setSubmitting] = useState(false);

  const submit = async () => {
    setSubmitting(true);
    try {
      const sub = await authedApi.createAlertSubscription({
        ticker,
        market,
        alert_type: alertType,
        threshold: alertType === "threshold" ? parseFloat(threshold) : undefined,
        min_delta: parseFloat(minDelta),
      });
      onCreated(sub);
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <GhostBorderCard className="space-y-4">
      <div className="flex items-center justify-between">
        <h3 className="font-semibold text-on-surface">New Alert</h3>
        <button onClick={onCancel} className="text-on-surface-variant hover:text-on-surface">
          <X size={16} />
        </button>
      </div>

      <div className="grid sm:grid-cols-2 gap-3">
        <div>
          <label className="text-xs text-on-surface-variant block mb-1">Ticker</label>
          <input
            value={ticker}
            onChange={e => setTicker(e.target.value.toUpperCase())}
            placeholder="AAPL"
            className="w-full px-3 py-2 rounded-lg bg-surface-container text-on-surface text-sm ghost-border focus:outline-none focus:ring-1 focus:ring-primary"
          />
        </div>
        <div>
          <label className="text-xs text-on-surface-variant block mb-1">Market</label>
          <select
            value={market}
            onChange={e => setMarket(e.target.value as "US" | "IN")}
            className="w-full px-3 py-2 rounded-lg bg-surface-container text-on-surface text-sm ghost-border"
          >
            <option value="US">US</option>
            <option value="IN">India</option>
          </select>
        </div>
        <div>
          <label className="text-xs text-on-surface-variant block mb-1">Alert Type</label>
          <select
            value={alertType}
            onChange={e => setAlertType(e.target.value as AlertType)}
            className="w-full px-3 py-2 rounded-lg bg-surface-container text-on-surface text-sm ghost-border"
          >
            <option value="score_change">Score Change</option>
            <option value="regime_change">Regime Change</option>
            <option value="threshold">Threshold Cross</option>
          </select>
        </div>
        {alertType === "threshold" ? (
          <div>
            <label className="text-xs text-on-surface-variant block mb-1">Threshold</label>
            <input
              type="number" step="0.05" min="0" max="1"
              value={threshold}
              onChange={e => setThreshold(e.target.value)}
              className="w-full px-3 py-2 rounded-lg bg-surface-container text-on-surface text-sm ghost-border focus:outline-none focus:ring-1 focus:ring-primary"
            />
          </div>
        ) : (
          <div>
            <label className="text-xs text-on-surface-variant block mb-1">Min Delta</label>
            <input
              type="number" step="0.05" min="0.01" max="0.50"
              value={minDelta}
              onChange={e => setMinDelta(e.target.value)}
              className="w-full px-3 py-2 rounded-lg bg-surface-container text-on-surface text-sm ghost-border focus:outline-none focus:ring-1 focus:ring-primary"
            />
          </div>
        )}
      </div>

      <GradientButton
        onClick={submit}
        disabled={!ticker || submitting}
        size="sm"
      >
        {submitting ? <Loader2 size={14} className="animate-spin" /> : <Bell size={14} />}
        Create Alert
      </GradientButton>
    </GhostBorderCard>
  );
}

function AlertsSkeleton() {
  return (
    <div className="space-y-6 p-4 lg:p-6 animate-pulse">
      <div className="flex items-center justify-between">
        <div>
          <div className="h-7 w-24 rounded bg-surface-container" />
          <div className="h-4 w-48 rounded bg-surface-container mt-2" />
        </div>
        <div className="h-8 w-24 rounded-xl bg-surface-container" />
      </div>
      <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-3">
        {[0, 1, 2].map(i => (
          <div key={i} className="h-28 rounded-2xl bg-surface-container" />
        ))}
      </div>
      <div className="space-y-2">
        {[0, 1, 2, 3].map(i => (
          <div key={i} className="h-12 rounded-2xl bg-surface-container" />
        ))}
      </div>
    </div>
  );
}
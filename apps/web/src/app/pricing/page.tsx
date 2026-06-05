"use client";

import { useState, useEffect } from "react";
import Link from "next/link";
import { TIERS, formatPrice, detectCurrency, type Currency } from "@/lib/pricing";
import { trackEvent, EVENT, trackApiEvent } from "@/lib/analytics";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "https://neuralquant.onrender.com";

const FEATURE_ROWS = [
  { feature: "AI Stock Queries", free: "5/day", investor: "100/day", pro: "Unlimited", api: "Unlimited" },
  { feature: "ForeCast Score", free: "Top 10", investor: "All 100", pro: "All 100", api: "All 100" },
  { feature: "Ask Morgan Analysis", free: "5/day", investor: "100/day", pro: "Unlimited", api: "Unlimited" },
  { feature: "Screener Access", free: "Basic", investor: "Full", pro: "Full", api: "Full" },
  { feature: "Watchlists", free: "1", investor: "10", pro: "50", api: "50" },
  { feature: "Alerts", free: "—", investor: "5", pro: "25", api: "25" },
  { feature: "Backtests/Day", free: "1", investor: "10", pro: "50", api: "50" },
  { feature: "Portfolio Builder", free: "—", investor: "Full", pro: "Full", api: "Full" },
  { feature: "PARA-DEbate Engine", free: "—", investor: "Full", pro: "Full", api: "Full" },
  { feature: "Market Coverage", free: "US only", investor: "US + India", pro: "US + India", api: "US + India" },
  { feature: "Priority Access", free: "—", investor: "—", pro: "Yes", api: "Yes" },
  { feature: "API Access", free: "—", investor: "—", pro: "—", api: "Full REST API" },
];

function WhyCard({ icon, title, desc }: { icon: string; title: string; desc: string }) {
  return (
    <div className="bg-surface-container ghost-border p-4">
      <div className="text-2xl mb-2">{icon}</div>
      <h3 className="font-headline text-sm font-semibold text-on-surface">{title}</h3>
      <p className="mt-1 text-xs text-on-surface-variant leading-relaxed">{desc}</p>
    </div>
  );
}

export default function PricingPage() {
  const [currency, setCurrency] = useState<Currency>("USD");
  const [loading, setLoading] = useState<string | null>(null);

  useEffect(() => {
    setCurrency(detectCurrency());
    trackEvent(EVENT.TIER_VIEWED, { page: "pricing" });
    trackApiEvent("pricing_viewed").catch(() => {});
  }, []);

  async function handleCheckout(tier: string, provider: "paypal" | "stripe" = "stripe") {
    setLoading(tier);
    trackEvent(EVENT.CHECKOUT_STARTED, { tier, provider, currency });
    try {
      const token = (() => {
        if (typeof window === "undefined") return "";
        const stored = localStorage.getItem("nq_session");
        if (stored) { try { return JSON.parse(stored).access_token; } catch { /* */ } }
        return "";
      })();
      const endpoint = provider === "stripe"
        ? `${API_URL}/checkout/stripe/session?tier=${tier}&currency=${currency}`
        : `${API_URL}/checkout/session?tier=${tier}&currency=USD`;
      const res = await fetch(endpoint, {
        method: "POST",
        headers: { ...(token ? { Authorization: `Bearer ${token}` } : {}) },
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(err.detail || "Checkout failed");
      }
      const { url } = await res.json();
      if (url) window.location.href = url;
    } catch (e) {
      alert(e instanceof Error ? e.message : "Checkout failed — please try again.");
    } finally {
      setLoading(null);
    }
  }

  return (
    <div className="min-h-screen bg-surface text-on-surface">
      {/* Quota banner removed — free indefinitely during development phase */}
      <div className="max-w-6xl mx-auto px-6 py-20">
        <h1 className="font-headline text-4xl md:text-5xl font-bold tracking-tight text-center">
          Simple, transparent pricing
        </h1>
        <p className="mt-4 text-on-surface-variant text-center max-w-xl mx-auto">
          Start free forever. Upgrade when you need more queries, watchlists, or backtests.
        </p>

        {/* Currency Toggle */}
        <div className="mt-8 flex justify-center gap-2">
          <button
            onClick={() => setCurrency("INR")}
            className={`px-4 py-2 text-sm font-medium transition-colors ${
              currency === "INR"
                ? "bg-primary text-on-primary"
                : "ghost-border text-on-surface-variant hover:text-on-surface"
            }`}
          >
            ₹ INR (approx)
          </button>
          <button
            onClick={() => setCurrency("USD")}
            className={`px-4 py-2 text-sm font-medium transition-colors ${
              currency === "USD"
                ? "bg-primary text-on-primary"
                : "ghost-border text-on-surface-variant hover:text-on-surface"
            }`}
          >
            $ USD
          </button>
        </div>
        {currency === "INR" && (
          <p className="mt-2 text-center text-xs text-on-surface-variant">
            INR prices shown for reference. Stripe will charge in INR for India, USD via PayPal.
          </p>
        )}

        {/* Tier Cards */}
        <div className="mt-12 grid md:grid-cols-2 lg:grid-cols-4 gap-6">
          {TIERS.map((tier) => (
            <div
              key={tier.key}
              className={`relative ghost-border bg-surface-low/40 p-6 flex flex-col ${
                tier.popular ? "ring-2 ring-primary" : ""
              }`}
            >
              {tier.popular && (
                <span className="absolute -top-3 left-1/2 -translate-x-1/2 px-3 py-1 rounded-full bg-primary text-on-primary text-xs font-semibold">
                  Most popular
                </span>
              )}
              <h3 className="font-headline text-xl font-bold">{tier.name}</h3>
              <div className="mt-3 font-headline text-3xl font-bold gradient-cta bg-clip-text text-transparent">
                {formatPrice(tier.key === "free" ? 0 : (currency === "INR" ? tier.inrPrice : tier.usdPrice), currency)}
              </div>
              <ul className="mt-6 space-y-3 text-sm text-on-surface-variant flex-1">
                <li>✓ {tier.watchlists} watchlists</li>
                <li>✓ {tier.queriesPerDay.toLocaleString()} AI queries/day</li>
                <li>✓ {tier.backtestsPerDay} backtests/day</li>
                <li>✓ Full screener access</li>
                {tier.key !== "free" && <li>✓ Priority support</li>}
              </ul>
              <div className="mt-6">
                {tier.key === "free" ? (
                  <Link
                    href="/signup"
                    className="block text-center px-6 py-3 ghost-border text-on-surface-variant hover:text-on-surface font-medium text-sm transition-colors"
                  >
                    Get started free
                  </Link>
                ) : (
                  <div className="space-y-2">
                    <button
                      onClick={() => handleCheckout(tier.key, "stripe")}
                      disabled={loading !== null}
                      className="w-full px-6 py-3 bg-gradient-to-r from-[#c1c1ff] to-[#bdf4ff] text-[#0f0f1a] font-semibold text-sm hover:opacity-90 transition-opacity disabled:opacity-50"
                    >
                      {loading === tier.key ? "Redirecting…" : "Pay with Card"}
                    </button>
                    <button
                      onClick={() => handleCheckout(tier.key, "paypal")}
                      disabled={loading !== null}
                      className="w-full px-6 py-2.5 ghost-border text-on-surface-variant hover:text-on-surface font-medium text-xs transition-colors"
                    >
                      or pay with PayPal
                    </button>
                  </div>
                )}
              </div>
            </div>
          ))}
        </div>

        <p className="mt-8 text-center text-xs text-on-surface-variant">
          Secure payment via Stripe or PayPal. INR available for India via Stripe. Cancel anytime. No lock-in.
        </p>

        {/* Why Upgrade */}
        <div className="mt-16">
          <h2 className="font-headline text-2xl font-bold text-center">Why upgrade?</h2>
          <p className="mt-2 text-on-surface-variant text-center max-w-lg mx-auto text-sm">
            QuantAlpha uses institutional-grade AI scoring on 100+ stocks. Free gives you a taste; Investor unlocks the full engine.
          </p>
          <div className="mt-8 grid grid-cols-1 md:grid-cols-3 gap-6">
            <WhyCard
              icon="📊"
              title="Walk-Forward Validated"
              desc="Every score is backtested against real 3-month forward returns. Not curve-fitted — genuinely predictive."
            />
            <WhyCard
              icon="🎯"
              title="50+ Signals Per Stock"
              desc="Quality, momentum, value, volatility, insider activity — all combined into a single 1-10 score you can act on."
            />
            <WhyCard
              icon="⚡"
              title="Unlimited AI Analysis"
              desc="Ask any question about any stock. Get data-driven answers with live market data, not generic advice."
            />
            <WhyCard
              icon="🌍"
              title="US + India Markets"
              desc="ForeCast scores for 100 stocks across both markets. Dual-currency portfolio builder included."
            />
            <WhyCard
              icon="🔒"
              title="Priority Data Access"
              desc="Investor tier gets faster data refresh, watchlists, alerts, and priority during high-traffic periods."
            />
            <WhyCard
              icon="📈"
              title="Proven Edge"
              desc="Top-decile stocks outperform the market by measurable margins."
            />
          </div>
        </div>

        {/* Feature Comparison */}
        <div className="mt-16">
          <h2 className="font-headline text-2xl font-bold text-center">Feature comparison</h2>
          <div className="mt-8 overflow-x-auto">
            <table className="w-full text-sm border-collapse">
              <thead>
                <tr className="border-b border-outline/20">
                  <th className="text-left py-3 px-4 text-on-surface-variant font-medium">Feature</th>
                  <th className="text-center py-3 px-4 text-on-surface-variant font-medium">Free</th>
                  <th className="text-center py-3 px-4 font-medium text-primary bg-primary/5">Investor</th>
                  <th className="text-center py-3 px-4 text-on-surface-variant font-medium">Pro</th>
                  <th className="text-center py-3 px-4 text-on-surface-variant font-medium">API</th>
                </tr>
              </thead>
              <tbody>
                {FEATURE_ROWS.map((row) => (
                  <tr key={row.feature} className="border-b border-outline/10">
                    <td className="py-2.5 px-4 text-on-surface">{row.feature}</td>
                    <td className="py-2.5 px-4 text-center text-on-surface-variant">{row.free}</td>
                    <td className="py-2.5 px-4 text-center font-medium text-on-surface bg-primary/5">{row.investor}</td>
                    <td className="py-2.5 px-4 text-center text-on-surface-variant">{row.pro}</td>
                    <td className="py-2.5 px-4 text-center text-on-surface-variant">{row.api}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      </div>
    </div>
  );
}
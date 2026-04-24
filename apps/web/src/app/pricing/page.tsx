"use client";

import { useState, useEffect } from "react";
import Link from "next/link";
import { TIERS, formatPrice, detectCurrency, type Currency } from "@/lib/pricing";
import GradientButton from "@/components/ui/GradientButton";

export default function PricingPage() {
  const [currency, setCurrency] = useState<Currency>("USD");

  useEffect(() => {
    setCurrency(detectCurrency());
  }, []);

  return (
    <div className="min-h-screen bg-surface text-on-surface">
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
            className={`px-4 py-2 rounded-lg text-sm font-medium transition-colors ${
              currency === "INR"
                ? "bg-primary text-on-primary"
                : "ghost-border text-on-surface-variant hover:text-on-surface"
            }`}
          >
            ₹ INR
          </button>
          <button
            onClick={() => setCurrency("USD")}
            className={`px-4 py-2 rounded-lg text-sm font-medium transition-colors ${
              currency === "USD"
                ? "bg-primary text-on-primary"
                : "ghost-border text-on-surface-variant hover:text-on-surface"
            }`}
          >
            $ USD
          </button>
        </div>

        {/* Tier Cards */}
        <div className="mt-12 grid md:grid-cols-2 lg:grid-cols-4 gap-6">
          {TIERS.map((tier) => (
            <div
              key={tier.key}
              className={`relative rounded-2xl ghost-border bg-surface-low/40 p-6 flex flex-col ${
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
                    className="block text-center px-6 py-3 rounded-xl ghost-border text-on-surface-variant hover:text-on-surface font-medium text-sm transition-colors"
                  >
                    Get started free
                  </Link>
                ) : (
                  <GradientButton
                    href={`/api/checkout?tier=${tier.key}&currency=${currency}`}
                    size="md"
                    className="w-full"
                  >
                    Upgrade to {tier.name}
                  </GradientButton>
                )}
              </div>
            </div>
          ))}
        </div>

        <p className="mt-8 text-center text-xs text-on-surface-variant">
          All prices exclude applicable taxes. Cancel anytime. No lock-in.
        </p>
      </div>
    </div>
  );
}
"use client";

import { useState } from "react";
import type { UserProfile } from "@/lib/types";

interface Props {
  defaultAmount?: string;
  onSubmit: (profile: UserProfile) => void;
}

export default function ProfilerCard({ defaultAmount, onSubmit }: Props) {
  const [risk, setRisk] = useState<UserProfile["risk_profile"]>("balanced");
  const [horizon, setHorizon] = useState<UserProfile["time_horizon"]>("1-3yr");
  const [goal, setGoal] = useState<UserProfile["goal"]>("wealth_building");
  const [amount, setAmount] = useState(defaultAmount || "");

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    onSubmit({
      risk_profile: risk,
      time_horizon: horizon,
      goal,
      investable_amount: amount.trim() || undefined,
    });
  };

  return (
    <form
      onSubmit={handleSubmit}
      className="rounded-xl bg-surface-container ghost-border p-4 space-y-3"
    >
      <p className="text-sm text-on-surface font-medium">
        Before I build your portfolio, I need to understand your goals:
      </p>

      <div className="space-y-2">
        <label className="block text-xs text-on-surface-variant">Risk Profile</label>
        <select
          value={risk}
          onChange={(e) => setRisk(e.target.value as UserProfile["risk_profile"])}
          className="w-full rounded-lg bg-surface-high px-3 py-2 text-sm text-on-surface border border-outline/20 focus:outline-none focus:ring-2 focus:ring-primary/40"
        >
          <option value="conservative">Conservative — Protect capital</option>
          <option value="balanced">Balanced — Growth & stability</option>
          <option value="aggressive">Aggressive — Maximize returns</option>
        </select>
      </div>

      <div className="space-y-2">
        <label className="block text-xs text-on-surface-variant">Time Horizon</label>
        <select
          value={horizon}
          onChange={(e) => setHorizon(e.target.value as UserProfile["time_horizon"])}
          className="w-full rounded-lg bg-surface-high px-3 py-2 text-sm text-on-surface border border-outline/20 focus:outline-none focus:ring-2 focus:ring-primary/40"
        >
          <option value="<1yr">&lt; 1 year</option>
          <option value="1-3yr">1 – 3 years</option>
          <option value="3-5yr">3 – 5 years</option>
          <option value="5yr+">5+ years</option>
        </select>
      </div>

      <div className="space-y-2">
        <label className="block text-xs text-on-surface-variant">Investment Goal</label>
        <select
          value={goal}
          onChange={(e) => setGoal(e.target.value as UserProfile["goal"])}
          className="w-full rounded-lg bg-surface-high px-3 py-2 text-sm text-on-surface border border-outline/20 focus:outline-none focus:ring-2 focus:ring-primary/40"
        >
          <option value="wealth_building">Wealth Building</option>
          <option value="retirement">Retirement</option>
          <option value="education">Child&apos;s Education</option>
          <option value="passive_income">Passive Income</option>
          <option value="tax_saving">Tax Saving</option>
        </select>
      </div>

      <div className="space-y-2">
        <label className="block text-xs text-on-surface-variant">Investable Amount</label>
        <input
          type="text"
          value={amount}
          onChange={(e) => setAmount(e.target.value)}
          placeholder="e.g. INR 10,00,000 or $50,000"
          className="w-full rounded-lg bg-surface-high px-3 py-2 text-sm text-on-surface border border-outline/20 focus:outline-none focus:ring-2 focus:ring-primary/40"
        />
      </div>

      <button
        type="submit"
        className="w-full rounded-lg bg-primary px-4 py-2 text-sm font-medium text-on-primary hover:bg-primary/90 transition-colors"
      >
        Build My Portfolio
      </button>
    </form>
  );
}

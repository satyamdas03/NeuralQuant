export type Currency = "INR" | "USD";

export interface TierInfo {
  key: string;
  name: string;
  inrPrice: number;
  usdPrice: number;
  watchlists: number;
  queriesPerDay: number;
  backtestsPerDay: number;
  popular?: boolean;
}

// USD prices must match PayPal plan amounts exactly.
// INR prices are charged via Stripe (India-specific prices).
export const TIERS: TierInfo[] = [
  {
    key: "free",
    name: "Free",
    inrPrice: 0,
    usdPrice: 0,
    watchlists: 5,
    queriesPerDay: 50,
    backtestsPerDay: 20,
  },
  {
    key: "investor",
    name: "Investor",
    inrPrice: 899,
    usdPrice: 9.99,
    watchlists: 25,
    queriesPerDay: 100,
    backtestsPerDay: 25,
    popular: true,
  },
  {
    key: "pro",
    name: "Pro",
    inrPrice: 2499,
    usdPrice: 29.99,
    watchlists: 100,
    queriesPerDay: 1000,
    backtestsPerDay: 50,
  },
  {
    key: "api",
    name: "API",
    inrPrice: 8499,
    usdPrice: 99.99,
    watchlists: 1000,
    queriesPerDay: 100000,
    backtestsPerDay: 10000,
  },
];

export function formatPrice(amount: number, currency: Currency): string {
  if (amount === 0) return "Free forever";
  if (currency === "INR") return `~₹${amount.toLocaleString("en-IN")}/mo`;
  return `$${amount}/mo`;
}

export function detectCurrency(): Currency {
  if (typeof navigator === "undefined") return "USD";
  const lang = navigator.language || "";
  if (lang.includes("IN") || lang.startsWith("hi")) return "INR";
  return "USD";
}